from sqlalchemy import func
from sqlalchemy.orm import joinedload

from models import Membership, StudentGroup, StudentGroupMember, User
from repositories.base_repository import BaseRepository
from utils.db import db


class StudentGroupRepository(BaseRepository):
    def get_by_id(self, group_id: int) -> StudentGroup | None:
        return db.session.get(StudentGroup, group_id)

    def get_in_workspace(self, group_id: int, workspace_id: int) -> StudentGroup | None:
        return db.session.execute(
            db.select(StudentGroup)
            .options(
                joinedload(StudentGroup.created_by).joinedload(Membership.user),
                joinedload(StudentGroup.subject),
            )
            .where(
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
                .options(
                    joinedload(StudentGroup.created_by).joinedload(Membership.user),
                )
                .where(
                    StudentGroup.subject_id == subject_id,
                    StudentGroup.workspace_id == workspace_id,
                )
                .order_by(StudentGroup.name)
            )
            .scalars()
            .unique()
            .all()
        )

    def list_by_subject_for_owner(
        self, subject_id: int, workspace_id: int, owner_membership_id: int
    ) -> list[StudentGroup]:
        return list(
            db.session.execute(
                db.select(StudentGroup)
                .options(
                    joinedload(StudentGroup.created_by).joinedload(Membership.user),
                )
                .where(
                    StudentGroup.subject_id == subject_id,
                    StudentGroup.workspace_id == workspace_id,
                    StudentGroup.created_by_membership_id == owner_membership_id,
                )
                .order_by(StudentGroup.name)
            )
            .scalars()
            .unique()
            .all()
        )

    def list_by_workspace(self, workspace_id: int) -> list[StudentGroup]:
        return list(
            db.session.execute(
                db.select(StudentGroup)
                .options(
                    joinedload(StudentGroup.created_by).joinedload(Membership.user),
                    joinedload(StudentGroup.subject),
                )
                .where(StudentGroup.workspace_id == workspace_id)
                .order_by(StudentGroup.subject_id, StudentGroup.name)
            )
            .scalars()
            .unique()
            .all()
        )

    def list_by_workspace_for_owner(
        self, workspace_id: int, owner_membership_id: int
    ) -> list[StudentGroup]:
        return list(
            db.session.execute(
                db.select(StudentGroup)
                .options(
                    joinedload(StudentGroup.created_by).joinedload(Membership.user),
                    joinedload(StudentGroup.subject),
                )
                .where(
                    StudentGroup.workspace_id == workspace_id,
                    StudentGroup.created_by_membership_id == owner_membership_id,
                )
                .order_by(StudentGroup.subject_id, StudentGroup.name)
            )
            .scalars()
            .unique()
            .all()
        )

    def map_members_with_users_for_groups(
        self, group_ids: list[int]
    ) -> dict[int, list[tuple[StudentGroupMember, Membership, User | None]]]:
        if not group_ids:
            return {}
        rows = db.session.execute(
            db.select(StudentGroupMember, Membership, User)
            .join(
                Membership,
                Membership.id == StudentGroupMember.student_membership_id,
            )
            .join(User, User.id == Membership.user_id)
            .where(StudentGroupMember.group_id.in_(group_ids))
            .order_by(
                StudentGroupMember.group_id,
                User.full_name,
                Membership.id,
            )
        ).all()
        result: dict[int, list[tuple[StudentGroupMember, Membership, User | None]]] = {
            group_id: [] for group_id in group_ids
        }
        for member, membership, user in rows:
            result.setdefault(member.group_id, []).append((member, membership, user))
        return result

    def count_groups_by_student_membership_ids(
        self,
        workspace_id: int,
        student_membership_ids: list[int],
    ) -> dict[int, int]:
        """Count distinct student groups per student membership in a workspace."""
        if not student_membership_ids:
            return {}
        rows = db.session.execute(
            db.select(
                StudentGroupMember.student_membership_id,
                func.count(func.distinct(StudentGroupMember.group_id)),
            )
            .join(StudentGroup, StudentGroup.id == StudentGroupMember.group_id)
            .where(
                StudentGroup.workspace_id == workspace_id,
                StudentGroupMember.student_membership_id.in_(student_membership_ids),
            )
            .group_by(StudentGroupMember.student_membership_id)
        ).all()
        return {int(membership_id): int(count) for membership_id, count in rows}

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

    def list_member_ids_for_groups(self, group_ids: list[int]) -> set[int]:
        if not group_ids:
            return set()
        rows = db.session.execute(
            db.select(StudentGroupMember.student_membership_id).where(
                StudentGroupMember.group_id.in_(group_ids)
            )
        ).scalars().all()
        return set(int(value) for value in rows)

    def list_members_with_users(
        self, group_id: int
    ) -> list[tuple[StudentGroupMember, Membership, User | None]]:
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

    def map_current_groups_for_students_in_subject(
        self,
        *,
        subject_id: int,
        student_membership_ids: list[int],
        exclude_group_id: int | None = None,
    ) -> dict[int, StudentGroup]:
        """
        Map student_membership_id -> StudentGroup for students already in a
        group of this subject (optionally excluding one group).
        """
        if not student_membership_ids:
            return {}
        stmt = (
            db.select(StudentGroupMember.student_membership_id, StudentGroup)
            .join(StudentGroup, StudentGroup.id == StudentGroupMember.group_id)
            .options(
                joinedload(StudentGroup.created_by).joinedload(Membership.user),
            )
            .where(
                StudentGroup.subject_id == subject_id,
                StudentGroupMember.student_membership_id.in_(student_membership_ids),
            )
        )
        if exclude_group_id is not None:
            stmt = stmt.where(StudentGroup.id != exclude_group_id)
        rows = db.session.execute(stmt).unique().all()
        return {int(membership_id): group for membership_id, group in rows}

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

    def delete_members_for_student_in_subject(
        self, student_membership_id: int, subject_id: int
    ) -> int:
        rows = db.session.execute(
            db.select(StudentGroupMember)
            .join(StudentGroup, StudentGroup.id == StudentGroupMember.group_id)
            .where(
                StudentGroupMember.student_membership_id == student_membership_id,
                StudentGroup.subject_id == subject_id,
            )
        ).scalars().all()
        for row in rows:
            db.session.delete(row)
        return len(rows)
