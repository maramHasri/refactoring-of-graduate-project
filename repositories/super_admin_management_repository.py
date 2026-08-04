from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from models import Membership, Question, Test, TestAttempt, User, Workspace
from repositories.base_repository import BaseRepository
from utils.db import db
from utils.enums import MembershipRole, TestAttemptStatus, WorkspaceKind


class SuperAdminManagementRepository(BaseRepository):
    def get_workspace_by_id(self, workspace_id: int) -> Workspace | None:
        return db.session.get(Workspace, workspace_id)

    def count_owned_workspaces(self, user_id: int) -> int:
        return (
            db.session.execute(
                select(func.count(Workspace.id)).where(Workspace.owner_user_id == user_id)
            ).scalar_one()
            or 0
        )

    def count_owned_questions(self, user_id: int) -> int:
        return (
            db.session.execute(
                select(func.count(Question.id)).where(Question.owner_user_id == user_id)
            ).scalar_one()
            or 0
        )

    def get_institution_member_counts(self, workspace_id: int) -> dict[str, int]:
        rows = db.session.execute(
            select(Membership.role, func.count(Membership.id))
            .join(User, User.id == Membership.user_id)
            .where(
                Membership.workspace_id == workspace_id,
                Membership.status == "ACTIVE",
                User.deleted_at.is_(None),
                Membership.role.in_(
                    [
                        MembershipRole.ADMIN.value,
                        MembershipRole.STUDENT.value,
                        MembershipRole.TEACHER.value,
                    ]
                ),
            )
            .group_by(Membership.role)
        ).all()
        counts = {role: int(count) for role, count in rows}
        return {
            "admins_count": counts.get(MembershipRole.ADMIN.value, 0),
            "students_count": counts.get(MembershipRole.STUDENT.value, 0),
            "teachers_count": counts.get(MembershipRole.TEACHER.value, 0),
        }

    def count_institution_active_users(self, workspace_id: int) -> int:
        return (
            db.session.execute(
                select(func.count(Membership.id))
                .join(User, User.id == Membership.user_id)
                .where(
                    Membership.workspace_id == workspace_id,
                    Membership.status == "ACTIVE",
                    User.deleted_at.is_(None),
                )
            ).scalar_one()
            or 0
        )

    def count_institution_attempts(self, workspace_id: int) -> int:
        return (
            db.session.execute(
                select(func.count(TestAttempt.id))
                .select_from(TestAttempt)
                .join(Test, Test.id == TestAttempt.test_id)
                .join(Membership, Membership.id == Test.created_by_membership_id)
                .where(Membership.workspace_id == workspace_id)
            ).scalar_one()
            or 0
        )

    def count_user_created_tests(self, user_id: int) -> int:
        return (
            db.session.execute(
                select(func.count(Test.id))
                .select_from(Test)
                .join(Membership, Membership.id == Test.created_by_membership_id)
                .where(Membership.user_id == user_id)
            ).scalar_one()
            or 0
        )

    def count_user_completed_attempts(self, user_id: int) -> int:
        return (
            db.session.execute(
                select(func.count(TestAttempt.id)).where(
                    TestAttempt.user_id == user_id,
                    TestAttempt.status.in_(
                        [
                            TestAttemptStatus.SUBMITTED.value,
                            TestAttemptStatus.GRADED.value,
                        ]
                    ),
                )
            ).scalar_one()
            or 0
        )

    def get_user_last_attempt_activity(self, user_id: int):
        return db.session.execute(
            select(func.max(TestAttempt.last_activity_at)).where(
                TestAttempt.user_id == user_id
            )
        ).scalar_one()

    def get_institution_owner(self, workspace: Workspace) -> User | None:
        if not workspace.owner_user_id:
            return None
        return db.session.get(User, workspace.owner_user_id)

    def count_institution_tests(self, workspace_id: int) -> int:
        return (
            db.session.execute(
                select(func.count(Test.id))
                .select_from(Test)
                .join(Membership, Membership.id == Test.created_by_membership_id)
                .where(Membership.workspace_id == workspace_id)
            ).scalar_one()
            or 0
        )

    def load_memberships_for_users(
        self, user_ids: list[int]
    ) -> dict[int, list[Membership]]:
        if not user_ids:
            return {}
        rows = db.session.execute(
            select(Membership)
            .options(selectinload(Membership.workspace))
            .where(Membership.user_id.in_(user_ids))
        ).scalars().all()
        grouped: dict[int, list[Membership]] = {}
        for membership in rows:
            grouped.setdefault(membership.user_id, []).append(membership)
        return grouped

    def list_users_with_memberships(
        self,
        *,
        role: str | None = None,
        institution_id: int | None = None,
        organization_id: int | None = None,
        status: str | None = None,
        search: str | None = None,
        super_admin_only: bool = False,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[User], dict[int, list[Membership]], int]:
        base = select(User).distinct()

        if super_admin_only:
            base = base.where(User.is_superadmin.is_(True))

        membership_filters = []
        if role:
            membership_filters.append(Membership.role == role)
        workspace_filter_id = organization_id if organization_id is not None else institution_id
        if workspace_filter_id is not None:
            membership_filters.append(Membership.workspace_id == workspace_filter_id)
        if membership_filters:
            base = base.join(Membership, Membership.user_id == User.id).where(
                *membership_filters
            )

        if status:
            base = base.where(User.user_status == status)

        if search:
            term = f"%{search.strip()}%"
            base = base.where(
                or_(User.full_name.ilike(term), User.email.ilike(term))
            )

        total = db.session.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one() or 0

        filtered_users = base.with_only_columns(User.id).distinct().subquery()
        user_ids = db.session.execute(
            select(User.id)
            .join(filtered_users, User.id == filtered_users.c.id)
            .order_by(User.full_name, User.id)
            .offset(offset)
            .limit(limit)
        ).scalars().all()

        if not user_ids:
            return [], {}, int(total)

        users = db.session.execute(
            select(User)
            .where(User.id.in_(user_ids))
            .order_by(User.full_name, User.id)
        ).scalars().all()
        memberships_by_user = self.load_memberships_for_users(list(user_ids))

        return list(users), memberships_by_user, int(total)

    def get_user_with_memberships(self, user_id: int) -> User | None:
        user = db.session.get(User, user_id)
        if not user:
            return None
        return user
