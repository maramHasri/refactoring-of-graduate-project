from datetime import datetime, timezone

from models import Subject, SubjectMembership
from repositories.base_repository import BaseRepository
from utils.db import db
from utils.enums import SubjectMembershipStatus, SubjectRole


class SubjectRepository(BaseRepository):
    def get_by_id(self, subject_id: int) -> Subject | None:
        return db.session.get(Subject, subject_id)

    def get_active_by_id(self, subject_id: int, workspace_id: int) -> Subject | None:
        return db.session.execute(
            db.select(Subject).where(
                Subject.id == subject_id,
                Subject.workspace_id == workspace_id,
                Subject.deleted_at.is_(None),
            )
        ).scalar_one_or_none()

    def list_active_by_workspace(self, workspace_id: int) -> list[Subject]:
        return list(
            db.session.execute(
                db.select(Subject)
                .where(
                    Subject.workspace_id == workspace_id,
                    Subject.deleted_at.is_(None),
                )
                .order_by(Subject.name)
            ).scalars().all()
        )

    def find_by_workspace_and_name(
        self, workspace_id: int, name: str
    ) -> Subject | None:
        return db.session.execute(
            db.select(Subject).where(
                Subject.workspace_id == workspace_id,
                Subject.name == name,
                Subject.deleted_at.is_(None),
            )
        ).scalar_one_or_none()


class SubjectMembershipRepository(BaseRepository):
    def find_active(
        self, membership_id: int, subject_id: int
    ) -> SubjectMembership | None:
        return db.session.execute(
            db.select(SubjectMembership).where(
                SubjectMembership.membership_id == membership_id,
                SubjectMembership.subject_id == subject_id,
                SubjectMembership.deleted_at.is_(None),
                SubjectMembership.status == SubjectMembershipStatus.ACTIVE.value,
            )
        ).scalar_one_or_none()

    def find_active_by_role(
        self, membership_id: int, subject_id: int, subject_role: str
    ) -> SubjectMembership | None:
        return db.session.execute(
            db.select(SubjectMembership).where(
                SubjectMembership.membership_id == membership_id,
                SubjectMembership.subject_id == subject_id,
                SubjectMembership.subject_role == subject_role,
                SubjectMembership.deleted_at.is_(None),
                SubjectMembership.status == SubjectMembershipStatus.ACTIVE.value,
            )
        ).scalar_one_or_none()

    def list_teachers_for_subject(self, subject_id: int) -> list[SubjectMembership]:
        return list(
            db.session.execute(
                db.select(SubjectMembership)
                .where(
                    SubjectMembership.subject_id == subject_id,
                    SubjectMembership.subject_role == SubjectRole.TEACHER.value,
                    SubjectMembership.deleted_at.is_(None),
                    SubjectMembership.status == SubjectMembershipStatus.ACTIVE.value,
                )
                .order_by(SubjectMembership.id)
            ).scalars().all()
        )

    def list_students_for_subject(self, subject_id: int) -> list[SubjectMembership]:
        return list(
            db.session.execute(
                db.select(SubjectMembership)
                .where(
                    SubjectMembership.subject_id == subject_id,
                    SubjectMembership.subject_role == SubjectRole.STUDENT.value,
                    SubjectMembership.deleted_at.is_(None),
                    SubjectMembership.status == SubjectMembershipStatus.ACTIVE.value,
                )
                .order_by(SubjectMembership.id)
            ).scalars().all()
        )

    def soft_remove(self, link: SubjectMembership) -> None:
        now = datetime.now(timezone.utc)
        link.deleted_at = now
        link.status = SubjectMembershipStatus.REMOVED.value
        link.updated_at = now
