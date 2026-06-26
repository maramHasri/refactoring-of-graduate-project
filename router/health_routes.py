from flask import Blueprint, jsonify

from utils.db import db
from utils.enums import (
    MEMBERSHIP_ROLE_SEED,
    QUESTION_TYPE_SEED,
    QUESTION_VISIBILITY_SEED,
    UserStatus,
    WorkspaceKind,
    WorkspaceStatus,
    MembershipRole,
    MembershipStatus,
    InviteStatus,
    TestStatus,
    TestAttemptStatus,
    AttemptSubmissionSource,
    AvailabilityTimeMode,
    ProctoringAuditAction,
    ProctoringEventType,
    ProctoringSessionStatus,
    ProctoringViolationStatus,
    ProctoringViolationType,
    ViolationSeverity,
    TestQuestionSourceType,
    QuestionStatus,
    WorkspaceSubscriptionStatus,
    SubscriptionStatus,
    PaymentStatus,
    BillingCycle,
)

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "edu_forms"})


@health_bp.route("/api/enums", methods=["GET"])
def list_enums():
    return jsonify(
        {
            "membership_roles": MEMBERSHIP_ROLE_SEED,
            "question_types": QUESTION_TYPE_SEED,
            "question_visibility": QUESTION_VISIBILITY_SEED,
            "user_status": [s.value for s in UserStatus],
            "workspace_kind": [k.value for k in WorkspaceKind],
            "workspace_status": [s.value for s in WorkspaceStatus],
            "membership_role": [r.value for r in MembershipRole],
            "membership_status": [s.value for s in MembershipStatus],
            "invite_status": [s.value for s in InviteStatus],
            "test_status": [s.value for s in TestStatus],
            "test_attempt_status": [s.value for s in TestAttemptStatus],
            "attempt_submission_source": [s.value for s in AttemptSubmissionSource],
            "proctoring_event_type": [e.value for e in ProctoringEventType],
            "proctoring_session_status": [s.value for s in ProctoringSessionStatus],
            "violation_severity": [s.value for s in ViolationSeverity],
            "proctoring_violation_type": [t.value for t in ProctoringViolationType],
            "proctoring_violation_status": [s.value for s in ProctoringViolationStatus],
            "proctoring_audit_action": [a.value for a in ProctoringAuditAction],
            "availability_time_mode": [m.value for m in AvailabilityTimeMode],
            "test_question_source_type": [s.value for s in TestQuestionSourceType],
            "question_status": [s.value for s in QuestionStatus],
            "workspace_subscription_status": [s.value for s in WorkspaceSubscriptionStatus],
            "subscription_status": [s.value for s in SubscriptionStatus],
            "payment_status": [s.value for s in PaymentStatus],
            "billing_cycle": [c.value for c in BillingCycle],
        }
    )


@health_bp.route("/health/db", methods=["GET"])
def health_db():
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify({"database": "connected"})
    except Exception as exc:
        return jsonify({"database": "error", "detail": str(exc)}), 503
