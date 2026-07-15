from utils.messages import Messages

class ServiceError(Exception):
    """Base application error with HTTP status code."""

    status_code = 400

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(ServiceError):
    status_code = 404


class UnauthorizedError(ServiceError):
    status_code = 401


class ForbiddenError(ServiceError):
    status_code = 403


class ConflictError(ServiceError):
    status_code = 409


class ScheduleConflictError(ConflictError):
    error_code = "SCHEDULE_CONFLICT"

    def __init__(self, conflicting_test_ids: list[int]):
        self.conflicting_test_ids = sorted({int(test_id) for test_id in conflicting_test_ids})
        super().__init__(
            Messages.THIS_EXAM_OVERLAPS_WITH_ANOTHER_SCHEDULED_EXAM_FOR_ONE_OR_MORE_STUDENTS
        )


class TeacherScheduleConflictError(ConflictError):
    error_code = "TEACHER_SCHEDULE_CONFLICT"

    def __init__(self, conflicting_test_id: int):
        self.conflicting_test_id = int(conflicting_test_id)
        super().__init__(
            Messages.THE_TEACHER_ALREADY_HAS_ANOTHER_SCHEDULED_EXAM_DURING_THIS_TIME
        )


class ValidationError(ServiceError):
    status_code = 422
