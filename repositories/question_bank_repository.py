from models import QuestionBank
from repositories.base_repository import BaseRepository
from utils.db import db


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
