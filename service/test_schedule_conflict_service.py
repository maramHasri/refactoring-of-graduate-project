from __future__ import annotations

from datetime import datetime, timedelta

from models import Test
from repositories.test_assignment_repository import TestStudentAssignmentRepository
from repositories.test_repository import TestRepository
from service.exceptions import ScheduleConflictError, TeacherScheduleConflictError
from utils.app_timezone import ensure_local_aware
from utils.enums import AvailabilityTimeMode, TestStatus


class TestScheduleConflictService:
    """Detect overlapping scheduled exams (student assignments and teacher ownership)."""

    _ACTIVE_CONFLICT_STATUSES = (
        TestStatus.SCHEDULED.value,
        TestStatus.PUBLISHED.value,
    )

    def __init__(self):
        self.tests = TestRepository()
        self.test_assignments = TestStudentAssignmentRepository()

    def requires_student_conflict_check(self, test: Test) -> bool:
        if test.status not in self._ACTIVE_CONFLICT_STATUSES:
            return False
        if test.archived_at is not None:
            return False
        return self._scheduled_window(test) is not None

    def requires_teacher_conflict_check(self, test: Test) -> bool:
        if test.status in (
            TestStatus.CLOSED.value,
            TestStatus.ARCHIVED.value,
        ):
            return False
        if test.archived_at is not None:
            return False
        if not test.created_by_membership_id:
            return False
        return self._scheduled_window(test) is not None

    def requires_conflict_check(self, test: Test) -> bool:
        """Backward-compatible alias for student conflict gating."""
        return self.requires_student_conflict_check(test)

    def ensure_no_teacher_conflict(
        self,
        *,
        test: Test,
        workspace_id: int,
    ) -> None:
        if not self.requires_teacher_conflict_check(test):
            return

        window = self._scheduled_window(test)
        if not window:
            return

        window_start, window_end = window
        conflicting_id = self.tests.find_conflicting_teacher_scheduled_test_id(
            workspace_id=workspace_id,
            teacher_membership_id=test.created_by_membership_id,
            window_start=window_start,
            window_end=window_end,
            exclude_test_id=test.id,
        )
        if conflicting_id is not None:
            raise TeacherScheduleConflictError(conflicting_id)

    def ensure_no_conflict(
        self,
        *,
        test: Test,
        workspace_id: int,
        student_membership_ids: list[int] | None = None,
    ) -> None:
        if not self.requires_student_conflict_check(test):
            return

        window = self._scheduled_window(test)
        if not window:
            return

        window_start, window_end = window
        affected_students = student_membership_ids
        if affected_students is None:
            affected_students = self.test_assignments.list_student_membership_ids_for_test(
                test.id
            )
        if not affected_students:
            return

        conflicting_ids = self.tests.find_conflicting_scheduled_test_ids(
            workspace_id=workspace_id,
            window_start=window_start,
            window_end=window_end,
            student_membership_ids=affected_students,
            exclude_test_id=test.id,
        )
        if conflicting_ids:
            raise ScheduleConflictError(conflicting_ids)

    def ensure_no_schedule_conflicts(
        self,
        *,
        test: Test,
        workspace_id: int,
        student_membership_ids: list[int] | None = None,
    ) -> None:
        """Run teacher and student schedule validations (independent rules)."""
        self.ensure_no_teacher_conflict(test=test, workspace_id=workspace_id)
        self.ensure_no_conflict(
            test=test,
            workspace_id=workspace_id,
            student_membership_ids=student_membership_ids,
        )

    def _scheduled_window(self, test: Test) -> tuple[datetime, datetime] | None:
        if self._is_flexible(test):
            return None
        if not test.starts_at or not test.duration_minutes:
            return None
        window_start = ensure_local_aware(test.starts_at)
        window_end = window_start + timedelta(minutes=int(test.duration_minutes))
        return window_start, window_end

    @staticmethod
    def _is_flexible(test: Test) -> bool:
        mode = (test.availability_time_mode or AvailabilityTimeMode.SCHEDULED.value).upper()
        return mode == AvailabilityTimeMode.FLEXIBLE.value

    @staticmethod
    def tests_overlap(
        *,
        start_a: datetime,
        end_a: datetime,
        start_b: datetime,
        end_b: datetime,
    ) -> bool:
        return start_a < end_b and end_a > start_b
