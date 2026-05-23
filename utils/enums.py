import enum


class UserStatus(str, enum.Enum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DISABLED = "DISABLED"


class WorkspaceKind(str, enum.Enum):
    SOLO = "SOLO"
    INSTITUTION = "INSTITUTION"


class WorkspaceStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"


class MembershipStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REMOVED = "REMOVED"


class MembershipRole(str, enum.Enum):
    ADMIN = "ADMIN"
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"


class InviteStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class TestStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DRAFT = "DRAFT"
    ARCHIVED = "ARCHIVED"


class TestAttemptStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    GRADED = "GRADED"


class AvailabilityTimeMode(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    FLEXIBLE = "FLEXIBLE"


class QuestionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DRAFT = "DRAFT"
    ARCHIVED = "ARCHIVED"


class QuestionType(str, enum.Enum):
    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    TRUE_FALSE = "TRUE_FALSE"
    SHORT_TEXT = "SHORT_TEXT"
    ESSAY = "ESSAY"


class QuestionVisibility(str, enum.Enum):
    PLATFORM = "PLATFORM"
    WORKSPACE = "WORKSPACE"
    SUBJECT = "SUBJECT"


class Difficulty(str, enum.Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class ExamStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class ExamAttemptStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    GRADED = "GRADED"
    CANCELLED = "CANCELLED"


class WorkspaceSubscriptionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CANCELED = "CANCELED"
    TRIAL = "TRIAL"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELED = "CANCELED"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class BillingCycle(str, enum.Enum):
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class ProctoringEventType(str, enum.Enum):
    TAB_SWITCH = "TAB_SWITCH"
    WINDOW_BLUR = "WINDOW_BLUR"
    COPY_PASTE = "COPY_PASTE"
    FULLSCREEN_EXIT = "FULLSCREEN_EXIT"
    MULTIPLE_FACES = "MULTIPLE_FACES"
    NO_FACE = "NO_FACE"
    OTHER = "OTHER"


class NotificationType(str, enum.Enum):
    EXAM = "EXAM"
    INVITE = "INVITE"
    GRADING = "GRADING"
    SYSTEM = "SYSTEM"


# Seed reference lists (no roles/permissions tables per ERD)
MEMBERSHIP_ROLE_SEED = [r.value for r in MembershipRole]
QUESTION_TYPE_SEED = [t.value for t in QuestionType]
QUESTION_VISIBILITY_SEED = [v.value for v in QuestionVisibility]
