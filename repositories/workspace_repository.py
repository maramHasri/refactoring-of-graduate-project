from models import Membership, User, Workspace
from repositories.base_repository import BaseRepository
from utils.db import db
from utils.enums import MembershipRole


class WorkspaceRepository(BaseRepository):
    def get_by_id(self, workspace_id: int) -> Workspace | None:
        return db.session.get(Workspace, workspace_id)

    def find_by_slug(self, slug: str) -> Workspace | None:
        return db.session.execute(
            db.select(Workspace).where(Workspace.slug == slug)
        ).scalar_one_or_none()

    def find_by_join_code(self, join_code: str) -> Workspace | None:
        return db.session.execute(
            db.select(Workspace).where(Workspace.join_code == join_code.upper().strip())
        ).scalar_one_or_none()

    def list_for_user(self, user_id: int) -> list[Workspace]:
        return list(
            db.session.execute(
                db.select(Workspace)
                .join(Membership, Membership.workspace_id == Workspace.id)
                .where(
                    Membership.user_id == user_id,
                    Membership.status == "ACTIVE",
                )
                .order_by(Workspace.name)
            ).scalars().all()
        )


class MembershipRepository(BaseRepository):
    def get_by_id(self, membership_id: int) -> Membership | None:
        return db.session.get(Membership, membership_id)

    def find_by_user_and_workspace(
        self, user_id: int, workspace_id: int
    ) -> Membership | None:
        return db.session.execute(
            db.select(Membership).where(
                Membership.user_id == user_id,
                Membership.workspace_id == workspace_id,
            )
        ).scalar_one_or_none()

    def count_active_for_user(self, user_id: int) -> int:
        return db.session.execute(
            db.select(db.func.count())
            .select_from(Membership)
            .where(
                Membership.user_id == user_id,
                Membership.status == "ACTIVE",
            )
        ).scalar() or 0

    def list_active_members_by_role(
        self, workspace_id: int, role: str
    ) -> list[tuple[Membership, User]]:
        return list(
            db.session.execute(
                db.select(Membership, User)
                .join(User, User.id == Membership.user_id)
                .where(
                    Membership.workspace_id == workspace_id,
                    Membership.role == role,
                    Membership.status == "ACTIVE",
                )
                .order_by(User.full_name, User.id)
            ).all()
        )
