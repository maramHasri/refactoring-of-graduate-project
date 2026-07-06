from sqlalchemy import func

from models import Membership, StudentGroup, StudentGroupMember, User
from repositories.base_repository import BaseRepository
from utils.db import db


class StudentGroupRepository(BaseRepository):
    def get_by_id(self, group_id: int) -> StudentGroup | None:
        return db.session.get(StudentGroup, group_id)

    def get_in_workspace(self, group_id: int, workspace_id: int) -> StudentGroup | None:
        return db.session.execute(
            db.select(StudentGroup).where(
                StudentGroup.id == group_id,
                StudentGroup.workspace_id == workspace_id,
            )
        ).scalar_one_or_none()

    def find_by_subject_and_name(
        self, subject_id: int, name: str
    ) -> StudentGroup | None:
        return db.session.execute(
            db.select(StudentGroup).where(
                StudentGroup.subject_id == subject_id,
                StudentGroup.name == name,
            )
        ).scalar_one_or_none()

    def list_by_subject(self, subject_id: int, workspace_id: int) -> list[StudentGroup]:
        return list(
            db.session.execute(
                db.select(StudentGroup)
                .where(
                    StudentGroup.subject_id == subject_id,
                    StudentGroup.workspace_id == workspace_id,
                )
                .order_by(StudentGroup.name)
            ).scalars().all()
        )

    def count_members_for_groups(self, group_ids: list[int]) -> dict[int, int]:
        if not group_ids:
            return {}
        rows = db.session.execute(
            db.select(
                StudentGroupMember.group_id,
                func.count(StudentGroupMember.id),
            )
            .where(StudentGroupMember.group_id.in_(group_ids))
            .group_by(StudentGroupMember.group_id)
        ).all()
        return {group_id: count for group_id, count in rows}

    def count_members(self, group_id: int) -> int:
        return (
            db.session.execute(
                db.select(func.count(StudentGroupMember.id)).where(
                    StudentGroupMember.group_id == group_id
                )
            ).scalar_one()
            or 0
        )

    def find_member(
        self, *, group_id: int, student_membership_id: int
    ) -> StudentGroupMember | None:
        return db.session.execute(
            db.select(StudentGroupMember).where(
                StudentGroupMember.group_id == group_id,
                StudentGroupMember.student_membership_id == student_membership_id,
            )
        ).scalar_one_or_none()

    def list_member_ids(self, group_id: int) -> set[int]:
        rows = db.session.execute(
            db.select(StudentGroupMember.student_membership_id).where(
                StudentGroupMember.group_id == group_id
            )
        ).scalars().all()
        return set(rows)

    def list_members_with_users(self, group_id: int) -> list[tuple[StudentGroupMember, Membership, User | None]]:
        rows = db.session.execute(
            db.select(StudentGroupMember, Membership, User)
            .join(
                Membership,
                Membership.id == StudentGroupMember.student_membership_id,
            )
            .join(User, User.id == Membership.user_id)
            .where(StudentGroupMember.group_id == group_id)
            .order_by(User.full_name, Membership.id)
        ).all()
        return list(rows)

    def delete_group(self, group: StudentGroup) -> None:
        db.session.delete(group)

    def delete_members_for_student_in_workspace(
        self, student_membership_id: int, workspace_id: int
    ) -> None:
        rows = db.session.execute(
            db.select(StudentGroupMember)
            .join(StudentGroup, StudentGroup.id == StudentGroupMember.group_id)
            .where(
                StudentGroupMember.student_membership_id == student_membership_id,
                StudentGroup.workspace_id == workspace_id,
            )
        ).scalars().all()
        for row in rows:
            db.session.delete(row)
