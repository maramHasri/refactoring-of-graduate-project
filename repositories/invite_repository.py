from models import WorkspaceInvite
from repositories.base_repository import BaseRepository
from utils.db import db
from utils.enums import InviteStatus


class InviteRepository(BaseRepository):
    def find_by_token_hash(self, token_hash: str) -> WorkspaceInvite | None:
        return db.session.execute(
            db.select(WorkspaceInvite).where(
                WorkspaceInvite.token_hash == token_hash
            )
        ).scalar_one_or_none()

    def find_pending_by_email(
        self, workspace_id: int, email: str
    ) -> WorkspaceInvite | None:
        return db.session.execute(
            db.select(WorkspaceInvite).where(
                WorkspaceInvite.workspace_id == workspace_id,
                WorkspaceInvite.email == email.lower().strip(),
                WorkspaceInvite.status == InviteStatus.PENDING.value,
            )
        ).scalar_one_or_none()
