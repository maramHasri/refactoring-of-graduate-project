from utils.messages import Messages
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from flask import current_app

from models import Membership, Test, TestQuestion, TestStudentAssignment
from models.ai_generation import AIGeneratedQuestion, AIGenerationRequest
from repositories.ai_generation_repository import (
    AIGeneratedQuestionRepository,
    AIGenerationRequestRepository,
)
from repositories.test_assignment_repository import TestStudentAssignmentRepository
from repositories.question_repository import QuestionRepository, QuestionTypeRepository
from repositories.subject_repository import SubjectMembershipRepository, SubjectRepository
from repositories.test_repository import TestQuestionRepository, TestRepository
from repositories.topic_repository import TopicRepository
from repositories.attempt_repository import TestAttemptRepository
from repositories.workspace_repository import WorkspaceRepository
from service.exam_blueprint_service import ExamBlueprintService
from service.exam_csv_import_parser import parse_exam_csv, read_csv_text
from service.ai_question_service import AIQuestionService
from service.email_delivery_service import EmailDeliveryError, EmailDeliveryService
from service.question_bank_service import QuestionBankService
from service.question_image_service import QuestionImageService
from service.test_schedule_conflict_service import TestScheduleConflictService
from service.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from utils.academic_rbac import can_manage_subjects, verify_subject_teacher_access
from utils.app_timezone import ensure_local_aware, format_local_datetime, local_timezone_now
from utils.db import db
from utils.enums import (
    AIGeneratedQuestionStatus,
    AIGenerationRequestStatus,
    AvailabilityTimeMode,
    DEFAULT_OFFLINE_GRACE_MINUTES,
    Difficulty,
    MembershipRole,
    MembershipStatus,
    SubjectRole,
    TestQuestionSourceType,
    TestStatus,
)
from utils.question_type_validation import validate_question_create_payload
from utils.test_scoring import distribute_points, sum_points


logger = logging.getLogger(__name__)


