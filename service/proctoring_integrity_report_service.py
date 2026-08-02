"""Persisted Proctoring Integrity Reports (academic integrity inbox).

Created only on PROCTORING_AUTO termination. Independent from Support Reports.
Reuses ProctoringRiskService + ProctoringService.build_integrity_recommendation.
"""

from __future__ import annotations

import logging
from datetime import datetime

from models import Membership, ProctoringIntegrityReport, Test, TestAttempt, Workspace
from repositories.proctoring_integrity_report_repository import (
    ProctoringIntegrityReportRepository,
)
from repositories.proctoring_repository import (
    ProctoringAuditLogRepository,
    ProctoringSessionRepository,
    ProctoringViolationRepository,
)
from repositories.test_repository import TestQuestionRepository, TestRepository
from repositories.workspace_repository import MembershipRepository, WorkspaceRepository
from service.exam_grading_service import ExamGradingService
from service.exceptions import ForbiddenError, NotFoundError, ValidationError
from service.proctoring_risk_service import ProctoringRiskService
from utils.app_timezone import format_local_datetime, local_timezone_now
from utils.db import db
from utils.enums import (
    AttemptSubmissionSource,
    ProctoringAuditAction,
    ProctoringIntegrityReportStatus,
    WorkspaceKind,
)
from utils.messages import Messages
from utils.pagination import build_pagination_meta, normalize_pagination
from utils.rbac import is_workspace_owner

logger = logging.getLogger(__name__)


