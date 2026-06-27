import json
import re
from io import StringIO
from datetime import datetime, timezone
from decimal import Decimal
import csv

from models import Test, TestQuestion
from repositories.question_repository import QuestionRepository, QuestionTypeRepository
from repositories.subject_repository import SubjectMembershipRepository, SubjectRepository
from repositories.test_repository import TestQuestionRepository, TestRepository
from repositories.topic_repository import TopicRepository
from repositories.attempt_repository import TestAttemptRepository
from repositories.workspace_repository import WorkspaceRepository
from service.ai_question_service import AIQuestionService
from service.question_bank_service import QuestionBankService
from service.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from utils.academic_rbac import can_manage_subjects, verify_subject_teacher_access
from utils.db import db
from utils.enums import Difficulty, TestQuestionSourceType, TestStatus
from utils.question_type_validation import validate_question_create_payload


class TestService:
    def __init__(self):
        self.tests = TestRepository()
        self.test_questions = TestQuestionRepository()
        self.attempts = TestAttemptRepository()
        self.questions = QuestionRepository()
        self.question_types = QuestionTypeRepository()
        self.subjects = SubjectRepository()
        self.subject_memberships = SubjectMembershipRepository()
        self.topics = TopicRepository()
        self.workspaces = WorkspaceRepository()
        self.bank_service = QuestionBankService()
        self.ai_questions = AIQuestionService()

    def create_test(self, *, workspace_id: int, actor_membership, data: dict) -> Test:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found")

        subject = self.subjects.get_active_by_id(data["subject_id"], workspace_id)
        if not subject:
            raise NotFoundError("Subject not found")

        actor_link = self.subject_memberships.find_active(
            actor_membership.id, subject.id
        )
        if not can_manage_subjects(workspace, actor_membership) and not verify_subject_teacher_access(actor_link):
            raise ForbiddenError("You are not allowed to create exams for this subject")

        base_slug = self._resolve_slug(None, data["name"])
        slug = self._resolve_unique_slug(base_slug)

        total_score = self._to_decimal(data.get("total_score"), "total_score")
        passing_score = self._to_decimal(data.get("passing_score"), "passing_score")
        if total_score is not None and passing_score is not None and passing_score > total_score:
            raise ValidationError("passing_score cannot be greater than total_score")

        test = Test(
            name=data["name"].strip(),
            slug=slug,
            description=(data.get("description") or "").strip() or None,
            subject_id=subject.id,
            total_score=total_score,
            passing_score=passing_score,
            auto_distribute_scores=bool(data.get("auto_distribute_scores", False)),
            created_by_membership_id=actor_membership.id,
            status=TestStatus.DRAFT.value,
            duration_minutes=data.get("duration_minutes"),
        )
        self.tests.add(test)
        db.session.commit()
        return test

    def list_my_tests(self, actor_membership) -> list[dict]:
        rows = self.tests.list_for_creator(actor_membership.id)
        return [self.serialize_test(row) for row in rows]

    def get_test(self, *, test_id: int, workspace_id: int, actor_membership) -> dict:
        test = self._resolve_test_access(test_id, workspace_id, actor_membership)
        questions = self.test_questions.list_for_test(test.id)
        payload = self.serialize_test(test)
        payload["questions"] = [self.serialize_test_question(row) for row in questions]
        return payload

    def update_test(self, *, test_id: int, workspace_id: int, actor_membership, data: dict) -> Test:
        test = self._resolve_test_access(test_id, workspace_id, actor_membership)
        if test.status != TestStatus.DRAFT.value:
            raise ValidationError("Only DRAFT tests are editable")

        if "name" in data and data["name"]:
            test.name = data["name"].strip()
        if "slug" in data and data["slug"]:
            slug = self._resolve_slug(data.get("slug"), test.name)
            existing = self.tests.find_by_slug(slug)
            if existing and existing.id != test.id:
                raise ConflictError("Test slug already exists")
            test.slug = slug
        if "description" in data:
            test.description = (data.get("description") or "").strip() or None
        if "grading_mode" in data:
            test.grading_mode = (data.get("grading_mode") or "").strip() or None
        if "total_score" in data:
            test.total_score = self._to_decimal(data.get("total_score"), "total_score")
        if "passing_score" in data:
            test.passing_score = self._to_decimal(data.get("passing_score"), "passing_score")
        if test.total_score is not None and test.passing_score is not None and test.passing_score > test.total_score:
            raise ValidationError("passing_score cannot be greater than total_score")
        if "scoring_config" in data:
            test.scoring_config = self._dump_json(data.get("scoring_config"))
        if "settings_config" in data:
            test.settings_config = self._dump_json(data.get("settings_config"))
        if "availability_time_mode" in data:
            test.availability_time_mode = data.get("availability_time_mode")
        if "starts_at" in data:
            test.starts_at = data.get("starts_at")
        if "duration_minutes" in data:
            test.duration_minutes = data.get("duration_minutes")
        if "entry_window_minutes" in data:
            test.entry_window_minutes = data.get("entry_window_minutes")

        db.session.commit()
        return test

    def add_questions_from_bank(
        self,
        *,
        test_id: int,
        workspace_id: int,
        actor_membership,
        question_ids: list[int],
        source_type: str,
    ) -> list[dict]:
        test = self._resolve_test_access(test_id, workspace_id, actor_membership)
        if test.status != TestStatus.DRAFT.value:
            raise ValidationError("Questions can only be added while test is DRAFT")
        if not question_ids:
            raise ValidationError("question_ids must contain at least one item")

        created = []
        for question_id in question_ids:
            question = self.questions.get_by_id(question_id)
            if not question or not question.bank or question.bank.workspace_id != workspace_id:
                raise NotFoundError(f"Question {question_id} not found in workspace")
            if question.bank.subject_id != test.subject_id:
                raise ValidationError(
                    f"Question {question_id} does not belong to the test subject"
                )
            if self.test_questions.find_by_test_and_question(test.id, question.id):
                continue

            snapshot = self._snapshot_from_source_question(question)
            row = TestQuestion(
                test_id=test.id,
                question_id=question.id,
                kind=source_type,
                source_type=source_type,
                source_bank_id=question.bank_id,
                points=question.points or Decimal("1"),
                snapshot_question_text=snapshot["snapshot_question_text"],
                snapshot_explanation=snapshot["snapshot_explanation"],
                snapshot_type_code=snapshot["snapshot_type_code"],
                snapshot_topic_id=snapshot["snapshot_topic_id"],
                snapshot_topic_name=snapshot["snapshot_topic_name"],
                snapshot_difficulty=snapshot["snapshot_difficulty"],
                snapshot_points=snapshot["snapshot_points"],
                snapshot_choices_json=snapshot["snapshot_choices_json"],
            )
            self.test_questions.add(row)
            created.append(row)

        db.session.commit()
        return [self.serialize_test_question(row) for row in created]

    def add_manual_questions(
        self,
        *,
        test_id: int,
        workspace_id: int,
        actor_membership,
        questions: list[dict],
    ) -> list[dict]:
        test = self._resolve_draft_test(test_id, workspace_id, actor_membership)
        created = [
            self._create_snapshot_row_from_payload(
                test_id=test.id,
                payload=payload,
                source_type=TestQuestionSourceType.MANUAL.value,
            )
            for payload in questions
        ]
        db.session.commit()
        return [self.serialize_test_question(row) for row in created]

    def import_questions_from_csv(
        self,
        *,
        test_id: int,
        workspace_id: int,
        actor_membership,
        file_storage,
    ) -> list[dict]:
        test = self._resolve_draft_test(test_id, workspace_id, actor_membership)
        if not file_storage:
            raise ValidationError("csv_file is required")

        raw_bytes = file_storage.read()
        if not raw_bytes:
            raise ValidationError("Uploaded CSV file is empty")
        text = raw_bytes.decode("utf-8-sig")
        reader = csv.DictReader(StringIO(text))
        if not reader.fieldnames:
            raise ValidationError("CSV headers are required")

        rows = []
        for idx, row in enumerate(reader):
            rows.append(self._csv_row_to_question_payload(idx, row))
        if not rows:
            raise ValidationError("CSV file must contain at least one question row")

        created = [
            self._create_snapshot_row_from_payload(
                test_id=test.id,
                payload=payload,
                source_type=TestQuestionSourceType.IMPORT.value,
            )
            for payload in rows
        ]
        db.session.commit()
        return [self.serialize_test_question(row) for row in created]

    def add_questions_from_bank_selection(
        self,
        *,
        test_id: int,
        workspace_id: int,
        actor_membership,
        bank_id: int,
        question_ids: list[int],
    ) -> list[dict]:
        test = self._resolve_draft_test(test_id, workspace_id, actor_membership)
        bank = self.bank_service.resolve_bank_for_question_view(
            bank_id=bank_id,
            workspace_id=workspace_id,
            actor_membership=actor_membership,
        )
        if bank.subject_id != test.subject_id:
            raise ValidationError("Selected bank does not belong to exam subject")

        created = []
        for question_id in question_ids:
            question = self.questions.get_active_in_bank(question_id, bank.id)
            if not question:
                raise NotFoundError(f"Question {question_id} not found in selected bank")
            snapshot = self._snapshot_from_source_question(question)
            row = TestQuestion(
                test_id=test.id,
                question_id=None,
                kind=TestQuestionSourceType.QUESTION_BANK.value,
                source_type=TestQuestionSourceType.QUESTION_BANK.value,
                source_bank_id=bank.id,
                points=question.points or Decimal("1"),
                snapshot_question_text=snapshot["snapshot_question_text"],
                snapshot_explanation=snapshot["snapshot_explanation"],
                snapshot_type_code=snapshot["snapshot_type_code"],
                snapshot_topic_id=snapshot["snapshot_topic_id"],
                snapshot_topic_name=snapshot["snapshot_topic_name"],
                snapshot_difficulty=snapshot["snapshot_difficulty"],
                snapshot_points=snapshot["snapshot_points"],
                snapshot_choices_json=snapshot["snapshot_choices_json"],
            )
            self.test_questions.add(row)
            created.append(row)

        db.session.commit()
        return [self.serialize_test_question(row) for row in created]

    def add_random_questions_from_banks(
        self,
        *,
        test_id: int,
        workspace_id: int,
        actor_membership,
        bank_ids: list[int],
        count: int,
        difficulty: str | None = None,
        type_code: str | None = None,
        topic_id: int | None = None,
    ) -> list[dict]:
        test = self._resolve_draft_test(test_id, workspace_id, actor_membership)
        valid_bank_ids = []
        for bank_id in bank_ids:
            bank = self.bank_service.resolve_bank_for_question_view(
                bank_id=bank_id,
                workspace_id=workspace_id,
                actor_membership=actor_membership,
            )
            if bank.subject_id != test.subject_id:
                raise ValidationError("All selected banks must match exam subject")
            valid_bank_ids.append(bank.id)

        pool = self.questions.list_random_by_banks(
            bank_ids=valid_bank_ids,
            limit=count,
            difficulty=(difficulty.upper() if difficulty else None),
            type_code=type_code,
            topic_id=topic_id,
        )
        if len(pool) < count:
            raise ValidationError(
                f"Not enough questions to satisfy random selection (requested {count}, found {len(pool)})"
            )

        created = []
        for question in pool:
            snapshot = self._snapshot_from_source_question(question)
            row = TestQuestion(
                test_id=test.id,
                question_id=None,
                kind=TestQuestionSourceType.RANDOM_FROM_BANK.value,
                source_type=TestQuestionSourceType.RANDOM_FROM_BANK.value,
                source_bank_id=question.bank_id,
                points=question.points or Decimal("1"),
                snapshot_question_text=snapshot["snapshot_question_text"],
                snapshot_explanation=snapshot["snapshot_explanation"],
                snapshot_type_code=snapshot["snapshot_type_code"],
                snapshot_topic_id=snapshot["snapshot_topic_id"],
                snapshot_topic_name=snapshot["snapshot_topic_name"],
                snapshot_difficulty=snapshot["snapshot_difficulty"],
                snapshot_points=snapshot["snapshot_points"],
                snapshot_choices_json=snapshot["snapshot_choices_json"],
            )
            self.test_questions.add(row)
            created.append(row)

        db.session.commit()
        return [self.serialize_test_question(row) for row in created]

    def add_ai_generated_questions(
        self,
        *,
        test_id: int,
        workspace_id: int,
        actor_membership,
        count: int,
        type_code: str,
        difficulty: str | None = None,
        topics: list[str] | None = None,
        learning_objectives: list[str] | None = None,
        additional_instructions: str | None = None,
    ) -> tuple[list[dict], str, str]:
        test = self._resolve_draft_test(test_id, workspace_id, actor_membership)
        if not test.subject:
            raise ValidationError("Test must have a subject for AI question generation")

        subject_name = test.subject.name
        topics = topics or []
        learning_objectives = learning_objectives or []

        ai_request = self.ai_questions.build_request_body(
            subject_name=subject_name,
            exam_name=test.name,
            count=count,
            type_code=type_code,
            difficulty=difficulty,
            topics=topics,
            learning_objectives=learning_objectives,
            additional_instructions=additional_instructions,
        )
        payloads, model_name = self.ai_questions.generate_questions(
            request_body=ai_request
        )

        created = []
        for payload in payloads:
            created.append(
                self._create_snapshot_row_from_payload(
                    test_id=test.id,
                    payload=payload,
                    source_type=TestQuestionSourceType.AI.value,
                )
            )
        db.session.commit()
        return [self.serialize_test_question(row) for row in created], model_name, subject_name

    def update_test_question(
        self,
        *,
        test_id: int,
        test_question_id: int,
        workspace_id: int,
        actor_membership,
        data: dict,
    ) -> dict:
        test = self._resolve_draft_test(test_id, workspace_id, actor_membership)
        self._ensure_no_attempts_on_test(test.id)
        row = self._get_test_question_or_404(test.id, test_question_id)
        merged = self._merge_test_question_payload(row, data)
        validated = self._validate_and_normalize_payload(merged)
        topic_id, topic_name = self._resolve_topic_snapshot(
            test, validated["topic_id"], workspace_id
        )
        row.snapshot_question_text = validated["body"]
        row.snapshot_explanation = validated["explanation"]
        row.snapshot_type_code = validated["type_code"]
        row.snapshot_difficulty = validated["difficulty"]
        row.snapshot_topic_id = topic_id
        row.snapshot_topic_name = topic_name
        row.points = validated["points"]
        row.snapshot_points = validated["points"]
        row.snapshot_choices_json = json.dumps(validated["choices"])
        db.session.commit()
        return self.serialize_test_question(row)

    def delete_test_question(
        self,
        *,
        test_id: int,
        test_question_id: int,
        workspace_id: int,
        actor_membership,
    ) -> None:
        test = self._resolve_draft_test(test_id, workspace_id, actor_membership)
        self._ensure_no_attempts_on_test(test.id)
        row = self._get_test_question_or_404(test.id, test_question_id)
        self.test_questions.delete(row)
        db.session.commit()

    def publish_now(self, *, test_id: int, workspace_id: int, actor_membership) -> Test:
        test = self._resolve_test_access(test_id, workspace_id, actor_membership)
        if test.status in (TestStatus.CLOSED.value, TestStatus.ARCHIVED.value):
            raise ValidationError("Closed or archived tests cannot be published")
        test.status = TestStatus.PUBLISHED.value
        test.published_at = datetime.now(timezone.utc)
        test.scheduled_publish_at = None
        db.session.commit()
        return test

    def publish_due_scheduled_tests(self) -> list[int]:
        """Publish all SCHEDULED tests whose scheduled_publish_at is in the past."""
        return self.tests.publish_due_scheduled_tests()

    def schedule_publication(
        self,
        *,
        test_id: int,
        workspace_id: int,
        actor_membership,
        publish_at,
    ) -> Test:
        test = self._resolve_test_access(test_id, workspace_id, actor_membership)
        if test.status in (TestStatus.CLOSED.value, TestStatus.ARCHIVED.value):
            raise ValidationError("Closed or archived tests cannot be scheduled")
        if not publish_at:
            raise ValidationError("publish_at is required")
        now = datetime.now(timezone.utc)
        if publish_at <= now:
            raise ValidationError("publish_at must be in the future")
        test.status = TestStatus.SCHEDULED.value
        test.scheduled_publish_at = publish_at
        db.session.commit()
        return test

    def close_test(self, *, test_id: int, workspace_id: int, actor_membership) -> Test:
        test = self._resolve_test_access(test_id, workspace_id, actor_membership)
        if test.status == TestStatus.ARCHIVED.value:
            raise ValidationError("Archived tests cannot be closed")
        test.status = TestStatus.CLOSED.value
        test.closed_at = datetime.now(timezone.utc)
        db.session.commit()
        return test

    def archive_test(self, *, test_id: int, workspace_id: int, actor_membership) -> Test:
        test = self._resolve_test_access(test_id, workspace_id, actor_membership)
        test.status = TestStatus.ARCHIVED.value
        test.archived_at = datetime.now(timezone.utc)
        db.session.commit()
        return test

    def _resolve_test_access(self, test_id: int, workspace_id: int, actor_membership) -> Test:
        test = self.tests.get_by_id(test_id)
        if not test:
            raise NotFoundError("Test not found")

        if not test.created_by or test.created_by.workspace_id != workspace_id:
            raise NotFoundError("Test not found in this workspace")

        workspace = self.workspaces.get_by_id(workspace_id)
        actor_link = self.subject_memberships.find_active(actor_membership.id, test.subject_id)
        is_creator = test.created_by_membership_id == actor_membership.id
        if is_creator or can_manage_subjects(workspace, actor_membership):
            return test
        if verify_subject_teacher_access(actor_link):
            return test
        raise ForbiddenError("You do not have access to this test")

    def _resolve_draft_test(self, test_id: int, workspace_id: int, actor_membership) -> Test:
        test = self._resolve_test_access(test_id, workspace_id, actor_membership)
        if test.status != TestStatus.DRAFT.value:
            raise ValidationError("Questions can only be modified while test is DRAFT")
        return test

    def _get_test_question_or_404(self, test_id: int, test_question_id: int) -> TestQuestion:
        row = self.test_questions.get_for_test(test_question_id, test_id)
        if not row:
            raise NotFoundError("Test question not found")
        return row

    def _ensure_no_attempts_on_test(self, test_id: int) -> None:
        if self.attempts.list_for_test(test_id):
            raise ValidationError(
                "Cannot modify exam questions after student attempts have been recorded"
            )

    def _merge_test_question_payload(self, row: TestQuestion, patch: dict) -> dict:
        current = {
            "type_code": row.snapshot_type_code,
            "body": row.snapshot_question_text,
            "explanation": row.snapshot_explanation,
            "points": float(row.points) if row.points is not None else 1,
            "difficulty": row.snapshot_difficulty,
            "topic_id": row.snapshot_topic_id,
            "choices": self._load_json(row.snapshot_choices_json) or [],
        }
        merged = {**current, **patch}
        if "choices" not in patch:
            merged["choices"] = current["choices"]
        return merged

    def _resolve_topic_snapshot(
        self, test: Test, topic_id: int | None, workspace_id: int
    ) -> tuple[int | None, str | None]:
        if topic_id is None:
            return None, None
        topic = self.topics.get_in_subject(
            topic_id, subject_id=test.subject_id, workspace_id=workspace_id
        )
        if not topic:
            raise ValidationError(
                f"topic_id {topic_id} does not belong to the exam subject"
            )
        return topic.id, topic.name

    def _snapshot_from_source_question(self, question) -> dict:
        return {
            "snapshot_question_text": question.question_text,
            "snapshot_explanation": question.explanation,
            "snapshot_type_code": (
                (question.question_type.code or question.question_type.name).upper()
                if question.question_type
                else "UNKNOWN"
            ),
            "snapshot_topic_id": question.topic_id,
            "snapshot_topic_name": question.topic.name if question.topic else None,
            "snapshot_difficulty": question.difficulty,
            "snapshot_points": question.points,
            "snapshot_choices_json": json.dumps(
                [
                    {
                        "id": choice.id,
                        "body": choice.body,
                        "is_correct": bool(choice.is_correct),
                        "order_index": choice.order_index,
                    }
                    for choice in question.choices
                ]
            ),
        }

    def serialize_test(self, test: Test) -> dict:
        return {
            "test_id": test.id,
            "name": test.name,
            "slug": test.slug,
            "description": test.description,
            "grading_mode": test.grading_mode,
            "subject_id": test.subject_id,
            "subject_name": test.subject.name if test.subject else None,
            "status": test.status,
            "total_score": float(test.total_score) if test.total_score is not None else None,
            "passing_score": float(test.passing_score) if test.passing_score is not None else None,
            "auto_distribute_scores": bool(test.auto_distribute_scores),
            "scoring_config": self._load_json(test.scoring_config),
            "settings_config": self._load_json(test.settings_config),
            "availability_time_mode": test.availability_time_mode,
            "starts_at": test.starts_at.isoformat() if test.starts_at else None,
            "duration_minutes": test.duration_minutes,
            "entry_window_minutes": test.entry_window_minutes,
            "created_by_membership_id": test.created_by_membership_id,
            "published_at": test.published_at.isoformat() if test.published_at else None,
            "scheduled_publish_at": test.scheduled_publish_at.isoformat()
            if test.scheduled_publish_at
            else None,
            "closed_at": test.closed_at.isoformat() if test.closed_at else None,
            "archived_at": test.archived_at.isoformat() if test.archived_at else None,
            "created_at": test.created_at.isoformat() if test.created_at else None,
            "updated_at": test.updated_at.isoformat() if test.updated_at else None,
        }

    def serialize_test_question(self, row: TestQuestion) -> dict:
        return {
            "id": row.id,
            "test_id": row.test_id,
            "question_id": row.question_id,
            "source_type": row.source_type,
            "source_bank_id": row.source_bank_id,
            "points": float(row.points) if row.points is not None else None,
            "status": row.status,
            "snapshot_question_text": row.snapshot_question_text,
            "snapshot_explanation": row.snapshot_explanation,
            "snapshot_type_code": row.snapshot_type_code,
            "snapshot_topic_id": row.snapshot_topic_id,
            "snapshot_topic_name": row.snapshot_topic_name,
            "snapshot_difficulty": row.snapshot_difficulty,
            "snapshot_points": float(row.snapshot_points) if row.snapshot_points is not None else None,
            "snapshot_choices": self._load_json(row.snapshot_choices_json) or [],
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def _resolve_slug(self, maybe_slug: str | None, name: str) -> str:
        base = (maybe_slug or name or "").strip().lower()
        base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
        if not base:
            base = "test"
        return base

    def _resolve_unique_slug(self, base_slug: str) -> str:
        """
        Create a unique slug by appending -2, -3, ... when needed.
        This avoids collisions for non-latin titles that normalize to the same fallback.
        """
        candidate = base_slug
        counter = 2
        while self.tests.find_by_slug(candidate):
            candidate = f"{base_slug}-{counter}"
            counter += 1
        return candidate

    def _create_snapshot_row_from_payload(
        self, *, test_id: int, payload: dict, source_type: str
    ) -> TestQuestion:
        validated = self._validate_and_normalize_payload(payload)
        row = TestQuestion(
            test_id=test_id,
            question_id=None,
            kind=source_type,
            source_type=source_type,
            source_bank_id=None,
            points=validated["points"],
            snapshot_question_text=validated["body"],
            snapshot_explanation=validated["explanation"],
            snapshot_type_code=validated["type_code"],
            snapshot_topic_id=validated["topic_id"],
            snapshot_topic_name=None,
            snapshot_difficulty=validated["difficulty"],
            snapshot_points=validated["points"],
            snapshot_choices_json=json.dumps(validated["choices"]),
        )
        self.test_questions.add(row)
        return row

    def _validate_and_normalize_payload(self, payload: dict) -> dict:
        type_code = validate_question_create_payload(
            type_code=payload.get("type_code"),
            choices=payload.get("choices"),
        )
        question_type = self.question_types.find_by_code(type_code)
        if not question_type:
            raise ValidationError(
                f"Question type '{type_code}' is not configured. Run flask seed."
            )

        body = (payload.get("body") or "").strip()
        if not body:
            raise ValidationError("Question body is required")

        points = payload.get("points")
        points_value = Decimal(str(points)) if points is not None else Decimal("1")
        if points_value < 0:
            raise ValidationError("points must be non-negative")

        difficulty = payload.get("difficulty")
        if difficulty is not None:
            difficulty = difficulty.strip().upper()
            if difficulty not in [d.value for d in Difficulty]:
                raise ValidationError("invalid difficulty value")

        topic_id = payload.get("topic_id")
        if topic_id is not None:
            try:
                topic_id = int(topic_id)
            except (TypeError, ValueError):
                raise ValidationError("topic_id must be a valid integer")
            if topic_id <= 0:
                topic_id = None

        choices = payload.get("choices") or []
        return {
            "type_code": type_code,
            "body": body,
            "explanation": (payload.get("explanation") or "").strip() or None,
            "points": points_value,
            "difficulty": difficulty,
            "topic_id": topic_id,
            "choices": [
                {
                    "body": (item.get("body") or "").strip(),
                    "is_correct": bool(item.get("is_correct")),
                    "order_index": item.get("order_index", idx),
                }
                for idx, item in enumerate(choices)
            ],
        }

    def _default_choices_for_type(self, type_code: str) -> list[dict]:
        normalized = (type_code or "").strip().upper()
        if normalized == "TRUE_FALSE":
            return [
                {"body": "True", "is_correct": True, "order_index": 0},
                {"body": "False", "is_correct": False, "order_index": 1},
            ]
        if normalized in ("MCQ", "MULTI_SELECT"):
            return [
                {"body": "Option A", "is_correct": True, "order_index": 0},
                {"body": "Option B", "is_correct": False, "order_index": 1},
            ]
        return []

    def _csv_row_to_question_payload(self, row_index: int, row: dict) -> dict:
        type_code = (row.get("type_code") or "").strip()
        body = (row.get("body") or "").strip()
        if not type_code or not body:
            raise ValidationError(
                f"CSV row {row_index + 1}: type_code and body are required"
            )
        choices_raw = (row.get("choices") or "").strip()
        choices = []
        if choices_raw:
            try:
                choices = json.loads(choices_raw)
            except Exception:
                raise ValidationError(
                    f"CSV row {row_index + 1}: choices must be valid JSON array"
                )
        return {
            "type_code": type_code,
            "body": body,
            "explanation": row.get("explanation"),
            "points": row.get("points") or None,
            "difficulty": row.get("difficulty") or None,
            "topic_id": row.get("topic_id") or None,
            "choices": choices,
        }

    def _to_decimal(self, value, field_name: str):
        if value is None:
            return None
        try:
            parsed = Decimal(str(value))
        except Exception:
            raise ValidationError(f"{field_name} must be numeric")
        if parsed < 0:
            raise ValidationError(f"{field_name} must be non-negative")
        return parsed

    def _dump_json(self, value):
        if value is None:
            return None
        return json.dumps(value)

    def _load_json(self, value):
        if not value:
            return None
        try:
            return json.loads(value)
        except Exception:
            return None
