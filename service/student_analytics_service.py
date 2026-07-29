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

_WEAK_TOPIC_CLASSIFICATIONS = frozenset({"NEEDS_IMPROVEMENT", "WEAKNESS"})

# Recent graded attempts used when summarizing "topics to strengthen lately".
RECENT_WEAK_TOPICS_ATTEMPT_LIMIT = 5


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

        Includes every graded attempt (`status=GRADED`). Review settings do not
        affect score visibility or analytics inclusion.
        """
        self._ensure_student_scope(actor_membership)
        graded_attempts = [
            attempt
            for attempt in self.attempts.list_graded_for_student(
                workspace_id=workspace_id,
                student_membership_id=actor_membership.id,
                student_user_id=actor_user_id,
            )
            if attempt.test is not None and attempt.percentage is not None
        ]

        if not graded_attempts:
            return self._empty_dashboard()

        overview = self._build_overview(graded_attempts)
        best_subject, weakest_subject = self._build_subject_extremes(graded_attempts)
        weak_topics = self._build_weak_topics([attempt.id for attempt in graded_attempts])

        return {
            "overview": overview,
            "best_subject": best_subject,
            "weakest_subject": weakest_subject,
            "weak_topics": weak_topics,
        }

    def get_performance_summary(
        self,
        *,
        workspace_id: int,
        actor_membership,
        actor_user_id: int,
    ) -> dict:
        """
        Compact performance summary for the authenticated student.

        Reuses graded-attempt filtering, percentage averages, subject ranking,
        and the same topic mastery classification as get_test_analytics /
        get_dashboard_analytics. Weak topics are derived from the most recent
        graded attempts only (RECENT_WEAK_TOPICS_ATTEMPT_LIMIT).
        """
        self._ensure_student_scope(actor_membership)
        graded_attempts = [
            attempt
            for attempt in self.attempts.list_graded_for_student(
                workspace_id=workspace_id,
                student_membership_id=actor_membership.id,
                student_user_id=actor_user_id,
            )
            if attempt.test is not None and attempt.percentage is not None
        ]

        if not graded_attempts:
            return {
                "average_score": 0,
                "highest_score": None,
                "best_subject": None,
                "weak_topics": [],
            }

        percentages = [float(attempt.percentage) for attempt in graded_attempts]
        best_subject, _ = self._build_subject_extremes(graded_attempts)
        recent_for_topics = graded_attempts[:RECENT_WEAK_TOPICS_ATTEMPT_LIMIT]
        weak_topics = self._build_recent_weak_topics_summary(
            [attempt.id for attempt in recent_for_topics]
        )

        best_subject_payload = None
        if best_subject is not None:
            best_subject_payload = {
                "subject_id": best_subject["id"],
                "subject_name": best_subject["name"],
                "average_score": best_subject["average_percentage"],
            }

        return {
            "average_score": round(sum(percentages) / len(percentages), 2),
            "highest_score": round(max(percentages), 2),
            "best_subject": best_subject_payload,
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
            "student_name": (
                attempt.user.full_name
                if attempt.user is not None and attempt.user.full_name
                else None
            ),
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

    def _build_overview(self, graded_attempts: list[TestAttempt]) -> dict:
        percentages = [float(attempt.percentage) for attempt in graded_attempts]
        passed_exams = 0
        failed_exams = 0
        for attempt in graded_attempts:
            if self._attempt_is_passed(attempt, attempt.test):
                passed_exams += 1
            else:
                failed_exams += 1

        return {
            "overall_average": round(sum(percentages) / len(percentages), 2),
            "highest_score": round(max(percentages), 2),
            "lowest_score": round(min(percentages), 2),
            "total_exams": len(graded_attempts),
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
        self, graded_attempts: list[TestAttempt]
    ) -> tuple[dict | None, dict | None]:
        subject_stats: dict[int, dict] = {}
        for attempt in graded_attempts:
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

    def _build_weak_topics(self, graded_attempt_ids: list[int]) -> list[dict]:
        rows = self.attempts.list_topic_weighted_rows_for_attempt_ids(
            attempt_ids=graded_attempt_ids
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

    def _build_recent_weak_topics_summary(
        self, recent_graded_attempt_ids: list[int]
    ) -> list[dict]:
        """
        Merge weak topics across recent graded attempts.

        Uses the same difficulty-weighted mastery and _classify thresholds as
        get_test_analytics. A topic counts once per attempt where it classified
        as NEEDS_IMPROVEMENT or WEAKNESS.
        """
        rows = self.attempts.list_topic_weighted_rows_grouped_by_attempt(
            attempt_ids=recent_graded_attempt_ids
        )
        # topic_id -> {name, scores: [mastery per weak occurrence]}
        merged: dict[int | None, dict] = {}
        for (
            _attempt_id,
            topic_id,
            topic_name,
            weighted_earned,
            weighted_possible,
        ) in rows:
            if weighted_possible <= 0:
                mastery = 0.0
            else:
                mastery = round((weighted_earned / weighted_possible) * 100, 2)
            if self._classify(mastery) not in _WEAK_TOPIC_CLASSIFICATIONS:
                continue
            entry = merged.get(topic_id)
            if entry is None:
                entry = {
                    "topic_id": topic_id,
                    "topic_name": topic_name or "General",
                    "scores": [],
                }
                merged[topic_id] = entry
            entry["scores"].append(mastery)

        weak_topics: list[dict] = []
        for entry in merged.values():
            scores = entry["scores"]
            weak_topics.append(
                {
                    "topic_id": entry["topic_id"],
                    "topic_name": entry["topic_name"],
                    "average_score": round(sum(scores) / len(scores), 2),
                    "occurrences": len(scores),
                }
            )

        # Weakest first; for ties, more frequent weakness first.
        weak_topics.sort(
            key=lambda item: (item["average_score"], -item["occurrences"])
        )
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