class TestService:
    def __init__(self):
        self.tests = TestRepository()
        self.test_questions = TestQuestionRepository()
        self.attempts = TestAttemptRepository()
        self.questions = QuestionRepository()
        self.test_assignments = TestStudentAssignmentRepository()
        self.question_types = QuestionTypeRepository()
        self.subjects = SubjectRepository()
        self.subject_memberships = SubjectMembershipRepository()
        self.topics = TopicRepository()
        self.workspaces = WorkspaceRepository()
        self.bank_service = QuestionBankService()
        self.images = QuestionImageService()
        self.email_delivery = EmailDeliveryService()
        self.ai_questions = AIQuestionService()
        self.exam_blueprint = ExamBlueprintService()
        self.schedule_conflicts = TestScheduleConflictService()
        self.ai_generation_requests = AIGenerationRequestRepository()
        self.ai_generated_questions = AIGeneratedQuestionRepository()

    def assign_students_to_test(
        self,
        *,
        test_id: int,
        workspace_id: int,
        actor_membership,
        student_membership_ids: list[int],
    ) -> int:
        test = self._resolve_test_access(test_id, workspace_id, actor_membership)
        unique_ids: list[int] = []
        seen: set[int] = set()
        for membership_id in student_membership_ids:
            student_id = int(membership_id)
            if student_id in seen:
                continue
            seen.add(student_id)
            unique_ids.append(student_id)

        self._validate_students_belong_to_test_subject(
            workspace_id=workspace_id,
            test=test,
            student_membership_ids=unique_ids,
        )

        created_count = 0
        for student_membership_id in unique_ids:
            row = self.test_assignments.find(
                test_id=test.id,
                student_membership_id=student_membership_id,
            )
            if row:
                row.assigned_by_membership_id = actor_membership.id
                continue
            self.test_assignments.add(
                TestStudentAssignment(
                    test_id=test.id,
                    student_membership_id=student_membership_id,
                    assigned_by_membership_id=actor_membership.id,
                )
            )
            created_count += 1

        all_student_ids = list(
            set(self.test_assignments.list_student_membership_ids_for_test(test.id))
            | set(unique_ids)
        )
        self.schedule_conflicts.ensure_no_schedule_conflicts(
            test=test,
            workspace_id=workspace_id,
            student_membership_ids=all_student_ids,
        )

        db.session.commit()
        logger.info(
            "event=student_assigned test_id=%s actor_membership_id=%s requested=%s created=%s result=success",
            test.id,
            actor_membership.id,
            len(unique_ids),
            created_count,
        )
        return len(unique_ids)

    def list_assigned_students(
        self,
        *,
        test_id: int,
        workspace_id: int,
        actor_membership,
    ) -> list[dict]:
        test = self._resolve_test_access(test_id, workspace_id, actor_membership)
        rows = self.test_assignments.list_for_test_with_student_profile(test.id)
        return [
            {
                "assignment_id": item["assignment"].id,
                "membership_id": item["membership"].id,
                "user_id": item["user"].id,
                "full_name": item["user"].full_name,
                "email": item["user"].email,
                "invite_status": item["assignment"].invite_status,
                "invite_sent_at": format_local_datetime(item["assignment"].invite_sent_at),
            }
            for item in rows
        ]

    def remove_assigned_student(
        self,
        *,
        test_id: int,
        workspace_id: int,
        actor_membership,
        student_membership_id: int,
    ) -> None:
        test = self._resolve_test_access(test_id, workspace_id, actor_membership)
        row = self.test_assignments.find(
            test_id=test.id,
            student_membership_id=student_membership_id,
        )
        if not row:
            raise NotFoundError(Messages.STUDENT_ASSIGNMENT_NOT_FOUND)
        self.test_assignments.delete(row)
        db.session.commit()
        logger.info(
            "event=student_removed test_id=%s actor_membership_id=%s student_membership_id=%s result=success",
            test.id,
            actor_membership.id,
            student_membership_id,
        )

    def create_test(self, *, workspace_id: int, actor_membership, data: dict) -> Test:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError(Messages.WORKSPACE_NOT_FOUND)

        subject = self.subjects.get_active_by_id(data["subject_id"], workspace_id)
        if not subject:
            raise NotFoundError(Messages.SUBJECT_NOT_FOUND)

        actor_link = self.subject_memberships.find_active(
            actor_membership.id, subject.id
        )
        if not can_manage_subjects(workspace, actor_membership) and not verify_subject_teacher_access(actor_link):
            raise ForbiddenError(Messages.YOU_ARE_NOT_ALLOWED_TO_CREATE_EXAMS_FOR_THIS_SUBJECT)

        base_slug = self._resolve_slug(None, data["name"])
        slug = self._resolve_unique_slug(base_slug)

        total_score_input = self._to_decimal(data.get("total_score"), "total_score")
        passing_score = self._to_decimal(data.get("passing_score"), "passing_score")
        auto_distribute = bool(data.get("auto_distribute_scores", False))

        target_total_score = None
        calculated_total = Decimal("0")
        if auto_distribute:
            if total_score_input is None:
                raise ValidationError(
                    Messages.TARGET_TOTAL_SCORE_IS_REQUIRED_WHEN_AUTO_DISTRIBUTE_IS_ENABLED
                )
            target_total_score = total_score_input
            if (
                passing_score is not None
                and target_total_score is not None
                and passing_score > target_total_score
            ):
                raise ValidationError(Messages.PASSING_SCORE_CANNOT_BE_GREATER_THAN_TOTAL_SCORE)
        else:
            # Soft check against the UI-intended scale before questions exist.
            if (
                total_score_input is not None
                and passing_score is not None
                and passing_score > total_score_input
            ):
                raise ValidationError(Messages.PASSING_SCORE_CANNOT_BE_GREATER_THAN_TOTAL_SCORE)

        mode = (data.get("availability_time_mode") or "").upper() or None
        if mode == AvailabilityTimeMode.SURVEY.value:
            closed_at = data.get("closed_at")
            if closed_at is None:
                raise ValidationError(Messages.SURVEY_CLOSED_AT_IS_REQUIRED)
            closed_at = ensure_local_aware(closed_at)
            if closed_at <= local_timezone_now():
                raise ValidationError(Messages.SURVEY_CLOSED_AT_MUST_BE_IN_THE_FUTURE)
            if data.get("duration_minutes") is not None:
                raise ValidationError(Messages.SURVEY_DURATION_IS_NOT_ALLOWED)
            duration_minutes = None
        else:
            closed_at = None
            # Exam default duration when omitted (Survey never reaches here).
            duration_minutes = data.get("duration_minutes")
            if duration_minutes is None:
                duration_minutes = 30

        test = Test(
            name=data["name"].strip(),
            slug=slug,
            description=(data.get("description") or "").strip() or None,
            subject_id=subject.id,
            total_score=calculated_total,
            target_total_score=target_total_score,
            passing_score=passing_score,
            auto_distribute_scores=auto_distribute,
            created_by_membership_id=actor_membership.id,
            status=TestStatus.DRAFT.value,
            availability_time_mode=mode,
            duration_minutes=duration_minutes,
            closed_at=closed_at,
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

    def delete_test(
        self,
        *,
        test_id: int,
        workspace_id: int,
        actor_membership,
    ) -> None:
        test = self._resolve_test_for_creator(test_id, workspace_id, actor_membership)
        self._ensure_no_attempts_on_test(test.id)
        self.tests.delete(test)
        db.session.commit()
        logger.info(
            "event=test_deleted test_id=%s actor_membership_id=%s result=success",
            test_id,
            actor_membership.id,
        )

    def update_test(self, *, test_id: int, workspace_id: int, actor_membership, data: dict) -> Test:
        test = self._resolve_test_access(test_id, workspace_id, actor_membership)
        self._ensure_test_editable_for_settings_update(test)

        if "name" in data and data["name"]:
            test.name = data["name"].strip()
        if "slug" in data:
            raw_slug = (data.get("slug") or "").strip()
            if not raw_slug:
                raise ValidationError(Messages.SLUG_CANNOT_BE_EMPTY)
            slug = self._normalize_slug_value(raw_slug)
            if not slug:
                raise ValidationError(Messages.SLUG_MUST_CONTAIN_AT_LEAST_ONE_LATIN_LETTER_OR_DIGIT_A_Z_0_9)
            if slug != test.slug:
                existing = self.tests.find_by_slug(slug)
                if existing:
                    raise ConflictError(Messages.TEST_SLUG_SLUG_IS_ALREADY_USED_BY_TEST_ID_EXISTING_ID.format(slug=slug, existing_id=existing.id))
                test.slug = slug
        if "description" in data:
            test.description = (data.get("description") or "").strip() or None

        scoring_touched = any(
            key in data
            for key in ("total_score", "passing_score", "auto_distribute_scores")
        )
        if scoring_touched:
            self._apply_test_scoring_update(test, data)

        if "availability_time_mode" in data:
            test.availability_time_mode = data.get("availability_time_mode")
        if "starts_at" in data:
            value = data.get("starts_at")
            test.starts_at = ensure_local_aware(value) if value is not None else None
        if "duration_minutes" in data:
            test.duration_minutes = data.get("duration_minutes")
        if "entry_window_minutes" in data:
            test.entry_window_minutes = data.get("entry_window_minutes")
        if "closed_at" in data:
            value = data.get("closed_at")
            test.closed_at = ensure_local_aware(value) if value is not None else None

        self._validate_test_timing_rules(test)

        if "settings_config" in data:
            test.settings_config = self._normalize_settings_config(
                data.get("settings_config"),
                test=test,
            )

        self.schedule_conflicts.ensure_no_schedule_conflicts(
            test=test,
            workspace_id=workspace_id,
        )

        db.session.commit()
        return test

    def redistribute_test_points(
        self,
        test: Test,
        target_total_score: Decimal,
        *,
        lock_attempts: bool = True,
    ) -> list[TestQuestion]:
        """Distribute ``target_total_score`` across active test questions."""
        if lock_attempts:
            self._ensure_no_attempts_for_scoring(test.id)
        rows = self.test_questions.list_active_for_test(test.id)
        if not rows:
            test.total_score = Decimal("0")
            return []
        if target_total_score is None:
            raise ValidationError(
                Messages.TARGET_TOTAL_SCORE_IS_REQUIRED_WHEN_AUTO_DISTRIBUTE_IS_ENABLED
            )
        if target_total_score <= 0:
            raise ValidationError(
                Messages.TARGET_TOTAL_SCORE_MUST_BE_GREATER_THAN_ZERO_WHEN_DISTRIBUTING
            )

        points_list = distribute_points(target_total_score, len(rows))
        for row, points in zip(rows, points_list):
            row.points = points
            row.snapshot_points = points
        test.total_score = sum_points(points_list)
        return rows

    def _apply_test_scoring_update(self, test: Test, data: dict) -> None:
        will_auto = (
            bool(data["auto_distribute_scores"])
            if "auto_distribute_scores" in data
            else bool(test.auto_distribute_scores)
        )
        total_input = (
            self._to_decimal(data.get("total_score"), "total_score")
            if "total_score" in data
            else None
        )

        if not will_auto and "total_score" in data:
            raise ValidationError(
                Messages.TOTAL_SCORE_IS_CALCULATED_FROM_QUESTION_POINTS_WHEN_AUTO_DISTRIBUTE_IS_DISABLED
            )

        structure_change = (
            "auto_distribute_scores" in data
            or (will_auto and "total_score" in data)
        )
        if structure_change:
            self._ensure_no_attempts_for_scoring(test.id)

            if "auto_distribute_scores" in data:
                test.auto_distribute_scores = will_auto

            if will_auto:
                if "total_score" in data:
                    if total_input is None:
                        raise ValidationError(
                            Messages.TARGET_TOTAL_SCORE_IS_REQUIRED_WHEN_AUTO_DISTRIBUTE_IS_ENABLED
                        )
                    test.target_total_score = total_input
                elif test.target_total_score is None:
                    raise ValidationError(
                        Messages.TARGET_TOTAL_SCORE_IS_REQUIRED_WHEN_AUTO_DISTRIBUTE_IS_ENABLED
                    )
                self._refresh_test_scoring(test, lock_attempts=False)
            else:
                test.target_total_score = None
                self._sync_total_score_from_questions(test)

        if "passing_score" in data:
            test.passing_score = self._to_decimal(
                data.get("passing_score"), "passing_score"
            )
        self._validate_passing_score(test)

    def _refresh_test_scoring(
        self, test: Test, *, lock_attempts: bool = True
    ) -> None:
        """Recompute points/total after question or target changes."""
        if test.auto_distribute_scores:
            target = test.target_total_score
            if target is None:
                raise ValidationError(
                    Messages.TARGET_TOTAL_SCORE_IS_REQUIRED_WHEN_AUTO_DISTRIBUTE_IS_ENABLED
                )
            self.redistribute_test_points(
                test,
                Decimal(str(target)),
                lock_attempts=lock_attempts,
            )
        else:
            if lock_attempts:
                self._ensure_no_attempts_for_scoring(test.id)
            self._sync_total_score_from_questions(test)

        self._validate_passing_score(test)

    def _sync_total_score_from_questions(self, test: Test) -> None:
        rows = self.test_questions.list_active_for_test(test.id)
        test.total_score = sum_points(row.points for row in rows)

    def _validate_passing_score(self, test: Test) -> None:
        if test.passing_score is None:
            return
        rows = self.test_questions.list_active_for_test(test.id)
        if rows:
            maximum = sum_points(row.points for row in rows)
            if test.passing_score > maximum:
                raise ValidationError(
                    Messages.PASSING_SCORE_CANNOT_BE_GREATER_THAN_TOTAL_SCORE
                )
            return
        # No questions yet: when auto-distribute is on, compare against target.
        if test.auto_distribute_scores and test.target_total_score is not None:
            if test.passing_score > test.target_total_score:
                raise ValidationError(
                    Messages.PASSING_SCORE_CANNOT_BE_GREATER_THAN_TOTAL_SCORE
                )

    def _ensure_no_attempts_for_scoring(self, test_id: int) -> None:
        if self.attempts.list_for_test(test_id):
            raise ConflictError(
                Messages.CANNOT_CHANGE_TEST_SCORING_AFTER_STUDENT_ATTEMPTS_HAVE_BEEN_RECORDED
            )

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
            raise ValidationError(Messages.QUESTIONS_CAN_ONLY_BE_ADDED_WHILE_TEST_IS_DRAFT)
        if not question_ids:
            raise ValidationError(Messages.QUESTION_IDS_MUST_CONTAIN_AT_LEAST_ONE_ITEM)

        created = []
        for question_id in question_ids:
            question = self.questions.get_by_id(question_id)
            if not question or not question.bank or question.bank.workspace_id != workspace_id:
                raise NotFoundError(Messages.QUESTION_QUESTION_ID_NOT_FOUND_IN_WORKSPACE.format(question_id=question_id))
            if question.bank.subject_id != test.subject_id:
                raise ValidationError(Messages.QUESTION_QUESTION_ID_DOES_NOT_BELONG_TO_THE_TEST_SUBJECT.format(question_id=question_id))
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
                snapshot_image_path=snapshot["snapshot_image_path"],
                snapshot_type_code=snapshot["snapshot_type_code"],
                snapshot_topic_id=snapshot["snapshot_topic_id"],
                snapshot_topic_name=snapshot["snapshot_topic_name"],
                snapshot_difficulty=snapshot["snapshot_difficulty"],
                snapshot_points=snapshot["snapshot_points"],
                snapshot_choices_json=snapshot["snapshot_choices_json"],
            )
            self.test_questions.add(row)
            created.append(row)

        self._refresh_test_scoring(test)
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
                test=test,
                workspace_id=workspace_id,
                payload=payload,
                source_type=TestQuestionSourceType.MANUAL.value,
            )
            for payload in questions
        ]
        self._refresh_test_scoring(test)
        db.session.commit()
        return [self.serialize_test_question(row) for row in created]

    def import_questions_from_csv(
        self,
        *,
        test_id: int,
        workspace_id: int,
        actor_membership,
        file_storage,
    ) -> dict:
        test = self._resolve_draft_test(test_id, workspace_id, actor_membership)
        if not file_storage:
            raise ValidationError(Messages.CSV_FILE_IS_REQUIRED)

        text = read_csv_text(file_storage.read())
        logger.info(
            "[CSV Import] File received for test_id=%s actor_membership_id=%s",
            test.id,
            actor_membership.id,
        )

        payloads, failed_rows = parse_exam_csv(
            text,
            subject_id=test.subject_id,
            workspace_id=workspace_id,
        )

        for failure in failed_rows:
            logger.warning(
                "[CSV Import] Row %s skipped: %s",
                failure["row"],
                failure["error"],
            )

        created = []
        for payload in payloads:
            row = self._create_snapshot_row_from_payload(
                test=test,
                workspace_id=workspace_id,
                payload=payload,
                source_type=TestQuestionSourceType.IMPORT.value,
            )
            created.append(row)
            logger.info(
                "[CSV Import] Question created test_id=%s test_question_id=%s type=%s",
                test.id,
                row.id,
                row.snapshot_type_code,
            )

        self._refresh_test_scoring(test)
        db.session.commit()

        imported_count = len(created)
        failed_count = len(failed_rows)
        logger.info(
            "[CSV Import] Finished test_id=%s imported=%s failed=%s",
            test.id,
            imported_count,
            failed_count,
        )

        result = {
            "message": Messages.CSV_QUESTIONS_IMPORTED,
            "count": imported_count,
            "questions": [self.serialize_test_question(row) for row in created],
        }
        if failed_rows:
            result["failed_rows"] = failed_rows
            result["failed_count"] = failed_count
            result["message"] = (
                f"CSV import completed with {imported_count} imported and "
                f"{failed_count} failed row(s)"
            )
        return result

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
            raise ValidationError(Messages.SELECTED_BANK_DOES_NOT_BELONG_TO_EXAM_SUBJECT)

        created = []
        for question_id in question_ids:
            question = self.questions.get_active_in_bank(question_id, bank.id)
            if not question:
                raise NotFoundError(Messages.QUESTION_QUESTION_ID_NOT_FOUND_IN_SELECTED_BANK.format(question_id=question_id))
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
                snapshot_image_path=snapshot["snapshot_image_path"],
                snapshot_type_code=snapshot["snapshot_type_code"],
                snapshot_topic_id=snapshot["snapshot_topic_id"],
                snapshot_topic_name=snapshot["snapshot_topic_name"],
                snapshot_difficulty=snapshot["snapshot_difficulty"],
                snapshot_points=snapshot["snapshot_points"],
                snapshot_choices_json=snapshot["snapshot_choices_json"],
            )
            self.test_questions.add(row)
            created.append(row)

        self._refresh_test_scoring(test)
        db.session.commit()
        return [self.serialize_test_question(row) for row in created]

    def generate_exam_from_blueprint(
        self,
        *,
        test_id: int,
        workspace_id: int,
        actor_membership,
        banks_blueprint: list[dict],
    ) -> dict:
        test = self._resolve_draft_test(test_id, workspace_id, actor_membership)
        plans = self.exam_blueprint.build_plan(
            banks_blueprint=banks_blueprint,
            test_subject_id=test.subject_id,
            workspace_id=workspace_id,
            actor_membership=actor_membership,
        )
        selected_questions, summary = self.exam_blueprint.select_questions(plans)

        created = []
        for question in selected_questions:
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
                snapshot_image_path=snapshot["snapshot_image_path"],
                snapshot_type_code=snapshot["snapshot_type_code"],
                snapshot_topic_id=snapshot["snapshot_topic_id"],
                snapshot_topic_name=snapshot["snapshot_topic_name"],
                snapshot_difficulty=snapshot["snapshot_difficulty"],
                snapshot_points=snapshot["snapshot_points"],
                snapshot_choices_json=snapshot["snapshot_choices_json"],
            )
            self.test_questions.add(row)
            created.append(row)

        self._refresh_test_scoring(test)
        db.session.commit()
        serialized = [self.serialize_test_question(row) for row in created]
        return {
            "message": Messages.BLUEPRINT_GENERATED_SUCCESSFULLY,
            "count": len(serialized),
            "summary": summary,
            "questions": serialized,
        }

    def add_ai_generated_questions(
        self,
        *,
        test_id: int,
        workspace_id: int,
        actor_membership,
        topic_ids: list[int],
        count: int,
        type_code: str,
        difficulty: str | None = None,
        learning_objectives: list[str] | None = None,
        additional_instructions: str | None = None,
    ) -> dict:
        test = self._resolve_draft_test(test_id, workspace_id, actor_membership)
        if not test.subject:
            raise ValidationError(Messages.TEST_MUST_HAVE_A_SUBJECT_FOR_AI_QUESTION_GENERATION)

        subject_name = test.subject.name
        topic_rows = self._resolve_topics_for_test(
            test=test,
            workspace_id=workspace_id,
            topic_ids=topic_ids,
        )
        topic_names = [topic.name for topic in topic_rows]
        learning_objectives = learning_objectives or []

        ai_request = self.ai_questions.build_request_body(
            subject_name=subject_name,
            exam_name=test.name,
            count=count,
            type_code=type_code,
            difficulty=difficulty,
            topics=topic_names,
            learning_objectives=learning_objectives,
            additional_instructions=additional_instructions,
        )
        request_row = AIGenerationRequest(
            test_id=test.id,
            created_by_membership_id=actor_membership.id,
            topic_ids_json=json.dumps([topic.id for topic in topic_rows]),
            learning_objectives_json=json.dumps(learning_objectives),
            count=count,
            difficulty=difficulty,
            type_code=type_code,
            additional_instructions=(additional_instructions or "").strip() or None,
            status=AIGenerationRequestStatus.PENDING.value,
        )
        self.ai_generation_requests.add(request_row)
        db.session.flush()

        try:
            payloads, model_name = self.ai_questions.generate_questions(
                request_body=ai_request
            )
            created: list[AIGeneratedQuestion] = []
            for idx, payload in enumerate(payloads):
                selected_topic = topic_rows[idx % len(topic_rows)]
                normalized = self._validate_and_normalize_payload(
                    {
                        **payload,
                        "topic_id": selected_topic.id,
                    }
                )
                row = AIGeneratedQuestion(
                    generation_request_id=request_row.id,
                    question_text=normalized["body"],
                    type_code=normalized["type_code"],
                    options_json=json.dumps(normalized["choices"]),
                    correct_answer_json=json.dumps(
                        self._extract_correct_answer(normalized["choices"])
                    ),
                    explanation=normalized["explanation"],
                    difficulty=normalized["difficulty"],
                    topic_id=selected_topic.id,
                    topic_name=selected_topic.name,
                    points=normalized["points"],
                    status=AIGeneratedQuestionStatus.PENDING_REVIEW.value,
                )
                self.ai_generated_questions.add(row)
                created.append(row)
            request_row.status = AIGenerationRequestStatus.COMPLETED.value
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            request_row = AIGenerationRequest(
                test_id=test.id,
                created_by_membership_id=actor_membership.id,
                topic_ids_json=json.dumps([topic.id for topic in topic_rows]),
                learning_objectives_json=json.dumps(learning_objectives),
                count=count,
                difficulty=difficulty,
                type_code=type_code,
                additional_instructions=(additional_instructions or "").strip() or None,
                status=AIGenerationRequestStatus.FAILED.value,
                error_message=str(exc),
            )
            self.ai_generation_requests.add(request_row)
            db.session.commit()
            raise

        return {
            "generation_request_id": request_row.id,
            "generation_status": request_row.status,
            "ai_model": model_name,
            "subject_name": subject_name,
            "count": len(created),
            "generated_questions": [
                self.serialize_ai_generated_question(row) for row in created
            ],
        }

    def get_ai_generation_request(
        self,
        *,
        request_id: int,
        workspace_id: int,
        actor_membership,
    ) -> dict:
        request_row = self._get_ai_generation_request_or_404(request_id)
        self._ensure_can_manage_ai_request(
            request_row=request_row,
            workspace_id=workspace_id,
            actor_membership=actor_membership,
        )
        questions = self.ai_generation_requests.list_questions(request_id)
        return {
            "request": self.serialize_ai_generation_request(request_row),
            "generated_questions": [
                self.serialize_ai_generated_question(row) for row in questions
            ],
            "count": len(questions),
        }

    def update_ai_generated_question(
        self,
        *,
        generated_question_id: int,
        workspace_id: int,
        actor_membership,
        data: dict,
    ) -> dict:
        row = self._get_ai_generated_question_or_404(generated_question_id)
        request_row = self._get_ai_generation_request_or_404(row.generation_request_id)
        self._ensure_can_manage_ai_request(
            request_row=request_row,
            workspace_id=workspace_id,
            actor_membership=actor_membership,
        )
        if row.status != AIGeneratedQuestionStatus.PENDING_REVIEW.value:
            raise ValidationError(Messages.ONLY_PENDING_REVIEW_AI_QUESTIONS_CAN_BE_EDITED)

        payload = {
            "type_code": data.get("type_code", row.type_code),
            "body": data.get("question_text", row.question_text),
            "explanation": data.get("explanation", row.explanation),
            "points": data.get("points", float(row.points) if row.points is not None else 1),
            "difficulty": data.get("difficulty", row.difficulty),
            "topic_id": data.get("topic_id", row.topic_id),
            "choices": data.get("options", self._load_json(row.options_json) or []),
        }
        normalized = self._validate_and_normalize_payload(payload)
        test = self.tests.get_by_id(request_row.test_id)
        topic_id, topic_name = self._resolve_topic_snapshot(test, normalized["topic_id"], workspace_id)

        row.question_text = normalized["body"]
        row.type_code = normalized["type_code"]
        row.options_json = json.dumps(normalized["choices"])
        row.correct_answer_json = json.dumps(
            self._extract_correct_answer(normalized["choices"])
        )
        row.explanation = normalized["explanation"]
        row.difficulty = normalized["difficulty"]
        row.points = normalized["points"]
        row.topic_id = topic_id
        row.topic_name = topic_name
        db.session.commit()
        return self.serialize_ai_generated_question(row)

    def delete_ai_generated_question(
        self,
        *,
        generated_question_id: int,
        workspace_id: int,
        actor_membership,
    ) -> None:
        row = self._get_ai_generated_question_or_404(generated_question_id)
        request_row = self._get_ai_generation_request_or_404(row.generation_request_id)
        self._ensure_can_manage_ai_request(
            request_row=request_row,
            workspace_id=workspace_id,
            actor_membership=actor_membership,
        )
        db.session.delete(row)
        db.session.commit()

    def import_ai_generated_questions(
        self,
        *,
        test_id: int,
        request_id: int,
        question_ids: list[int],
        workspace_id: int,
        actor_membership,
    ) -> dict:
        test = self._resolve_draft_test(test_id, workspace_id, actor_membership)
        request_row = self._get_ai_generation_request_or_404(request_id)
        self._ensure_can_manage_ai_request(
            request_row=request_row,
            workspace_id=workspace_id,
            actor_membership=actor_membership,
        )
        if request_row.test_id != test.id:
            raise ValidationError(Messages.REQUEST_ID_DOES_NOT_BELONG_TO_THIS_TEST)
        if request_row.status != AIGenerationRequestStatus.COMPLETED.value:
            raise ValidationError(Messages.ONLY_COMPLETED_GENERATION_REQUESTS_CAN_BE_IMPORTED)
        if not question_ids:
            raise ValidationError(Messages.QUESTION_IDS_MUST_CONTAIN_AT_LEAST_ONE_ID)

        rows = self.ai_generated_questions.list_by_ids_for_request(request_id, question_ids)
        if len(rows) != len(set(question_ids)):
            raise ValidationError(Messages.SOME_QUESTION_IDS_DO_NOT_BELONG_TO_THE_GENERATION_REQUEST)

        created = []
        try:
            for row in rows:
                if row.status != AIGeneratedQuestionStatus.PENDING_REVIEW.value:
                    raise ValidationError(Messages.AI_QUESTION_ALREADY_IMPORTED.format(question_id=row.id))
                payload = {
                    "type_code": row.type_code,
                    "body": row.question_text,
                    "explanation": row.explanation,
                    "points": float(row.points) if row.points is not None else 1,
                    "difficulty": row.difficulty,
                    "topic_id": row.topic_id,
                    "choices": self._load_json(row.options_json) or [],
                }
                created_row = self._create_snapshot_row_from_payload(
                    test=test,
                    workspace_id=workspace_id,
                    payload=payload,
                    source_type=TestQuestionSourceType.AI.value,
                )
                row.status = AIGeneratedQuestionStatus.IMPORTED.value
                created.append(created_row)

            self._refresh_test_scoring(test)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        return {
            "message": Messages.AI_QUESTIONS_IMPORTED_INTO_TEST,
            "count": len(created),
            "questions": [self.serialize_test_question(row) for row in created],
        }

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
        if "points" in data and test.auto_distribute_scores:
            raise ValidationError(
                Messages.MANUAL_QUESTION_POINTS_NOT_ALLOWED_WHILE_AUTO_DISTRIBUTE_IS_ENABLED
            )
        row = self._get_test_question_or_404(test.id, test_question_id)
        merged = self._merge_test_question_payload(row, data)
        validated = self._validate_and_normalize_payload(merged)
        topic_id, topic_name = self._resolve_topic_snapshot(
            test, validated["topic_id"], workspace_id
        )
        row.snapshot_question_text = validated["body"]
        if data.get("remove_image"):
            self.images.delete_if_local(row.snapshot_image_path)
            row.snapshot_image_path = None
        elif "image_path" in data:
            new_path = (data.get("image_path") or "").strip() or None
            if row.snapshot_image_path and new_path != row.snapshot_image_path:
                self.images.delete_if_local(row.snapshot_image_path)
            row.snapshot_image_path = new_path
        else:
            row.snapshot_image_path = validated.get("image_path")
        row.snapshot_explanation = validated["explanation"]
        row.snapshot_type_code = validated["type_code"]
        row.snapshot_difficulty = validated["difficulty"]
        row.snapshot_topic_id = topic_id
        row.snapshot_topic_name = topic_name
        if "points" in data:
            row.points = validated["points"]
            row.snapshot_points = validated["points"]
        row.snapshot_choices_json = json.dumps(validated["choices"])
        if "points" in data and not test.auto_distribute_scores:
            self._refresh_test_scoring(test, lock_attempts=False)
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
        self._refresh_test_scoring(test, lock_attempts=False)
        db.session.commit()

    def publish_now(self, *, test_id: int, workspace_id: int, actor_membership) -> Test:
        test = self._resolve_test_access(test_id, workspace_id, actor_membership)
        if test.status in (TestStatus.CLOSED.value, TestStatus.ARCHIVED.value):
            raise ValidationError(Messages.CLOSED_OR_ARCHIVED_TESTS_CANNOT_BE_PUBLISHED)
        if test.auto_distribute_scores:
            if test.target_total_score is None:
                raise ValidationError(
                    Messages.TARGET_TOTAL_SCORE_IS_REQUIRED_WHEN_AUTO_DISTRIBUTE_IS_ENABLED
                )
            self.redistribute_test_points(
                test, Decimal(str(test.target_total_score))
            )
        else:
            self._sync_total_score_from_questions(test)
        self._validate_passing_score(test)
        self.schedule_conflicts.ensure_no_schedule_conflicts(
            test=test,
            workspace_id=workspace_id,
        )
        test.status = TestStatus.PUBLISHED.value
        test.published_at = local_timezone_now()
        test.scheduled_publish_at = None
        db.session.commit()
        logger.info(
            "event=exam_published test_id=%s actor_membership_id=%s result=success",
            test.id,
            actor_membership.id,
        )
        self.dispatch_exam_invitations(test.id)
        return test

    def publish_due_scheduled_tests(self) -> list[int]:
        """Publish all SCHEDULED tests whose scheduled_publish_at is in the past."""
        published_ids = self.tests.publish_due_scheduled_tests()
        for test_id in published_ids:
            logger.info(
                "event=exam_published test_id=%s actor_membership_id=%s reason=scheduled_worker result=success",
                test_id,
                "system",
            )
            self.dispatch_exam_invitations(test_id)
        return published_ids

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
            raise ValidationError(Messages.CLOSED_OR_ARCHIVED_TESTS_CANNOT_BE_SCHEDULED)
        if not publish_at:
            raise ValidationError(Messages.PUBLISH_AT_IS_REQUIRED)
        publish_at = ensure_local_aware(publish_at)
        now = local_timezone_now()
        if publish_at <= now:
            raise ValidationError(Messages.PUBLISH_AT_MUST_BE_IN_THE_FUTURE)
        test.status = TestStatus.SCHEDULED.value
        test.scheduled_publish_at = publish_at
        self.schedule_conflicts.ensure_no_schedule_conflicts(
            test=test,
            workspace_id=workspace_id,
        )
        db.session.commit()
        logger.info(
            "event=exam_scheduled test_id=%s actor_membership_id=%s publish_at=%s result=success",
            test.id,
            actor_membership.id,
            format_local_datetime(publish_at),
        )
        return test

    def close_test(self, *, test_id: int, workspace_id: int, actor_membership) -> Test:
        test = self._resolve_test_access(test_id, workspace_id, actor_membership)
        if test.status == TestStatus.ARCHIVED.value:
            raise ValidationError(Messages.ARCHIVED_TESTS_CANNOT_BE_CLOSED)
        test.status = TestStatus.CLOSED.value
        test.closed_at = local_timezone_now()
        from service.attempt_service import AttemptService

        AttemptService().finalize_in_progress_for_test(test)
        db.session.commit()
        return test

    def archive_test(self, *, test_id: int, workspace_id: int, actor_membership) -> Test:
        test = self._resolve_test_access(test_id, workspace_id, actor_membership)
        test.status = TestStatus.ARCHIVED.value
        test.archived_at = local_timezone_now()
        db.session.commit()
        return test

    def dispatch_exam_invitations(self, test_id: int) -> dict:
        test = self.tests.get_by_id(test_id)
        if not test or test.status != TestStatus.PUBLISHED.value:
            return {"sent": 0, "failed": 0}

        pending = self.test_assignments.list_pending_invites_for_test(test.id)
        if not pending:
            return {"sent": 0, "failed": 0}

        starts_at_text = format_local_datetime(test.starts_at) or "Not set"
        teacher_name = (
            test.created_by.user.full_name
            if test.created_by and test.created_by.user
            else "Teacher"
        )
        subject_name = test.subject.name if test.subject else "Subject"
        exam_link = self._build_exam_link(test.id)
        sent_count = 0
        failed_count = 0

        logger.info(
            "event=invitation_dispatch_started test_id=%s count=%s result=started",
            test.id,
            len(pending),
        )
        for row in pending:
            membership = db.session.get(Membership, row.student_membership_id)
            user = membership.user if membership else None
            if not user or not user.email:
                failed_count += 1
                self.test_assignments.mark_invite_failed(
                    row,
                    error_message="Student email is missing",
                )
                logger.error(
                    "event=invitation_failed test_id=%s student_membership_id=%s reason=missing_email result=failed",
                    test.id,
                    row.student_membership_id,
                )
                continue
            try:
                self.email_delivery.send_exam_invitation_email(
                    to_email=user.email,
                    student_name=user.full_name or "Student",
                    exam_name=test.name,
                    subject_name=subject_name,
                    teacher_name=teacher_name,
                    starts_at_text=starts_at_text,
                    duration_minutes=test.duration_minutes,
                    exam_link=exam_link,
                )
                sent_count += 1
                self.test_assignments.mark_invite_sent(
                    row,
                    sent_at=local_timezone_now(),
                )
                logger.info(
                    "event=invitation_sent test_id=%s student_membership_id=%s email=%s result=success",
                    test.id,
                    row.student_membership_id,
                    user.email,
                )
            except EmailDeliveryError as exc:
                failed_count += 1
                self.test_assignments.mark_invite_failed(
                    row,
                    error_message=str(exc),
                )
                logger.error(
                    "event=invitation_failed test_id=%s student_membership_id=%s reason=%s result=failed",
                    test.id,
                    row.student_membership_id,
                    exc,
                )
        db.session.commit()
        return {"sent": sent_count, "failed": failed_count}

    def _build_exam_link(self, test_id: int) -> str:
        base_url = (
            current_app.config.get("FRONTEND_BASE_URL")
            or current_app.config.get("APP_URL")
            or "http://localhost:5173"
        )
        return f"{base_url.rstrip('/')}/tests/{test_id}"

    def _resolve_test_access(self, test_id: int, workspace_id: int, actor_membership) -> Test:
        test = self.tests.get_by_id(test_id)
        if not test:
            raise NotFoundError(Messages.TEST_NOT_FOUND)

        if not test.created_by or test.created_by.workspace_id != workspace_id:
            raise NotFoundError(Messages.TEST_NOT_FOUND_IN_THIS_WORKSPACE)

        workspace = self.workspaces.get_by_id(workspace_id)
        actor_link = self.subject_memberships.find_active(actor_membership.id, test.subject_id)
        is_creator = test.created_by_membership_id == actor_membership.id
        if is_creator or can_manage_subjects(workspace, actor_membership):
            return test
        if verify_subject_teacher_access(actor_link):
            return test
        raise ForbiddenError(Messages.YOU_DO_NOT_HAVE_ACCESS_TO_THIS_TEST)

    def _resolve_draft_test(self, test_id: int, workspace_id: int, actor_membership) -> Test:
        test = self._resolve_test_access(test_id, workspace_id, actor_membership)
        if test.status != TestStatus.DRAFT.value:
            raise ValidationError(Messages.QUESTIONS_CAN_ONLY_BE_MODIFIED_WHILE_TEST_IS_DRAFT)
        return test

    def _resolve_test_for_creator(
        self, test_id: int, workspace_id: int, actor_membership
    ) -> Test:
        test = self.tests.get_by_id_in_workspace(test_id, workspace_id)
        if not test:
            raise NotFoundError(Messages.TEST_NOT_FOUND_IN_THIS_WORKSPACE)
        if test.created_by_membership_id != actor_membership.id:
            raise ForbiddenError(Messages.ONLY_THE_TEST_CREATOR_CAN_DELETE_THIS_TEST)
        return test

    def _get_test_question_or_404(self, test_id: int, test_question_id: int) -> TestQuestion:
        row = self.test_questions.get_for_test(test_question_id, test_id)
        if not row:
            raise NotFoundError(Messages.TEST_QUESTION_NOT_FOUND)
        return row

    def _ensure_no_attempts_on_test(self, test_id: int) -> None:
        if self.attempts.list_for_test(test_id):
            raise ConflictError(
                Messages.CANNOT_MODIFY_EXAM_QUESTIONS_AFTER_STUDENT_ATTEMPTS_HAVE_BEEN_RECORDED
            )

    def _merge_test_question_payload(self, row: TestQuestion, patch: dict) -> dict:
        current = {
            "type_code": row.snapshot_type_code,
            "body": row.snapshot_question_text,
            "image_path": row.snapshot_image_path,
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
            raise ValidationError(Messages.TOPIC_ID_TOPIC_ID_DOES_NOT_BELONG_TO_THE_EXAM_SUBJECT.format(topic_id=topic_id))
        return topic.id, topic.name

    def _resolve_topics_for_test(
        self, *, test: Test, workspace_id: int, topic_ids: list[int]
    ) -> list:
        if not topic_ids:
            raise ValidationError(Messages.TOPIC_IDS_MUST_CONTAIN_AT_LEAST_ONE_TOPIC)
        unique_topic_ids = []
        seen = set()
        for topic_id in topic_ids:
            tid = int(topic_id)
            if tid <= 0:
                raise ValidationError(Messages.TOPIC_IDS_MUST_CONTAIN_POSITIVE_INTEGERS)
            if tid in seen:
                continue
            seen.add(tid)
            unique_topic_ids.append(tid)

        rows = []
        missing = []
        for topic_id in unique_topic_ids:
            topic = self.topics.get_in_subject(
                topic_id, subject_id=test.subject_id, workspace_id=workspace_id
            )
            if not topic:
                missing.append(topic_id)
                continue
            rows.append(topic)
        if missing:
            raise ValidationError(Messages.TOPIC_ID_S_DO_NOT_BELONG_TO_THE_EXAM_SUBJECT_MISSING.format(missing=missing))
        return rows

    def _snapshot_from_source_question(self, question) -> dict:
        return {
            "snapshot_question_text": question.question_text,
            "snapshot_explanation": question.explanation,
            "snapshot_image_path": question.image_path,
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

    @staticmethod
    def _extract_correct_answer(choices: list[dict]) -> list[int]:
        return [
            int(choice.get("order_index", idx))
            for idx, choice in enumerate(choices)
            if choice.get("is_correct")
        ]

    def _get_ai_generation_request_or_404(
        self, request_id: int
    ) -> AIGenerationRequest:
        row = self.ai_generation_requests.get_by_id(request_id)
        if not row:
            raise NotFoundError(Messages.AI_GENERATION_REQUEST_NOT_FOUND)
        return row

    def _get_ai_generated_question_or_404(
        self, generated_question_id: int
    ) -> AIGeneratedQuestion:
        row = self.ai_generated_questions.get_by_id(generated_question_id)
        if not row:
            raise NotFoundError(Messages.AI_GENERATED_QUESTION_NOT_FOUND)
        return row

    def _ensure_can_manage_ai_request(
        self,
        *,
        request_row: AIGenerationRequest,
        workspace_id: int,
        actor_membership,
    ) -> None:
        test = self.tests.get_by_id(request_row.test_id)
        if not test:
            raise NotFoundError(Messages.TEST_NOT_FOUND)
        self._resolve_test_access(test.id, workspace_id, actor_membership)
        if request_row.created_by_membership_id != actor_membership.id:
            raise ForbiddenError(Messages.YOU_CAN_ONLY_MANAGE_YOUR_OWN_AI_GENERATION_REQUESTS)

    def serialize_ai_generation_request(self, row: AIGenerationRequest) -> dict:
        return {
            "id": row.id,
            "test_id": row.test_id,
            "created_by_membership_id": row.created_by_membership_id,
            "topic_ids": self._load_json(row.topic_ids_json) or [],
            "learning_objectives": self._load_json(row.learning_objectives_json) or [],
            "count": row.count,
            "difficulty": row.difficulty,
            "type_code": row.type_code,
            "additional_instructions": row.additional_instructions,
            "status": row.status,
            "error_message": row.error_message,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def serialize_ai_generated_question(self, row: AIGeneratedQuestion) -> dict:
        return {
            "id": row.id,
            "generation_request_id": row.generation_request_id,
            "question_text": row.question_text,
            "type_code": row.type_code,
            "options": self._load_json(row.options_json) or [],
            "correct_answer": self._load_json(row.correct_answer_json) or [],
            "explanation": row.explanation,
            "difficulty": row.difficulty,
            "topic_id": row.topic_id,
            "topic_name": row.topic_name,
            "points": float(row.points) if row.points is not None else None,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def serialize_test_created(self, test: Test) -> dict:
        """Payload for POST /tests — essential fields only (no lifecycle/config nulls)."""
        return {
            "test_id": test.id,
            "name": test.name,
            "description": test.description,
            "subject_id": test.subject_id,
            "subject_name": test.subject.name if test.subject else None,
            "duration_minutes": test.duration_minutes,
            "total_score": float(test.total_score) if test.total_score is not None else None,
            "target_total_score": float(test.target_total_score)
            if test.target_total_score is not None
            else None,
            "passing_score": float(test.passing_score) if test.passing_score is not None else None,
            "auto_distribute_scores": bool(test.auto_distribute_scores),
            "status": test.status,
            "slug": test.slug,
            "created_at": format_local_datetime(test.created_at),
            "test_link": self._build_exam_link(test.id),
        }

    def serialize_test_updated(self, test: Test) -> dict:
        """PATCH /tests/{id} — full settings without lifecycle close/archive timestamps."""
        payload = self.serialize_test(test)
        for key in ("published_at", "closed_at", "archived_at"):
            payload.pop(key, None)
        return payload

    def serialize_test(self, test: Test) -> dict:
        return {
            "test_id": test.id,
            "name": test.name,
            "slug": test.slug,
            "description": test.description,
            "subject_id": test.subject_id,
            "subject_name": test.subject.name if test.subject else None,
            "status": test.status,
            "total_score": float(test.total_score) if test.total_score is not None else None,
            "target_total_score": float(test.target_total_score)
            if test.target_total_score is not None
            else None,
            "passing_score": float(test.passing_score) if test.passing_score is not None else None,
            "auto_distribute_scores": bool(test.auto_distribute_scores),
            "settings_config": self._load_json(test.settings_config),
            "availability_time_mode": test.availability_time_mode,
            "starts_at": format_local_datetime(test.starts_at),
            "duration_minutes": test.duration_minutes,
            "entry_window_minutes": test.entry_window_minutes,
            "created_by_membership_id": test.created_by_membership_id,
            "published_at": format_local_datetime(test.published_at),
            "scheduled_publish_at": format_local_datetime(test.scheduled_publish_at),
            "closed_at": format_local_datetime(test.closed_at),
            "archived_at": format_local_datetime(test.archived_at),
            "created_at": format_local_datetime(test.created_at),
            "updated_at": format_local_datetime(test.updated_at),
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
            "snapshot_image_path": row.snapshot_image_path,
            "snapshot_image_url": self.images.build_public_url(row.snapshot_image_path),
            "snapshot_type_code": row.snapshot_type_code,
            "snapshot_topic_id": row.snapshot_topic_id,
            "snapshot_topic_name": row.snapshot_topic_name,
            "snapshot_difficulty": row.snapshot_difficulty,
            "snapshot_points": float(row.snapshot_points) if row.snapshot_points is not None else None,
            "snapshot_choices": self._load_json(row.snapshot_choices_json) or [],
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def _validate_students_belong_to_test_subject(
        self,
        *,
        workspace_id: int,
        test: Test,
        student_membership_ids: list[int],
    ) -> None:
        if not student_membership_ids:
            raise ValidationError(Messages.STUDENT_MEMBERSHIP_IDS_MUST_CONTAIN_AT_LEAST_ONE_ID)

        missing_in_workspace: list[int] = []
        not_student_role: list[int] = []
        not_enrolled: list[int] = []
        inactive_memberships: list[int] = []

        for membership_id in student_membership_ids:
            membership = db.session.get(Membership, membership_id)
            if not membership or membership.workspace_id != workspace_id:
                missing_in_workspace.append(membership_id)
                continue
            if membership.status != MembershipStatus.ACTIVE.value:
                inactive_memberships.append(membership_id)
                continue
            if membership.role != MembershipRole.STUDENT.value:
                not_student_role.append(membership_id)
                continue
            link = self.subject_memberships.find_active_by_role(
                membership_id,
                test.subject_id,
                SubjectRole.STUDENT.value,
            )
            if not link:
                not_enrolled.append(membership_id)

        if missing_in_workspace:
            raise ValidationError(Messages.MEMBERSHIP_S_NOT_FOUND_IN_WORKSPACE_MISSING_IN_WORKSPACE.format(missing_in_workspace=missing_in_workspace))
        if inactive_memberships:
            raise ValidationError(Messages.MEMBERSHIP_S_ARE_NOT_ACTIVE_INACTIVE_MEMBERSHIPS.format(inactive_memberships=inactive_memberships))
        if not_student_role:
            raise ValidationError(Messages.ONLY_STUDENT_MEMBERSHIPS_ARE_ALLOWED_NOT_STUDENT_ROLE.format(not_student_role=not_student_role))
        if not_enrolled:
            raise ValidationError(
                Messages.STUDENT_MEMBERSHIPS_NOT_ENROLLED_IN_EXAM_SUBJECT.format(
                    membership_ids=not_enrolled
                )
            )

    def _normalize_slug_value(self, raw: str) -> str:
        base = raw.strip().lower()
        return re.sub(r"[^a-z0-9]+", "-", base).strip("-")

    def _resolve_slug(self, maybe_slug: str | None, name: str) -> str:
        raw = (maybe_slug or name or "").strip()
        normalized = self._normalize_slug_value(raw) if raw else ""
        return normalized or "test"

    def _resolve_unique_slug(self, base_slug: str, *, exclude_test_id: int | None = None) -> str:
        """
        Create a unique slug by appending -2, -3, ... when needed.
        This avoids collisions for non-latin titles that normalize to the same fallback.
        """
        candidate = base_slug
        counter = 2
        while True:
            existing = self.tests.find_by_slug(candidate)
            if not existing or (
                exclude_test_id is not None and existing.id == exclude_test_id
            ):
                return candidate
            candidate = f"{base_slug}-{counter}"
            counter += 1

    def _create_snapshot_row_from_payload(
        self, *, test: Test, workspace_id: int, payload: dict, source_type: str
    ) -> TestQuestion:
        validated = self._validate_and_normalize_payload(payload)
        topic_id, topic_name = self._resolve_topic_snapshot(
            test, validated["topic_id"], workspace_id
        )
        row = TestQuestion(
            test_id=test.id,
            question_id=None,
            kind=source_type,
            source_type=source_type,
            source_bank_id=None,
            points=validated["points"],
            snapshot_question_text=validated["body"],
            snapshot_image_path=validated.get("image_path"),
            snapshot_explanation=validated["explanation"],
            snapshot_type_code=validated["type_code"],
            snapshot_topic_id=topic_id,
            snapshot_topic_name=topic_name,
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
            raise ValidationError(Messages.QUESTION_TYPE_TYPE_CODE_IS_NOT_CONFIGURED_RUN_FLASK_SEED.format(type_code=type_code))

        body = (payload.get("body") or "").strip()
        if not body:
            raise ValidationError(Messages.QUESTION_BODY_IS_REQUIRED)

        points = payload.get("points")
        points_value = Decimal(str(points)) if points is not None else Decimal("1")
        if points_value < 0:
            raise ValidationError(Messages.POINTS_MUST_BE_NON_NEGATIVE)

        difficulty = payload.get("difficulty")
        if difficulty is not None:
            difficulty = difficulty.strip().upper()
            if difficulty not in [d.value for d in Difficulty]:
                raise ValidationError(Messages.INVALID_DIFFICULTY_VALUE)

        topic_id = payload.get("topic_id")
        if topic_id is not None:
            try:
                topic_id = int(topic_id)
            except (TypeError, ValueError):
                raise ValidationError(Messages.TOPIC_ID_MUST_BE_A_VALID_INTEGER)
            if topic_id <= 0:
                topic_id = None

        choices = payload.get("choices") or []
        return {
            "type_code": type_code,
            "body": body,
            "explanation": (payload.get("explanation") or "").strip() or None,
            "image_path": (payload.get("image_path") or "").strip() or None,
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

    def _to_decimal(self, value, field_name: str):
        if value is None:
            return None
        try:
            parsed = Decimal(str(value))
        except Exception:
            raise ValidationError(Messages.FIELD_NAME_MUST_BE_NUMERIC.format(field_name=field_name))
        if parsed < 0:
            raise ValidationError(Messages.FIELD_NAME_MUST_BE_NON_NEGATIVE.format(field_name=field_name))
        return parsed

    def _validate_test_timing_rules(self, test: Test) -> None:
        mode = (test.availability_time_mode or AvailabilityTimeMode.SCHEDULED.value).upper()
        if mode == AvailabilityTimeMode.SURVEY.value:
            if test.closed_at is None:
                raise ValidationError(Messages.SURVEY_CLOSED_AT_IS_REQUIRED)
            if test.duration_minutes is not None:
                raise ValidationError(Messages.SURVEY_DURATION_IS_NOT_ALLOWED)
            return
        if mode == AvailabilityTimeMode.SCHEDULED.value:
            # Duration required when publishing/taking; allow null while drafting.
            return

    def _normalize_settings_config(self, value, *, test: Test | None = None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValidationError(Messages.SETTINGS_CONFIG_MUST_BE_AN_OBJECT)
        proctoring_raw = value.get("proctoring") or {}
        if not isinstance(proctoring_raw, dict):
            raise ValidationError(Messages.SETTINGS_CONFIGPROCTORING_MUST_BE_AN_OBJECT)

        attempt_raw = value.get("attempt_settings") or {}
        if not isinstance(attempt_raw, dict):
            raise ValidationError(Messages.SETTINGS_CONFIGATTEMPT_SETTINGS_MUST_BE_AN_OBJECT)
        max_attempts_raw = attempt_raw.get("max_attempts", 1)
        try:
            max_attempts = int(max_attempts_raw)
        except (TypeError, ValueError):
            raise ValidationError(Messages.SETTINGS_CONFIGATTEMPT_SETTINGSMAX_ATTEMPTS_MUST_BE_AN_INTEGER)
        if max_attempts < 1:
            raise ValidationError(Messages.SETTINGS_CONFIGATTEMPT_SETTINGSMAX_ATTEMPTS_MUST_BE_1)

        navigation_raw = value.get("navigation_settings") or {}
        if not isinstance(navigation_raw, dict):
            raise ValidationError(Messages.SETTINGS_CONFIGNAVIGATION_SETTINGS_MUST_BE_AN_OBJECT)

        answer_rules_raw = value.get("answer_rules") or {}
        if not isinstance(answer_rules_raw, dict):
            raise ValidationError(Messages.SETTINGS_CONFIGANSWER_RULES_MUST_BE_AN_OBJECT)

        display_raw = value.get("display_settings") or {}
        if not isinstance(display_raw, dict):
            raise ValidationError(Messages.SETTINGS_CONFIGDISPLAY_SETTINGS_MUST_BE_AN_OBJECT)

        review_raw = value.get("review_settings") or {}
        if not isinstance(review_raw, dict):
            raise ValidationError(Messages.SETTINGS_CONFIGREVIEW_SETTINGS_MUST_BE_AN_OBJECT)

        offline_raw = value.get("offline_policy") or {}
        if offline_raw and not isinstance(offline_raw, dict):
            raise ValidationError(Messages.SETTINGS_CONFIGOFFLINE_POLICY_MUST_BE_AN_OBJECT)

        require_answer_all = bool(answer_rules_raw.get("require_answer_all", False))
        allow_skip_questions = bool(answer_rules_raw.get("allow_skip_questions", True))
        if require_answer_all and allow_skip_questions:
            allow_skip_questions = False

        proctoring_enabled = bool(proctoring_raw.get("enabled", False))
        mode = (
            (test.availability_time_mode or AvailabilityTimeMode.SCHEDULED.value).upper()
            if test is not None
            else AvailabilityTimeMode.SCHEDULED.value
        )
        if mode == AvailabilityTimeMode.SURVEY.value and proctoring_enabled:
            raise ValidationError(Messages.SURVEY_PROCTORING_IS_NOT_ALLOWED)
        if mode == AvailabilityTimeMode.SURVEY.value:
            proctoring_enabled = False

        grace = self._resolve_offline_grace_minutes(
            mode=mode,
            proctoring_enabled=proctoring_enabled,
            offline_raw=offline_raw if isinstance(offline_raw, dict) else {},
        )

        normalized = {
            "proctoring": {"enabled": proctoring_enabled},
            "attempt_settings": {
                "max_attempts": max_attempts,
            },
            "navigation_settings": {
                "sequential_navigation": bool(
                    navigation_raw.get("sequential_navigation", False)
                ),
                "allow_back_navigation": bool(
                    navigation_raw.get("allow_back_navigation", True)
                ),
            },
            "answer_rules": {
                "require_answer_all": require_answer_all,
                "allow_skip_questions": allow_skip_questions,
            },
            "display_settings": {
                "shuffle_questions": bool(display_raw.get("shuffle_questions", False)),
                "shuffle_choices": bool(display_raw.get("shuffle_choices", False)),
            },
            "review_settings": {
                "allow_review_after_grading": bool(
                    review_raw.get("allow_review_after_grading", False)
                )
            },
            "offline_policy": {
                # Frontend owns the grace timer; backend stores policy only.
                "grace_period_minutes": grace,
            },
        }
        return self._dump_json(normalized)

    @staticmethod
    def _resolve_offline_grace_minutes(
        *,
        mode: str,
        proctoring_enabled: bool,
        offline_raw: dict,
    ) -> int | None:
        """
        Policy:
        - SCHEDULED (any proctoring): default 5
        - FLEXIBLE + PROCTORED: default 5
        - FLEXIBLE + NON-PROCTORED: null
        - SURVEY: null
        Grace never extends the authoritative deadline.
        """
        if mode == AvailabilityTimeMode.SURVEY.value:
            return None
        if mode == AvailabilityTimeMode.FLEXIBLE.value and not proctoring_enabled:
            return None

        if "grace_period_minutes" in offline_raw:
            raw = offline_raw.get("grace_period_minutes")
            if raw is None:
                return None
            try:
                value = int(raw)
            except (TypeError, ValueError):
                raise ValidationError(
                    Messages.SETTINGS_CONFIGOFFLINE_POLICYGRACE_PERIOD_MINUTES_MUST_BE_A_NON_NEGATIVE_INTEGER
                )
            if value < 0:
                raise ValidationError(
                    Messages.SETTINGS_CONFIGOFFLINE_POLICYGRACE_PERIOD_MINUTES_MUST_BE_A_NON_NEGATIVE_INTEGER
                )
            return value
        return DEFAULT_OFFLINE_GRACE_MINUTES

    def _ensure_test_editable_for_settings_update(self, test: Test) -> None:
        if test.status == TestStatus.DRAFT.value:
            return
        if test.status != TestStatus.SCHEDULED.value:
            raise ValidationError(Messages.ONLY_DRAFT_TESTS_ARE_EDITABLE)

        if not test.scheduled_publish_at:
            raise ValidationError(Messages.SCHEDULED_TEST_IS_MISSING_SCHEDULED_PUBLISH_AT)
        now = local_timezone_now()
        publish_at = ensure_local_aware(test.scheduled_publish_at)
        min_delta = timedelta(minutes=30)
        if publish_at - now < min_delta:
            raise ValidationError(Messages.SCHEDULED_TESTS_CAN_ONLY_BE_EDITED_AT_LEAST_30_MINUTES_BEFORE_PUBLISH_TIME)

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
