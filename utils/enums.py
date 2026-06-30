import enum


class UserStatus(str, enum.Enum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    REGISTRATION_REJECTED = "REGISTRATION_REJECTED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DISABLED = "DISABLED"


class InstitutionApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class WorkspaceKind(str, enum.Enum):
    SOLO = "SOLO"
    INSTITUTION = "INSTITUTION"


class WorkspaceStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"


class EmailOtpPurpose(str, enum.Enum):
    REGISTER_OWNER = "REGISTER_OWNER"
    VERIFY_ACCOUNT = "VERIFY_ACCOUNT"
    RESET_PASSWORD = "RESET_PASSWORD"


class MembershipStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REMOVED = "REMOVED"


class MembershipRole(str, enum.Enum):
    ADMIN = "ADMIN"
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"


class SubjectRole(str, enum.Enum):
    """Role on a specific subject (subject_memberships), not workspace membership."""

    TEACHER = "TEACHER"
    STUDENT = "STUDENT"


class SubjectMembershipStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    REMOVED = "REMOVED"


class QuestionBankVisibility(str, enum.Enum):
    PRIVATE = "PRIVATE"
    WORKSPACE = "WORKSPACE"
    COMMUNITY = "COMMUNITY"


class InviteStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class TestStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    PUBLISHED = "PUBLISHED"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class TestAttemptStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    GRADED = "GRADED"


class AttemptSubmissionSource(str, enum.Enum):
    """How an attempt was finalized."""

    STUDENT = "STUDENT"
    TIMEOUT = "TIMEOUT"
    FORCE = "FORCE"


class AnswerGradingStatus(str, enum.Enum):
    """Per-answer grading lifecycle."""

    AUTO_GRADED = "AUTO_GRADED"
    PENDING_REVIEW = "PENDING_REVIEW"
    MANUALLY_GRADED = "MANUALLY_GRADED"


class AttemptGradingAuditAction(str, enum.Enum):
    ATTEMPT_SUBMITTED = "ATTEMPT_SUBMITTED"
    AUTO_GRADING_COMPLETED = "AUTO_GRADING_COMPLETED"
    MANUAL_GRADING_STARTED = "MANUAL_GRADING_STARTED"
    MANUAL_GRADING_COMPLETED = "MANUAL_GRADING_COMPLETED"
    ATTEMPT_FULLY_GRADED = "ATTEMPT_FULLY_GRADED"
    GRADING_NOTIFICATION_SENT = "GRADING_NOTIFICATION_SENT"


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


class TestQuestionSourceType(str, enum.Enum):
    AI = "AI"
    QUESTION_BANK = "QUESTION_BANK"
    RANDOM_FROM_BANK = "RANDOM_FROM_BANK"
    MANUAL = "MANUAL"
    IMPORT = "IMPORT"


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
    STUDENT_JOINED = "STUDENT_JOINED"
    SESSION_STARTED = "SESSION_STARTED"
    FACE_DETECTED = "FACE_DETECTED"
    FACE_LOST = "FACE_LOST"
    NO_FACE = "NO_FACE"
    MULTIPLE_FACES = "MULTIPLE_FACES"
    TAB_SWITCH = "TAB_SWITCH"
    WINDOW_BLUR = "WINDOW_BLUR"
    COPY_PASTE = "COPY_PASTE"
    FULLSCREEN_EXIT = "FULLSCREEN_EXIT"
    CAMERA_STATUS = "CAMERA_STATUS"
    MICROPHONE_ACTIVITY = "MICROPHONE_ACTIVITY"
    SCREEN_INACTIVITY = "SCREEN_INACTIVITY"
    SUSPICIOUS_NAVIGATION = "SUSPICIOUS_NAVIGATION"
    AUDIO_ANOMALY = "AUDIO_ANOMALY"
    WARNING_GENERATED = "WARNING_GENERATED"
    VIOLATION_TRIGGERED = "VIOLATION_TRIGGERED"
    SESSION_TERMINATED = "SESSION_TERMINATED"
    OTHER = "OTHER"


class ProctoringSessionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    TERMINATED = "TERMINATED"
    COMPLETED = "COMPLETED"


class ViolationSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ProctoringViolationType(str, enum.Enum):
    TAB_SWITCH = "TAB_SWITCH"
    FACE_NOT_DETECTED = "FACE_NOT_DETECTED"
    MULTIPLE_FACES = "MULTIPLE_FACES"
    AUDIO_ANOMALY = "AUDIO_ANOMALY"
    SCREEN_INACTIVITY = "SCREEN_INACTIVITY"
    SUSPICIOUS_NAVIGATION = "SUSPICIOUS_NAVIGATION"
    FULLSCREEN_EXIT = "FULLSCREEN_EXIT"
    COPY_PASTE = "COPY_PASTE"
    OTHER = "OTHER"


class ProctoringViolationStatus(str, enum.Enum):
    OPEN = "OPEN"
    REVIEWED = "REVIEWED"
    DISMISSED = "DISMISSED"
    CONFIRMED = "CONFIRMED"


class ProctoringAuditAction(str, enum.Enum):
    SESSION_STARTED = "SESSION_STARTED"
    SESSION_TERMINATED = "SESSION_TERMINATED"
    EVENT_INGESTED = "EVENT_INGESTED"
    VIOLATION_CREATED = "VIOLATION_CREATED"
    EVIDENCE_GENERATED = "EVIDENCE_GENERATED"
    VIOLATION_REVIEWED = "VIOLATION_REVIEWED"
    WARNING_GENERATED = "WARNING_GENERATED"


class NotificationType(str, enum.Enum):
    EXAM = "EXAM"
    INVITE = "INVITE"
    GRADING = "GRADING"
    SYSTEM = "SYSTEM"


# Seed reference lists (no roles/permissions tables per ERD)
MEMBERSHIP_ROLE_SEED = [r.value for r in MembershipRole]
QUESTION_TYPE_SEED = [t.value for t in QuestionType]
QUESTION_VISIBILITY_SEED = [v.value for v in QuestionVisibility]
