"""
Student analytics based on already graded test attempts.
"""

from __future__ import annotations

from utils.messages import Messages

from models import Test, TestAttempt
from repositories.attempt_repository import TestAttemptRepository
from repositories.subject_repository import SubjectMembershipRepository, SubjectRepository
from service.exceptions import NotFoundError, ValidationError
from utils.academic_rbac import verify_subject_student_access
from utils.enums import MembershipRole, SubjectRole, TestAttemptStatus
from utils.review_settings import allow_review_after_grading

_WEAK_TOPIC_CLASSIFICATIONS = frozenset({"NEEDS_IMPROVEMENT", "WEAKNESS"})


class StudentAnalyticsService:
    def __init__(self):
        self.attempts = TestAttemptRepository()
        self.subjects = SubjectRepository()
        self.subject_memberships = SubjectMembershipRepository()

    def get_dashboard_analytics(
        self,
        *,
        workspace_id: int,
        actor_membership,
        actor_user_id: int,
    ) -> dict:
        """
        High-level Student Dashboard performance summary.

        Uses only graded attempts whose results are published
        (`review_settings.allow_review_after_grading`).
        """
        self._ensure_student_scope(actor_membership)
        graded_attempts = self.attempts.list_graded_for_student(
            workspace_id=workspace_id,
            student_membership_id=actor_membership.id,
            student_user_id=actor_user_id,
        )
        published_attempts = [
            attempt
            for attempt in graded_attempts
            if attempt.test is not None
            and self._is_published_graded_result(attempt.test, attempt)
            and attempt.percentage is not None
        ]

        if not published_attempts:
            return self._empty_dashboard()

        overview = self._build_overview(published_attempts)
        best_subject, weakest_subject = self._build_subject_extremes(published_attempts)
        weak_topics = self._build_weak_topics(
            [attempt.id for attempt in published_attempts]
        )

        return {
            "overview": overview,
            "best_subject": best_subject,
            "weakest_subject": weakest_subject,
            "weak_topics": weak_topics,
        }

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
                if item["classification"] in _WEAK_TOPIC_CLASSIFICATIONS
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
    def _is_published_graded_result(test: Test, attempt: TestAttempt) -> bool:
        if attempt.status != TestAttemptStatus.GRADED.value:
            return False
        return allow_review_after_grading(test.settings_config)

    @staticmethod
    def _empty_dashboard() -> dict:
        return {
            "overview": {
                "overall_average": 0,
                "highest_score": None,
                "lowest_score": None,
                "total_exams": 0,
                "passed_exams": 0,
                "failed_exams": 0,
            },
            "best_subject": None,
            "weakest_subject": None,
            "weak_topics": [],
        }

    def _build_overview(self, published_attempts: list[TestAttempt]) -> dict:
        percentages = [float(attempt.percentage) for attempt in published_attempts]
        passed_exams = 0
        failed_exams = 0
        for attempt in published_attempts:
            if self._attempt_is_passed(attempt, attempt.test):
                passed_exams += 1
            else:
                failed_exams += 1

        return {
            "overall_average": round(sum(percentages) / len(percentages), 2),
            "highest_score": round(max(percentages), 2),
            "lowest_score": round(min(percentages), 2),
            "total_exams": len(published_attempts),
            "passed_exams": passed_exams,
            "failed_exams": failed_exams,
        }

    @staticmethod
    def _attempt_is_passed(attempt: TestAttempt, test: Test) -> bool:
        """Pass/fail uses the exam's configured passing_score (absolute points)."""
        if test.passing_score is not None and attempt.final_score is not None:
            return float(attempt.final_score) >= float(test.passing_score)
        # No passing threshold configured — treat as passed (cannot fail without a bar).
        return True

    def _build_subject_extremes(
        self, published_attempts: list[TestAttempt]
    ) -> tuple[dict | None, dict | None]:
        subject_stats: dict[int, dict] = {}
        for attempt in published_attempts:
            test = attempt.test
            subject = test.subject if test else None
            if subject is None:
                continue
            entry = subject_stats.get(subject.id)
            if entry is None:
                entry = {
                    "id": subject.id,
                    "name": subject.name,
                    "percentages": [],
                }
                subject_stats[subject.id] = entry
            entry["percentages"].append(float(attempt.percentage))

        if not subject_stats:
            return None, None

        ranked: list[dict] = []
        for entry in subject_stats.values():
            percentages = entry["percentages"]
            ranked.append(
                {
                    "id": entry["id"],
                    "name": entry["name"],
                    "average_percentage": round(sum(percentages) / len(percentages), 2),
                    "attempt_count": len(percentages),
                }
            )

        best = max(
            ranked,
            key=lambda item: (item["average_percentage"], item["attempt_count"]),
        )
        weakest = min(
            ranked,
            key=lambda item: (item["average_percentage"], -item["attempt_count"]),
        )

        return (
            {
                "id": best["id"],
                "name": best["name"],
                "average_percentage": best["average_percentage"],
            },
            {
                "id": weakest["id"],
                "name": weakest["name"],
                "average_percentage": weakest["average_percentage"],
            },
        )

    def _build_weak_topics(self, published_attempt_ids: list[int]) -> list[dict]:
        rows = self.attempts.list_topic_weighted_rows_for_attempt_ids(
            attempt_ids=published_attempt_ids
        )
        weak_topics: list[dict] = []
        for (
            subject_id,
            subject_name,
            topic_id,
            topic_name,
            weighted_earned,
            weighted_possible,
        ) in rows:
            if weighted_possible <= 0:
                mastery = 0.0
            else:
                mastery = round((weighted_earned / weighted_possible) * 100, 2)
            classification = self._classify(mastery)
            if classification not in _WEAK_TOPIC_CLASSIFICATIONS:
                continue
            weak_topics.append(
                {
                    "subject_id": subject_id,
                    "subject_name": subject_name,
                    "topic_id": topic_id,
                    "topic_name": topic_name or "General",
                    "mastery": mastery,
                }
            )

        weak_topics.sort(key=lambda item: item["mastery"])
        return weak_topics

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