class ProctoringIntegrityReportService:
    def __init__(self):
        self.reports = ProctoringIntegrityReportRepository()
        self.sessions = ProctoringSessionRepository()
        self.violations = ProctoringViolationRepository()
        self.audit_logs = ProctoringAuditLogRepository()
        self.tests = TestRepository()
        self.test_questions = TestQuestionRepository()
        self.workspaces = WorkspaceRepository()
        self.memberships = MembershipRepository()
        self.risk = ProctoringRiskService()
        self.grading = ExamGradingService()

    def create_for_proctoring_auto(
        self,
        *,
        attempt: TestAttempt,
        test: Test,
        commit: bool = True,
    ) -> ProctoringIntegrityReport | None:
        """
        Idempotent create after a successful PROCTORING_AUTO finalization.

        Returns existing row if one already exists for the attempt.
        """
        if (
            (attempt.submission_source or "").upper()
            != AttemptSubmissionSource.PROCTORING_AUTO.value
        ):
            return None

        existing = self.reports.get_by_attempt_id(attempt.id)
        if existing:
            return existing

        from models import ProctoringAuditLog
        from service.proctoring_service import ProctoringService

        session = self.sessions.get_by_attempt_id(attempt.id)
        workspace = self._resolve_workspace(attempt, test, session)
        if workspace is None:
            logger.error(
                "Skipping integrity report — workspace unresolved attempt_id=%s",
                attempt.id,
            )
            return None

        violations = (
            self.violations.list_for_session(session.id) if session is not None else []
        )
        question_count = len(self.test_questions.list_active_for_test(test.id))
        risk = self.risk.calculate(
            attempt=attempt,
            test=test,
            violations=violations,
            question_count=question_count,
        )
        recommendation = ProctoringService.build_integrity_recommendation(
            attempt=attempt, risk=risk
        )

        teacher_membership = None
        teacher_name = None
        if test.created_by_membership_id:
            teacher_membership = self.memberships.get_by_id(
                test.created_by_membership_id
            )
            if teacher_membership and teacher_membership.user:
                teacher_name = teacher_membership.user.full_name

        student_name = ""
        if attempt.user is not None and attempt.user.full_name:
            student_name = attempt.user.full_name
        elif attempt.student_membership and attempt.student_membership.user:
            student_name = attempt.student_membership.user.full_name or ""

        subject = test.subject
        terminated_at = attempt.submitted_at or local_timezone_now()

        report = ProctoringIntegrityReport(
            attempt_id=attempt.id,
            test_id=test.id,
            subject_id=test.subject_id,
            workspace_id=workspace.id,
            teacher_membership_id=test.created_by_membership_id,
            student_membership_id=attempt.student_membership_id,
            proctoring_session_id=session.id if session else None,
            student_name=student_name or "Unknown student",
            teacher_name=teacher_name,
            subject_name=subject.name if subject else None,
            test_name=test.name or "",
            workspace_name=workspace.name or "",
            risk_percentage=float(risk["proctoring_risk_percentage"]),
            effective_violation_score=int(risk["effective_violation_score"]),
            violations_count=int(risk["violations_count"]),
            high_severity_count=int(risk["high_severity_count"]),
            medium_severity_count=int(risk["medium_severity_count"]),
            low_severity_count=int(risk["low_severity_count"]),
            final_score=attempt.final_score,
            raw_score=attempt.raw_score,
            maximum_score=self.grading.maximum_score(test),
            started_at=attempt.started_at,
            submitted_at=attempt.submitted_at,
            terminated_at=terminated_at,
            submission_source=AttemptSubmissionSource.PROCTORING_AUTO.value,
            termination_reason=attempt.termination_reason,
            recommendation=recommendation["status"],
            recommendation_reason=recommendation.get("reason"),
            status=ProctoringIntegrityReportStatus.PENDING.value,
        )
        self.reports.add(report)
        db.session.flush()

        if session is not None:
            self.audit_logs.add(
                ProctoringAuditLog(
                    session_id=session.id,
                    action=ProctoringAuditAction.INTEGRITY_REPORT_CREATED.value,
                    actor_user_id=None,
                    actor_membership_id=None,
                    details={
                        "integrity_report_id": report.id,
                        "attempt_id": attempt.id,
                        "test_id": test.id,
                        "submission_source": AttemptSubmissionSource.PROCTORING_AUTO.value,
                        "termination_reason": attempt.termination_reason,
                        "risk_percentage": report.risk_percentage,
                        "recommendation": report.recommendation,
                    },
                )
            )

        if commit:
            db.session.commit()
        return report

    def list_reports(
        self,
        *,
        workspace_id: int,
        actor_membership: Membership,
        page: int | None = None,
        per_page: int | None = None,
        status: str | None = None,
        test_id: int | None = None,
        subject_id: int | None = None,
        student_membership_id: int | None = None,
        search: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict:
        page, per_page, offset = normalize_pagination(page, per_page)
        workspace = self._get_workspace_or_404(workspace_id)
        viewer_is_owner = self._viewer_is_owner(workspace, actor_membership)
        self._ensure_list_access(workspace, actor_membership, viewer_is_owner)

        rows, total = self.reports.list_for_viewer(
            workspace_id=workspace.id,
            viewer_is_owner=viewer_is_owner,
            viewer_membership_id=actor_membership.id,
            status=status,
            test_id=test_id,
            subject_id=subject_id,
            student_membership_id=student_membership_id,
            search=search,
            date_from=date_from,
            date_to=date_to,
            offset=offset,
            limit=per_page,
        )
        return {
            "reports": [self._serialize_summary(row) for row in rows],
            **build_pagination_meta(total=total, page=page, per_page=per_page),
        }

    def get_report(
        self,
        *,
        report_id: int,
        workspace_id: int,
        actor_membership: Membership,
    ) -> dict:
        report = self._get_accessible_report(
            report_id, workspace_id, actor_membership
        )
        return self._serialize_detail(report)

    def review_report(
        self,
        *,
        report_id: int,
        workspace_id: int,
        actor_membership: Membership,
        status: str,
        review_note: str | None = None,
    ) -> dict:
        if status not in (
            ProctoringIntegrityReportStatus.CONFIRMED.value,
            ProctoringIntegrityReportStatus.DISMISSED.value,
        ):
            raise ValidationError(Messages.INVALID_INTEGRITY_REPORT_REVIEW_STATUS)

        report = self._get_accessible_report(
            report_id, workspace_id, actor_membership
        )
        report.status = status
        report.reviewed_by_membership_id = actor_membership.id
        report.reviewed_at = local_timezone_now()
        report.review_note = (review_note or "").strip() or None
        db.session.commit()
        return {
            "message": Messages.INTEGRITY_REPORT_STATUS_UPDATED_SUCCESSFULLY,
            "report": self._serialize_detail(report),
        }

    def _get_accessible_report(
        self,
        report_id: int,
        workspace_id: int,
        actor_membership: Membership,
    ) -> ProctoringIntegrityReport:
        report = self.reports.get_by_id(report_id)
        if not report or report.workspace_id != workspace_id:
            raise NotFoundError(Messages.INTEGRITY_REPORT_NOT_FOUND)
        workspace = self._get_workspace_or_404(workspace_id)
        if not self._can_view_report(workspace, actor_membership, report):
            raise ForbiddenError(
                Messages.INSUFFICIENT_PERMISSIONS_FOR_INTEGRITY_REPORTS
            )
        return report

    def _can_view_report(
        self,
        workspace: Workspace,
        actor: Membership,
        report: ProctoringIntegrityReport,
    ) -> bool:
        if is_workspace_owner(workspace, actor):
            return True
        if workspace.kind == WorkspaceKind.SOLO.value:
            return False
        return report.teacher_membership_id == actor.id

    def _ensure_list_access(
        self,
        workspace: Workspace,
        actor: Membership,
        viewer_is_owner: bool,
    ) -> None:
        from utils.enums import MembershipRole

        if viewer_is_owner:
            return
        if workspace.kind == WorkspaceKind.SOLO.value:
            raise ForbiddenError(
                Messages.INSUFFICIENT_PERMISSIONS_FOR_INTEGRITY_REPORTS
            )
        if actor.role == MembershipRole.STUDENT.value:
            raise ForbiddenError(
                Messages.INSUFFICIENT_PERMISSIONS_FOR_INTEGRITY_REPORTS
            )
        # INSTITUTION teacher/admin who is not owner: list filtered to own tests.

    def _viewer_is_owner(self, workspace: Workspace, actor: Membership) -> bool:
        return is_workspace_owner(workspace, actor)

    def _get_workspace_or_404(self, workspace_id: int) -> Workspace:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError(Messages.WORKSPACE_NOT_FOUND)
        return workspace

    def _resolve_workspace(
        self, attempt: TestAttempt, test: Test, session
    ) -> Workspace | None:
        if session is not None:
            workspace = self.workspaces.get_by_id(session.workspace_id)
            if workspace:
                return workspace
        membership = attempt.student_membership or self.memberships.get_by_id(
            attempt.student_membership_id
        )
        if membership:
            return self.workspaces.get_by_id(membership.workspace_id)
        if test.created_by_membership_id:
            creator = self.memberships.get_by_id(test.created_by_membership_id)
            if creator:
                return self.workspaces.get_by_id(creator.workspace_id)
        return None

    def _serialize_summary(self, report: ProctoringIntegrityReport) -> dict:
        return {
            "id": report.id,
            "attempt_id": report.attempt_id,
            "test_id": report.test_id,
            "subject_id": report.subject_id,
            "workspace_id": report.workspace_id,
            "teacher_membership_id": report.teacher_membership_id,
            "student_membership_id": report.student_membership_id,
            "student_name": report.student_name,
            "teacher_name": report.teacher_name,
            "subject_name": report.subject_name,
            "test_name": report.test_name,
            "risk_percentage": report.risk_percentage,
            "violations_count": report.violations_count,
            "recommendation": report.recommendation,
            "termination_reason": report.termination_reason,
            "status": report.status,
            "submitted_at": format_local_datetime(report.submitted_at),
            "terminated_at": format_local_datetime(report.terminated_at),
            "created_at": format_local_datetime(report.created_at),
        }

    def _serialize_detail(self, report: ProctoringIntegrityReport) -> dict:
        return {
            **self._serialize_summary(report),
            "proctoring_session_id": report.proctoring_session_id,
            "workspace_name": report.workspace_name,
            "effective_violation_score": report.effective_violation_score,
            "high_severity_count": report.high_severity_count,
            "medium_severity_count": report.medium_severity_count,
            "low_severity_count": report.low_severity_count,
            "final_score": report.final_score,
            "raw_score": report.raw_score,
            "maximum_score": report.maximum_score,
            "started_at": format_local_datetime(report.started_at),
            "submission_source": report.submission_source,
            "recommendation_reason": report.recommendation_reason,
            "reviewed_by": report.reviewed_by_membership_id,
            "reviewed_at": format_local_datetime(report.reviewed_at),
            "review_note": report.review_note,
            "updated_at": format_local_datetime(report.updated_at),
        }
