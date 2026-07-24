"""Institution admin workspace dashboard."""

from __future__ import annotations

from datetime import timedelta

from models import Membership, Workspace
from repositories.workspace_dashboard_repository import WorkspaceDashboardRepository
from repositories.workspace_repository import WorkspaceRepository
from service.exceptions import ForbiddenError, NotFoundError
from utils.app_timezone import ensure_local_aware, format_local_datetime, local_timezone_now
from utils.enums import WorkspaceKind
from utils.messages import Messages
from utils.rbac import can_manage_workspace_members


DEFAULT_RECENT_LIMIT = 5
DEFAULT_UPCOMING_LIMIT = 10
PERFORMANCE_TREND_DAYS = 30


class WorkspaceDashboardService:
    def __init__(self):
        self.workspaces = WorkspaceRepository()
        self.dashboard = WorkspaceDashboardRepository()

    def get_dashboard(
        self,
        workspace_id: int,
        actor_membership: Membership,
        *,
        recent_limit: int = DEFAULT_RECENT_LIMIT,
        upcoming_limit: int = DEFAULT_UPCOMING_LIMIT,
    ) -> dict:
        workspace = self._ensure_dashboard_access(workspace_id, actor_membership)
        now = local_timezone_now()
        since = now - timedelta(days=PERFORMANCE_TREND_DAYS)

        counts = self.dashboard.count_active_members_by_role(workspace.id)
        total_teachers = counts["teachers"]
        total_students = counts["students"]
        total_admins = counts["admins"]
        total_members = total_teachers + total_students + total_admins

        recent_subjects = [
            {
                "subject_id": item["subject"].id,
                "name": item["subject"].name,
                "created_at": format_local_datetime(item["subject"].created_at),
                "student_count": item["student_count"],
            }
            for item in self.dashboard.list_recent_subjects(
                workspace.id, limit=recent_limit
            )
        ]

        recent_members = []
        for membership, user in self.dashboard.list_recent_members(
            workspace.id, limit=recent_limit
        ):
            joined = membership.joined_at or membership.created_at
            recent_members.append(
                {
                    "user_id": user.id,
                    "membership_id": membership.id,
                    "full_name": user.full_name,
                    "role": membership.role,
                    "joined_at": format_local_datetime(joined),
                    "avatar_url": user.profile_image_url,
                    "profile_image_url": user.profile_image_url,
                }
            )

        recent_banks = [
            {
                "bank_id": item["bank"].id,
                "title": item["bank"].title,
                "updated_at": format_local_datetime(item["bank"].updated_at),
                "activity_source": "UPDATED",
                "question_count": item["question_count"],
            }
            for item in self.dashboard.list_recent_question_banks(
                workspace.id, limit=recent_limit
            )
        ]

        upcoming_tests = [
            self._serialize_upcoming_test(test)
            for test in self.dashboard.list_upcoming_tests(
                workspace.id, now=now, limit=upcoming_limit
            )
        ]

        return {
            "success": True,
            "overview": {
                "total_members": total_members,
                "total_teachers": total_teachers,
                "total_students": total_students,
                "total_admins": total_admins,
                "total_subjects": self.dashboard.count_subjects(workspace.id),
                "average_student_score": self.dashboard.average_graded_percentage(
                    workspace.id
                ),
                "most_enrolled_subject": self.dashboard.most_enrolled_subject(
                    workspace.id
                ),
            },
            "recent_subjects": recent_subjects,
            "recent_members": recent_members,
            "recent_question_banks": recent_banks,
            "upcoming_tests": upcoming_tests,
            "performance_trend": {
                "period": "LAST_30_DAYS",
                "metric": "percentage",
                "aggregation": "daily_mean_of_graded_attempts",
                "data": self.dashboard.graded_performance_trend(
                    workspace.id, since=since
                ),
            },
        }

    def _ensure_dashboard_access(
        self, workspace_id: int, actor_membership: Membership
    ) -> Workspace:
        """
        Dashboard is available to workspace owner or ADMIN for INSTITUTION and SOLO.

        Reuses the same authority model as member-management endpoints
        (``can_manage_workspace_members``). Workspace kind alone does not grant
        or deny access beyond supporting these two kinds.
        """
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError(Messages.WORKSPACE_NOT_FOUND)
        if workspace.kind not in (
            WorkspaceKind.INSTITUTION.value,
            WorkspaceKind.SOLO.value,
        ):
            raise ForbiddenError(Messages.UNSUPPORTED_WORKSPACE_TYPE_FOR_MEMBER_MANAGEMENT)
        if not can_manage_workspace_members(workspace, actor_membership):
            raise ForbiddenError(
                Messages.ONLY_THE_WORKSPACE_OWNER_OR_ADMIN_CAN_MANAGE_WORKSPACE_MEMBERS
            )
        return workspace

    @staticmethod
    def _serialize_upcoming_test(test) -> dict:
        subject = test.subject
        starts_at_date = None
        starts_at_time = None
        if test.starts_at is not None:
            local_at = ensure_local_aware(test.starts_at)
            starts_at_date = local_at.date().isoformat()
            starts_at_time = local_at.strftime("%H:%M")

        return {
            "test_id": test.id,
            "name": test.name,
            "subject_id": test.subject_id,
            "subject_name": subject.name if subject else None,
            "starts_at": format_local_datetime(test.starts_at),
            "starts_at_date": starts_at_date,
            "starts_at_time": starts_at_time,
            "exam_date": starts_at_date,
            "exam_time": starts_at_time,
            "closed_at": format_local_datetime(test.closed_at),
            "scheduled_publish_at": format_local_datetime(test.scheduled_publish_at),
            "status": test.status,
            "availability_time_mode": test.availability_time_mode,
        }
