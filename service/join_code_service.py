"""
Join codes: permanent workspace-level codes for STUDENT onboarding only.
"""
from models import Membership
from repositories.workspace_repository import MembershipRepository, WorkspaceRepository
from service.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from utils.db import db
from utils.enums import MembershipRole


class JoinCodeService:
    def __init__(self):
        self.workspaces = WorkspaceRepository()
        self.memberships = MembershipRepository()

    def join_workspace_with_code(self, *, user_id: int, join_code: str) -> Membership:
        """
        Purpose: Existing user joins workspace as STUDENT.
        Must NOT: create admins/teachers or create workspaces.
        """
        workspace = self.workspaces.find_by_join_code(join_code)
        if not workspace:
            raise NotFoundError("Invalid join code")

        existing = self.memberships.find_by_user_and_workspace(user_id, workspace.id)
        if existing:
            raise ConflictError("Already a member of this workspace")

        membership = Membership(
            user_id=user_id,
            workspace_id=workspace.id,
            role=MembershipRole.STUDENT.value,
            status="ACTIVE",
        )
        self.memberships.add(membership)
        db.session.commit()
        return membership
