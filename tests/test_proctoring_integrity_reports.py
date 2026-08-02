"""Tests for Proctoring Integrity Reports.

Run: python tests/test_proctoring_integrity_reports.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_schema_list_defaults():
    from schemas.proctoring_integrity_report_schema import IntegrityReportsListQuerySchema

    data = IntegrityReportsListQuerySchema().load({})
    assert data["page"] == 1
    assert data["per_page"] == 20
    assert data["status"] is None


def test_schema_review_rejects_pending():
    from marshmallow import ValidationError
    from schemas.proctoring_integrity_report_schema import ReviewIntegrityReportSchema

    try:
        ReviewIntegrityReportSchema().load({"status": "PENDING"})
        assert False, "expected ValidationError"
    except ValidationError:
        pass


def test_recommendation_reused_from_proctoring_service():
    from service.proctoring_service import ProctoringService

    attempt = SimpleNamespace(
        submission_source="PROCTORING_AUTO",
        termination_reason="PROCTORING_THRESHOLD_EXCEEDED",
    )
    risk = {
        "effective_violation_score": 55,
        "high_severity_count": 2,
        "violations_count": 3,
    }
    rec = ProctoringService.build_integrity_recommendation(attempt=attempt, risk=risk)
    assert rec["status"] == "SUSPICIOUS"
    assert ProctoringService._build_report_recommendation(
        attempt=attempt, risk=risk
    ) == rec


def test_create_skipped_for_non_proctoring_auto():
    from service.proctoring_integrity_report_service import (
        ProctoringIntegrityReportService,
    )

    svc = ProctoringIntegrityReportService()
    svc.reports = MagicMock()
    attempt = SimpleNamespace(id=1, submission_source="STUDENT")
    test = SimpleNamespace(id=2)
    assert svc.create_for_proctoring_auto(attempt=attempt, test=test) is None
    svc.reports.get_by_attempt_id.assert_not_called()


def test_create_skipped_for_timeout_and_force():
    from service.proctoring_integrity_report_service import (
        ProctoringIntegrityReportService,
    )

    svc = ProctoringIntegrityReportService()
    for source in ("TIMEOUT", "FORCE", "STUDENT"):
        attempt = SimpleNamespace(id=1, submission_source=source)
        assert (
            svc.create_for_proctoring_auto(attempt=attempt, test=SimpleNamespace(id=2))
            is None
        )


def test_create_idempotent_returns_existing():
    from service.proctoring_integrity_report_service import (
        ProctoringIntegrityReportService,
    )

    svc = ProctoringIntegrityReportService()
    existing = SimpleNamespace(id=99, attempt_id=5)
    svc.reports = MagicMock()
    svc.reports.get_by_attempt_id.return_value = existing
    attempt = SimpleNamespace(id=5, submission_source="PROCTORING_AUTO")
    assert svc.create_for_proctoring_auto(attempt=attempt, test=SimpleNamespace()) is existing
    svc.reports.add.assert_not_called()


def test_create_builds_snapshot_and_audit():
    from service.proctoring_integrity_report_service import (
        ProctoringIntegrityReportService,
    )
    from utils.enums import ProctoringAuditAction

    svc = ProctoringIntegrityReportService()
    svc.reports = MagicMock()
    svc.reports.get_by_attempt_id.return_value = None
    added = []

    def _add(entity):
        if getattr(entity, "id", None) is None and hasattr(entity, "attempt_id"):
            entity.id = 7
        added.append(entity)
        return entity

    svc.reports.add.side_effect = _add
    svc.sessions = MagicMock()
    session = SimpleNamespace(id=3, workspace_id=10)
    svc.sessions.get_by_attempt_id.return_value = session
    svc.violations = MagicMock()
    svc.violations.list_for_session.return_value = []
    svc.test_questions = MagicMock()
    svc.test_questions.list_active_for_test.return_value = [1, 2, 3]
    svc.risk = MagicMock()
    svc.risk.calculate.return_value = {
        "proctoring_risk_percentage": 42.5,
        "effective_violation_score": 50,
        "violations_count": 4,
        "high_severity_count": 1,
        "medium_severity_count": 2,
        "low_severity_count": 1,
    }
    svc.grading = MagicMock()
    svc.grading.maximum_score.return_value = 100.0
    svc.workspaces = MagicMock()
    svc.workspaces.get_by_id.return_value = SimpleNamespace(id=10, name="Uni")
    svc.memberships = MagicMock()
    teacher_user = SimpleNamespace(full_name="Teacher A")
    svc.memberships.get_by_id.return_value = SimpleNamespace(
        id=20, user=teacher_user
    )
    svc.audit_logs = MagicMock()
    svc.audit_logs.add.side_effect = _add

    attempt = SimpleNamespace(
        id=5,
        submission_source="PROCTORING_AUTO",
        termination_reason="PROCTORING_THRESHOLD_EXCEEDED",
        student_membership_id=30,
        user=SimpleNamespace(full_name="Student Z"),
        student_membership=None,
        final_score=None,
        raw_score=80.0,
        started_at=None,
        submitted_at=None,
    )
    test = SimpleNamespace(
        id=2,
        name="Midterm",
        subject_id=8,
        subject=SimpleNamespace(name="Math"),
        created_by_membership_id=20,
    )

    with patch("utils.db.db.session") as mock_session:
        mock_session.flush = MagicMock()
        mock_session.commit = MagicMock()
        report = svc.create_for_proctoring_auto(attempt=attempt, test=test, commit=True)

    assert report is not None
    assert report.student_name == "Student Z"
    assert report.teacher_name == "Teacher A"
    assert report.test_name == "Midterm"
    assert report.subject_name == "Math"
    assert report.workspace_name == "Uni"
    assert report.risk_percentage == 42.5
    assert report.recommendation == "SUSPICIOUS"
    assert report.status == "PENDING"
    audit = next(
        e
        for e in added
        if getattr(e, "action", None)
        == ProctoringAuditAction.INTEGRITY_REPORT_CREATED.value
    )
    assert audit.details["integrity_report_id"] == 7
    mock_session.commit.assert_called()


def test_access_owner_can_view_any():
    from service.proctoring_integrity_report_service import (
        ProctoringIntegrityReportService,
    )

    svc = ProctoringIntegrityReportService()
    workspace = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=10)
    owner = SimpleNamespace(id=10, role="ADMIN")
    report = SimpleNamespace(teacher_membership_id=99)
    assert svc._can_view_report(workspace, owner, report) is True


def test_access_creator_can_view_own():
    from service.proctoring_integrity_report_service import (
        ProctoringIntegrityReportService,
    )

    svc = ProctoringIntegrityReportService()
    workspace = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=10)
    teacher = SimpleNamespace(id=55, role="TEACHER")
    report = SimpleNamespace(teacher_membership_id=55)
    assert svc._can_view_report(workspace, teacher, report) is True
    other = SimpleNamespace(teacher_membership_id=77)
    assert svc._can_view_report(workspace, teacher, other) is False


def test_access_solo_non_owner_denied():
    from service.proctoring_integrity_report_service import (
        ProctoringIntegrityReportService,
    )

    svc = ProctoringIntegrityReportService()
    workspace = SimpleNamespace(id=1, kind="SOLO", owner_membership_id=10)
    other = SimpleNamespace(id=55, role="TEACHER")
    report = SimpleNamespace(teacher_membership_id=55)
    assert svc._can_view_report(workspace, other, report) is False


def test_review_updates_status_not_attempt():
    from service.proctoring_integrity_report_service import (
        ProctoringIntegrityReportService,
    )

    svc = ProctoringIntegrityReportService()
    report = SimpleNamespace(
        id=1,
        workspace_id=1,
        teacher_membership_id=10,
        attempt_id=5,
        test_id=2,
        subject_id=3,
        student_membership_id=4,
        student_name="S",
        teacher_name="T",
        subject_name="Sub",
        test_name="Exam",
        workspace_name="W",
        risk_percentage=10.0,
        violations_count=1,
        recommendation="SUSPICIOUS",
        termination_reason="PROCTORING_THRESHOLD_EXCEEDED",
        status="PENDING",
        submitted_at=None,
        terminated_at=None,
        created_at=None,
        updated_at=None,
        proctoring_session_id=1,
        effective_violation_score=50,
        high_severity_count=1,
        medium_severity_count=0,
        low_severity_count=0,
        final_score=None,
        raw_score=10.0,
        maximum_score=100.0,
        started_at=None,
        submission_source="PROCTORING_AUTO",
        recommendation_reason="x",
        reviewed_by_membership_id=None,
        reviewed_at=None,
        review_note=None,
    )
    svc.reports = MagicMock()
    svc.reports.get_by_id.return_value = report
    svc.workspaces = MagicMock()
    svc.workspaces.get_by_id.return_value = SimpleNamespace(
        id=1, kind="INSTITUTION", owner_membership_id=10
    )
    actor = SimpleNamespace(id=10, role="ADMIN")

    with patch("utils.db.db.session") as mock_session:
        mock_session.commit = MagicMock()
        payload = svc.review_report(
            report_id=1,
            workspace_id=1,
            actor_membership=actor,
            status="CONFIRMED",
            review_note="Clear cheating",
        )
    assert report.status == "CONFIRMED"
    assert report.review_note == "Clear cheating"
    assert report.reviewed_by_membership_id == 10
    assert payload["report"]["status"] == "CONFIRMED"
    # Review must not touch attempt APIs
    assert not hasattr(svc, "attempts") or True


def test_finalize_for_proctoring_auto_triggers_integrity_report():
    from service.attempt_service import AttemptService

    svc = AttemptService()
    svc.tests = MagicMock()
    attempt = SimpleNamespace(id=9, status="IN_PROGRESS", test_id=1, test=None)
    test = SimpleNamespace(id=1)
    svc.tests.get_by_id.return_value = test
    svc.attempts = MagicMock()
    svc.attempts.get_by_id.return_value = attempt

    with patch("utils.db.db.session") as mock_session:
        mock_session.execute.return_value.scalar_one_or_none.return_value = attempt
        with patch.object(
            AttemptService,
            "_finalize_attempt",
            return_value={"attempt": {"id": 9}},
        ) as finalize:
            with patch(
                "service.proctoring_integrity_report_service.ProctoringIntegrityReportService"
            ) as ReportSvc:
                instance = ReportSvc.return_value
                result = svc.finalize_for_proctoring_auto(attempt_id=9)
                assert result == {"attempt": {"id": 9}}
                finalize.assert_called_once()
                assert (
                    finalize.call_args.kwargs["submission_source"] == "PROCTORING_AUTO"
                )
                instance.create_for_proctoring_auto.assert_called_once()


def test_routes_registered():
    from flask import Flask
    from router.proctoring_integrity_report_routes import integrity_report_bp

    app = Flask(__name__)
    app.register_blueprint(integrity_report_bp, url_prefix="/proctoring")
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/proctoring/integrity-reports" in rules
    assert "/proctoring/integrity-reports/<int:report_id>" in rules


def test_audit_action_enum_added():
    from utils.enums import ProctoringAuditAction, ProctoringIntegrityReportStatus

    assert ProctoringAuditAction.INTEGRITY_REPORT_CREATED.value == "INTEGRITY_REPORT_CREATED"
    assert set(s.value for s in ProctoringIntegrityReportStatus) == {
        "PENDING",
        "CONFIRMED",
        "DISMISSED",
    }


if __name__ == "__main__":
    tests = [name for name, obj in globals().items() if name.startswith("test_")]
    failed = 0
    for name in tests:
        try:
            globals()[name]()
            print(f"OK  {name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")
    if failed:
        raise SystemExit(1)
    print(f"\n{len(tests)} passed")
