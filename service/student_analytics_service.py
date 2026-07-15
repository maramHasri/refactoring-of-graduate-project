"""
Student analytics based on already graded test attempts.
"""

from __future__ import annotations

from utils.messages import Messages

from repositories.attempt_repository import TestAttemptRepository
from repositories.subject_repository import SubjectMembershipRepository, SubjectRepository
from service.exceptions import NotFoundError, ValidationError
from utils.academic_rbac import verify_subject_student_access
from utils.enums import MembershipRole, SubjectRole, TestAttemptStatus


class StudentAnalyticsService:
    def __init__(self):
        self.attempts = TestAttemptRepository()
        self.subjects = SubjectRepository()
        self.subject_memberships = SubjectMembershipRepository()

    def get_subject_analytics(
        self,
        *,
        workspace_id: int,
        actor_membership,
        actor_user_id: int,
        subject_id: int,
    ) -> dict:
        self._ensure_student_scope(actor_membership)
        subject = self.subjects.get_active_by_id(subject_id, workspace_id)
        if not subject:
            raise NotFoundError(Messages.SUBJECT_NOT_FOUND)
        actor_link = self._subject_student_link(actor_membership.id, subject_id)
        if not verify_subject_student_access(actor_link):
            raise NotFoundError(Messages.SUBJECT_NOT_FOUND)

        rows = self.attempts.list_topic_weighted_rows_for_subject(
            workspace_id=workspace_id,
            student_membership_id=actor_membership.id,
            student_user_id=actor_user_id,
            subject_id=subject_id,
        )
        topics = self._serialize_topics(rows, key_name="performance")
        overall = self._overall_percentage(rows)

        return {
            "subject_id": subject.id,
            "subject_name": subject.name,
            "student": {
                "user_id": actor_user_id,
                "membership_id": actor_membership.id,
            },
            "overall_performance": overall,
            "topics": topics,
            "strengths": [
                item for item in topics if item["classification"] == "STRENGTH"
            ],
            "weaknesses": [
                item
                for item in topics
                if item["classification"] in ("NEEDS_IMPROVEMENT", "WEAKNESS")
            ],
        }

    def get_course_analytics(
        self,
        *,
        workspace_id: int,
        actor_membership,
        actor_user_id: int,
        course_id: int,
    ) -> dict:
        """
        Backward-compatible alias.
        In this system, course == subject.
        """
        result = self.get_subject_analytics(
            workspace_id=workspace_id,
            actor_membership=actor_membership,
            actor_user_id=actor_user_id,
            subject_id=course_id,
        )
        return {
            **result,
            "course_id": result["subject_id"],
            "course_name": result["subject_name"],
        }

    def get_test_analytics(
        self,
        *,
        workspace_id: int,
        actor_membership,
        actor_user_id: int,
        test_id: int,
    ) -> dict:
        self._ensure_student_scope(actor_membership)
        attempt = self.attempts.find_graded_for_student_test(
            workspace_id=workspace_id,
            student_membership_id=actor_membership.id,
            student_user_id=actor_user_id,
            test_id=test_id,
        )
        if not attempt:
            raise NotFoundError(Messages.GRADED_TEST_RESULT_NOT_FOUND)
        if attempt.status != TestAttemptStatus.GRADED.value:
            raise ValidationError(Messages.TEST_ATTEMPT_IS_NOT_FULLY_GRADED)

        rows = self.attempts.list_topic_weighted_rows_for_attempt(attempt_id=attempt.id)
        topics = self._serialize_topics(rows, key_name="mastery_percentage")
        return {
            "test_id": attempt.test_id,
            "test_title": attempt.test.name if attempt.test else None,
            "final_score": float(attempt.final_score or 0.0),
            "percentage": float(attempt.percentage or 0.0),
            "attempt_id": attempt.id,
            "topics": topics,
        }

    def _subject_student_link(self, membership_id: int, subject_id: int):
        return self.subject_memberships.find_active_by_role(
            membership_id, subject_id, SubjectRole.STUDENT.value
        )

    @staticmethod
    def _ensure_student_scope(actor_membership) -> None:
        if actor_membership.role != MembershipRole.STUDENT.value:
            raise ValidationError(Messages.STUDENT_ACCESS_REQUIRED)

    @staticmethod
    def _classify(performance: float) -> str:
        if performance >= 85:
            return "STRENGTH"
        if performance >= 70:
            return "GOOD"
        if performance >= 50:
            return "NEEDS_IMPROVEMENT"
        return "WEAKNESS"

    def _serialize_topics(
        self,
        rows: list[tuple[int | None, str | None, float, float]],
        *,
        key_name: str,
    ) -> list[dict]:
        items: list[dict] = []
        for topic_id, topic_name, weighted_earned, weighted_possible in rows:
            if weighted_possible <= 0:
                percentage = 0.0
            else:
                percentage = round((weighted_earned / weighted_possible) * 100, 2)
            item = {
                "topic_id": topic_id,
                "topic_name": topic_name or "General",
                key_name: percentage,
                "weighted_earned_points": round(weighted_earned, 2),
                "weighted_possible_points": round(weighted_possible, 2),
                "classification": self._classify(percentage),
            }
            items.append(item)
        items.sort(key=lambda x: x[key_name], reverse=True)
        return items

    @staticmethod
    def _overall_percentage(
        rows: list[tuple[int | None, str | None, float, float]]
    ) -> float:
        total_earned = sum(weighted_earned for _, _, weighted_earned, _ in rows)
        total_possible = sum(weighted_possible for _, _, _, weighted_possible in rows)
        if total_possible <= 0:
            return 0.0
        return round((total_earned / total_possible) * 100, 2)
