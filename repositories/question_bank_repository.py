from models import QuestionBank, Subject, SubjectMembership
from repositories.base_repository import BaseRepository
from utils.db import db
from utils.enums import QuestionBankVisibility, SubjectMembershipStatus, SubjectRole


class QuestionBankRepository(BaseRepository):
    def get_by_id(self, bank_id: int) -> QuestionBank | None:
        return db.session.get(QuestionBank, bank_id)

    def get_active_by_id(self, bank_id: int, workspace_id: int) -> QuestionBank | None:
        return db.session.execute(
            db.select(QuestionBank).where(
                QuestionBank.id == bank_id,
                QuestionBank.workspace_id == workspace_id,
                QuestionBank.deleted_at.is_(None),
            )
        ).scalar_one_or_none()

    def get_active_community_by_id(self, bank_id: int) -> QuestionBank | None:
        """Cross-workspace lookup for platform COMMUNITY banks."""
        return db.session.execute(
            db.select(QuestionBank).where(
                QuestionBank.id == bank_id,
                QuestionBank.visibility == QuestionBankVisibility.COMMUNITY.value,
                *self._active_bank_filters(),
            )
        ).scalar_one_or_none()

    def list_by_subject(self, subject_id: int, workspace_id: int) -> list[QuestionBank]:
        return list(
            db.session.execute(
                db.select(QuestionBank)
                .where(
                    QuestionBank.subject_id == subject_id,
                    QuestionBank.workspace_id == workspace_id,
                    QuestionBank.deleted_at.is_(None),
                )
                .order_by(QuestionBank.title)
            ).scalars().all()
        )

    def list_by_creator(self, membership_id: int, workspace_id: int) -> list[QuestionBank]:
        return list(
            db.session.execute(
                db.select(QuestionBank)
                .where(
                    QuestionBank.created_by_membership_id == membership_id,
                    QuestionBank.workspace_id == workspace_id,
                    QuestionBank.deleted_at.is_(None),
                )
                .order_by(QuestionBank.updated_at.desc())
            ).scalars().all()
        )

    def _active_bank_filters(self):
        return (
            QuestionBank.deleted_at.is_(None),
            QuestionBank.is_archived.is_(False),
        )

    def count_workspace_discoverable(
        self,
        *,
        workspace_id: int,
        exclude_membership_id: int,
        subject_ids: list[int],
    ) -> int:
        if not subject_ids:
            return 0
        return (
            db.session.execute(
                db.select(db.func.count())
                .select_from(QuestionBank)
                .where(
                    QuestionBank.workspace_id == workspace_id,
                    QuestionBank.created_by_membership_id != exclude_membership_id,
                    QuestionBank.created_by_membership_id.isnot(None),
                    QuestionBank.subject_id.in_(subject_ids),
                    QuestionBank.visibility == QuestionBankVisibility.WORKSPACE.value,
                    *self._active_bank_filters(),
                )
            ).scalar()
            or 0
        )

    def list_workspace_discoverable(
        self,
        *,
        workspace_id: int,
        exclude_membership_id: int,
        subject_ids: list[int],
        offset: int,
        limit: int,
    ) -> list[QuestionBank]:
        if not subject_ids:
            return []
        return list(
            db.session.execute(
                db.select(QuestionBank)
                .where(
                    QuestionBank.workspace_id == workspace_id,
                    QuestionBank.created_by_membership_id != exclude_membership_id,
                    QuestionBank.created_by_membership_id.isnot(None),
                    QuestionBank.subject_id.in_(subject_ids),
                    QuestionBank.visibility == QuestionBankVisibility.WORKSPACE.value,
                    *self._active_bank_filters(),
                )
                .order_by(QuestionBank.updated_at.desc(), QuestionBank.id.desc())
                .offset(offset)
                .limit(limit)
            ).scalars().all()
        )

    def count_community(self) -> int:
        return (
            db.session.execute(
                db.select(db.func.count())
                .select_from(QuestionBank)
                .where(
                    QuestionBank.visibility == QuestionBankVisibility.COMMUNITY.value,
                    *self._active_bank_filters(),
                )
            ).scalar()
            or 0
        )

    def list_community(self, *, offset: int, limit: int) -> list[QuestionBank]:
        return list(
            db.session.execute(
                db.select(QuestionBank)
                .where(
                    QuestionBank.visibility == QuestionBankVisibility.COMMUNITY.value,
                    *self._active_bank_filters(),
                )
                .order_by(QuestionBank.updated_at.desc(), QuestionBank.id.desc())
                .offset(offset)
                .limit(limit)
            ).scalars().all()
        )
