"""
Workspace business logic.

Owner vs admin:
- owner_membership_id identifies the privileged admin (owner is NOT a separate role).
- Owner can delete workspace, transfer ownership, remove admins.
- Regular admins cannot remove other admins.
"""
import re

from models import Membership, Workspace
from repositories.workspace_repository import MembershipRepository, WorkspaceRepository
from service.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from utils.db import db
from utils.enums import MembershipRole, WorkspaceKind
from utils.join_code import generate_workspace_join_code


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:100] or "workspace"


class WorkspaceService:
    def __init__(self):
        self.workspaces = WorkspaceRepository()
        self.memberships = MembershipRepository()

    def create_workspace(
        self,
        *,
        user_id: int,
        name: str,
        kind: str,
        slug: str | None = None,
    ) -> dict:
        """
        Purpose: Authenticated user creates a new workspace (owner onboarding).
        Side effects: workspace, ADMIN membership, owner_membership_id, join_code.
        """
        if kind not in (WorkspaceKind.SOLO.value, WorkspaceKind.INSTITUTION.value):
            raise ValidationError("Invalid workspace kind")

        slug = slug or _slugify(name)
        if self.workspaces.find_by_slug(slug):
            raise ConflictError("Workspace slug already exists")

        workspace = Workspace(
            name=name,
            slug=slug,
            kind=kind,
            owner_user_id=user_id,
            join_code=self._unique_join_code(),
        )
        self.workspaces.add(workspace)
        db.session.flush()

        membership = Membership(
            user_id=user_id,
            workspace_id=workspace.id,
            role=MembershipRole.ADMIN.value,
            status="ACTIVE",
        )
        self.memberships.add(membership)
        db.session.flush()

        workspace.owner_membership_id = membership.id
        db.session.commit()

        return {
            "workspace_id": workspace.id,
            "membership_id": membership.id,
            "join_code": workspace.join_code,
        }

    def list_accessible_workspaces(self, user_id: int, *, is_superadmin: bool) -> list[dict]:
        """
        Purpose: Return workspaces after login for workspace picker.
        Must NOT: mutate state.
        """
        if is_superadmin:
            rows = db.session.execute(db.select(Workspace).order_by(Workspace.name)).scalars().all()
            return [self._serialize_workspace(w, role="SUPERADMIN", membership_id=None) for w in rows]

        workspaces = self.workspaces.list_for_user(user_id)
        result = []
        for ws in workspaces:
            m = self.memberships.find_by_user_and_workspace(user_id, ws.id)
            result.append(
                self._serialize_workspace(
                    ws,
                    role=m.role if m else None,
                    membership_id=m.id if m else None,
                )
            )
        return result

    def get_workspace(self, workspace_id: int, actor_user_id: int, *, is_superadmin: bool) -> dict:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found")
        if not is_superadmin:
            m = self.memberships.find_by_user_and_workspace(actor_user_id, workspace_id)
            if not m or m.status != "ACTIVE":
                raise ForbiddenError("Not a member of this workspace")
        return self._serialize_workspace_detail(workspace)

    def update_workspace(
        self,
        workspace_id: int,
        actor_user_id: int,
        *,
        is_superadmin: bool,
        data: dict,
    ) -> Workspace:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found")

        if not is_superadmin:
            m = self.memberships.find_by_user_and_workspace(actor_user_id, workspace_id)
            if not m or m.role not in (
                MembershipRole.ADMIN.value,
            ):
                raise ForbiddenError("Admin access required")

        for field in ("name", "slug", "status", "subject_assignment_mode"):
            if field in data and data[field] is not None:
                setattr(workspace, field, data[field])

        if "slug" in data and data["slug"]:
            existing = self.workspaces.find_by_slug(data["slug"])
            if existing and existing.id != workspace.id:
                raise ConflictError("Slug already in use")

        db.session.commit()
        return workspace

    def delete_workspace(
        self, workspace_id: int, actor_user_id: int, *, is_superadmin: bool
    ) -> None:
        """
        Purpose: Delete workspace.
        Only owner membership or super admin.
        """
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found")

        if not is_superadmin:
            m = self.memberships.find_by_user_and_workspace(actor_user_id, workspace_id)
            if not m or workspace.owner_membership_id != m.id:
                raise ForbiddenError("Only the workspace owner can delete this workspace")

        db.session.delete(workspace)
        db.session.commit()

    def is_workspace_owner(self, workspace: Workspace, membership_id: int | None) -> bool:
        return membership_id is not None and workspace.owner_membership_id == membership_id

    def can_invite_teachers(self, workspace: Workspace) -> bool:
        return workspace.kind == WorkspaceKind.INSTITUTION.value

    def _unique_join_code(self) -> str:
        for _ in range(10):
            code = generate_workspace_join_code()
            if not self.workspaces.find_by_join_code(code):
                return code
        raise ConflictError("Could not generate unique join code")

    def _serialize_workspace(
        self, workspace: Workspace, *, role: str | None, membership_id: int | None
    ) -> dict:
        return {
            "id": workspace.id,
            "name": workspace.name,
            "slug": workspace.slug,
            "kind": workspace.kind,
            "status": workspace.status,
            "join_code": workspace.join_code,
            "membership_id": membership_id,
            "role": role,
            "is_owner": workspace.owner_membership_id == membership_id,
        }

    def _serialize_workspace_detail(self, workspace: Workspace) -> dict:
        return {
            "id": workspace.id,
            "name": workspace.name,
            "slug": workspace.slug,
            "kind": workspace.kind,
            "status": workspace.status,
            "join_code": workspace.join_code,
            "owner_user_id": workspace.owner_user_id,
            "owner_membership_id": workspace.owner_membership_id,
            "subject_assignment_mode": workspace.subject_assignment_mode,
            "is_verified_by_superadmin": workspace.is_verified_by_superadmin,
        }
