"""Teacher-scoped workspace dashboard (subjects the teacher teaches)."""

from __future__ import annotations

from collections import defaultdict

from models import Membership, Test, TestAttempt, Workspace
from repositories.attempt_repository import TestAttemptRepository
from repositories.subject_repository import SubjectMembershipRepository
from repositories.teacher_dashboard_repository import TeacherDashboardRepository
from repositories.workspace_repository import WorkspaceRepository
from service.exceptions import ForbiddenError, NotFoundError
from service.student_analytics_service import StudentAnalyticsService
from utils.academic_rbac import can_manage_subjects
from utils.app_timezone import ensure_local_aware, format_local_datetime, local_timezone_now
from utils.enums import MembershipRole, WorkspaceKind
from utils.messages import Messages

_WEAK_TOPIC_CLASSIFICATIONS = frozenset({"NEEDS_IMPROVEMENT", "WEAKNESS"})
SUMMARY_WEAK_TOPICS_LIMIT = 5
SUBJECT_WEAK_TOPICS_LIMIT = 3
DEFAULT_UPCOMING_LIMIT = 5
DEFAULT_RECENT_LIMIT = 5


class TeacherDashboardService:
    def __init__(self):
        self.workspaces = WorkspaceRepository()
        self.subject_memberships = SubjectMembershipRepository()
        self.dashboard = TeacherDashboardRepository()
        self.attempts = TestAttemptRepository()

    def get_dashboard(
        self,
        workspace_id: int,
        actor_membership: Membership,
        *,
        upcoming_limit: int = DEFAULT_UPCOMING_LIMIT,
        recent_limit: int = DEFAULT_RECENT_LIMIT,
    ) -> dict:
        workspace = self._ensure_access(workspace_id, actor_membership)
        subject_ids = self._resolve_subject_scope(workspace, actor_membership)
        subjects = self.dashboard.list_active_subjects_by_ids(subject_ids)

        graded_attempts = self.dashboard.list_graded_attempts_for_subjects(
            workspace_id=workspace.id,
            subject_ids=subject_ids,
        )
        students_per_subject = self.dashboard.count_students_per_subject(subject_ids)
        graded_tests_per_subject = self.dashboard.count_graded_tests_per_subject(
            workspace_id=workspace.id,
            subject_ids=subject_ids,
        )

        attempts_by_subject: dict[int, list[TestAttempt]] = defaultdict(list)
        for attempt in graded_attempts:
            test = attempt.test
            if test and test.subject_id is not None:
                attempts_by_subject[int(test.subject_id)].append(attempt)

        weak_by_subject = self._build_weak_topics_by_subject(graded_attempts)

        subject_cards = []
        for subject in subjects:
            sid = subject.id
            subject_attempts = attempts_by_subject.get(sid, [])
            subject_cards.append(
                {
                    "subject_id": sid,
                    "subject_name": subject.name,
                    "students_enrolled": students_per_subject.get(sid, 0),
                    "students_count": students_per_subject.get(sid, 0),
                    "graded_tests_count": graded_tests_per_subject.get(sid, 0),
                    "average_performance": self._average_percentage(subject_attempts),
                    "success_rate": self._success_rate(subject_attempts),
                    "weak_topics": weak_by_subject.get(sid, [])[:SUBJECT_WEAK_TOPICS_LIMIT],
                }
            )

        now = local_timezone_now()
        upcoming = [
            self._serialize_upcoming_test(test)
            for test in self.dashboard.list_upcoming_tests_for_subjects(
                workspace_id=workspace.id,
                subject_ids=subject_ids,
                now=now,
                limit=upcoming_limit,
            )
        ]
        recent = [
            self._serialize_recent_test(test)
            for test in self.dashboard.list_recent_created_tests(
                creator_membership_id=actor_membership.id,
                limit=recent_limit,
            )
        ]

        summary_weak = self._flatten_weak_topics(weak_by_subject)[
            :SUMMARY_WEAK_TOPICS_LIMIT
        ]

        return {
            "success": True,
            "summary": {
                "average_performance": self._average_percentage(graded_attempts),
                "total_students": self.dashboard.count_distinct_students_for_subjects(
                    subject_ids
                ),
                "weak_topics": summary_weak,
            },
            "subjects": subject_cards,
            "upcoming_tests": upcoming,
            "recent_tests": recent,
        }

    def _ensure_access(
        self, workspace_id: int, actor_membership: Membership
    ) -> Workspace:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError(Messages.WORKSPACE_NOT_FOUND)
        if workspace.kind not in (
            WorkspaceKind.INSTITUTION.value,
            WorkspaceKind.SOLO.value,
        ):
            raise ForbiddenError(Messages.UNSUPPORTED_WORKSPACE_TYPE_FOR_MEMBER_MANAGEMENT)

        if can_manage_subjects(workspace, actor_membership):
            return workspace
        if actor_membership.role == MembershipRole.TEACHER.value:
            return workspace
        # Subject-assigned ADMIN already covered by can_manage_subjects;
        # allow membership that has teacher subject links even if role is odd.
        if self.subject_memberships.list_teacher_subject_ids(
            actor_membership.id, workspace_id
        ):
            return workspace
        raise ForbiddenError(Messages.TEACHER_OR_WORKSPACE_ADMIN_ACCESS_REQUIRED)

    def _resolve_subject_scope(
        self, workspace: Workspace, actor_membership: Membership
    ) -> list[int]:
        # Same product pattern as question banks: owner/ADMIN → all workspace subjects.
        if can_manage_subjects(workspace, actor_membership):
            return self.dashboard.list_active_subject_ids_for_workspace(workspace.id)
        return self.subject_memberships.list_teacher_subject_ids(
            actor_membership.id, workspace.id
        )

    def _build_weak_topics_by_subject(
        self, graded_attempts: list[TestAttempt]
    ) -> dict[int, list[dict]]:
        """
        Cohort weak topics:
        - mastery_percentage = difficulty-weighted cohort mastery across graded attempts
        - classification uses StudentAnalyticsService._classify thresholds
        - students_affected = distinct students whose per-attempt topic mastery was weak
        - attempts_count = graded attempts that included the topic
        """
        if not graded_attempts:
            return {}

        attempt_ids = [attempt.id for attempt in graded_attempts]
        attempt_subject = {
            attempt.id: int(attempt.test.subject_id)
            for attempt in graded_attempts
            if attempt.test and attempt.test.subject_id is not None
        }
        attempt_student = {
            attempt.id: attempt.student_membership_id for attempt in graded_attempts
        }
        subject_names = {
            int(attempt.test.subject_id): attempt.test.subject.name
            for attempt in graded_attempts
            if attempt.test
            and attempt.test.subject_id is not None
            and attempt.test.subject is not None
        }

        # Cohort mastery per (subject, topic).
        cohort_rows = self.attempts.list_topic_weighted_rows_for_attempt_ids(
            attempt_ids=attempt_ids
        )
        # Per-attempt rows for students_affected / attempts_count.
        per_attempt_rows = self.attempts.list_topic_weighted_rows_grouped_by_attempt(
            attempt_ids=attempt_ids
        )

        meta: dict[tuple[int, int | None], dict] = {}
        for (
            subject_id,
            subject_name,
            topic_id,
            topic_name,
            weighted_earned,
            weighted_possible,
        ) in cohort_rows:
            if subject_id is None:
                continue
            if weighted_possible <= 0:
                mastery = 0.0
            else:
                mastery = round((weighted_earned / weighted_possible) * 100, 2)
            if StudentAnalyticsService._classify(mastery) not in _WEAK_TOPIC_CLASSIFICATIONS:
                continue
            key = (int(subject_id), topic_id)
            meta[key] = {
                "subject_id": int(subject_id),
                "subject_name": subject_name or subject_names.get(int(subject_id)),
                "topic_id": topic_id,
                "topic_name": topic_name or "General",
                "mastery_percentage": mastery,
                "student_ids": set(),
                "attempt_ids": set(),
            }

        for attempt_id, topic_id, topic_name, weighted_earned, weighted_possible in per_attempt_rows:
            subject_id = attempt_subject.get(attempt_id)
            if subject_id is None:
                continue
            key = (subject_id, topic_id)
            entry = meta.get(key)
            if entry is None:
                continue
            entry["attempt_ids"].add(attempt_id)
            if weighted_possible <= 0:
                mastery = 0.0
            else:
                mastery = round((weighted_earned / weighted_possible) * 100, 2)
            if StudentAnalyticsService._classify(mastery) not in _WEAK_TOPIC_CLASSIFICATIONS:
                continue
            student_id = attempt_student.get(attempt_id)
            if student_id is not None:
                entry["student_ids"].add(student_id)
            if not entry.get("topic_name") and topic_name:
                entry["topic_name"] = topic_name

        by_subject: dict[int, list[dict]] = defaultdict(list)
        for entry in meta.values():
            payload = {
                "topic_id": entry["topic_id"],
                "topic_name": entry["topic_name"],
                "mastery_percentage": entry["mastery_percentage"],
                "average_score": entry["mastery_percentage"],
                "attempts_count": len(entry["attempt_ids"]),
                "students_affected": len(entry["student_ids"]),
                "subject_id": entry["subject_id"],
                "subject_name": entry["subject_name"],
            }
            by_subject[entry["subject_id"]].append(payload)

        for items in by_subject.values():
            items.sort(
                key=lambda item: (
                    item["mastery_percentage"],
                    -item["students_affected"],
                    -item["attempts_count"],
                )
            )
        return by_subject

    @staticmethod
    def _flatten_weak_topics(weak_by_subject: dict[int, list[dict]]) -> list[dict]:
        flattened: list[dict] = []
        for items in weak_by_subject.values():
            flattened.extend(items)
        flattened.sort(
            key=lambda item: (
                item["mastery_percentage"],
                -item["students_affected"],
                -item["attempts_count"],
            )
        )
        return flattened

    @staticmethod
    def _average_percentage(attempts: list[TestAttempt]) -> float:
        if not attempts:
            return 0.0
        values = [float(a.percentage) for a in attempts if a.percentage is not None]
        if not values:
            return 0.0
        return round(sum(values) / len(values), 2)

    @staticmethod
    def _success_rate(attempts: list[TestAttempt]) -> float:
        """Passed graded attempts / total graded attempts × 100 (existing pass rule)."""
        if not attempts:
            return 0.0
        passed = 0
        for attempt in attempts:
            test = attempt.test
            if test is None:
                continue
            if StudentAnalyticsService._attempt_is_passed(attempt, test):
                passed += 1
        return round((passed / len(attempts)) * 100, 2)

    @staticmethod
    def _serialize_upcoming_test(test: Test) -> dict:
        subject = test.subject
        starts_at_date = None
        starts_at_time = None
        if test.starts_at is not None:
            local_at = ensure_local_aware(test.starts_at)
            starts_at_date = local_at.date().isoformat()
            starts_at_time = local_at.strftime("%H:%M")
        return {
            "test_id": test.id,
            "title": test.name,
            "name": test.name,
            "subject_id": test.subject_id,
            "subject_name": subject.name if subject else None,
            "starts_at": format_local_datetime(test.starts_at),
            "starts_at_date": starts_at_date,
            "starts_at_time": starts_at_time,
            "ends_at": format_local_datetime(test.closed_at),
            "closed_at": format_local_datetime(test.closed_at),
            "status": test.status,
            "availability_time_mode": test.availability_time_mode,
        }

    @staticmethod
    def _serialize_recent_test(test: Test) -> dict:
        subject = test.subject
        return {
            "test_id": test.id,
            "title": test.name,
            "name": test.name,
            "subject_id": test.subject_id,
            "subject_name": subject.name if subject else None,
            "status": test.status,
            "created_at": format_local_datetime(test.created_at),
            "published_at": format_local_datetime(test.published_at),
        }
