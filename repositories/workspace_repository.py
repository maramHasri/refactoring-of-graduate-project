from datetime import datetime

from sqlalchemy import func, or_

from models import Membership, Subject, SubjectMembership, TestAttempt, User, Workspace
from repositories.base_repository import BaseRepository
from utils.db import db
from utils.enums import MembershipRole, SubjectMembershipStatus


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
        from utils.enums import WorkspaceStatus

        return list(
            db.session.execute(
                db.select(Workspace)
                .join(Membership, Membership.workspace_id == Workspace.id)
                .where(
                    Membership.user_id == user_id,
                    Membership.status == "ACTIVE",
                    Workspace.status == WorkspaceStatus.ACTIVE.value,
                )
                .order_by(Workspace.name)
            ).scalars().all()
        )


class MembershipRepository(BaseRepository):
    def get_with_user(self, membership_id: int) -> tuple[Membership, User] | None:
        row = db.session.execute(
            db.select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.id == membership_id)
        ).first()
        if not row:
            return None
        return row[0], row[1]

    def list_recently_active_in_workspace(
        self,
        workspace_id: int,
        *,
        since: datetime,
        role: str | None = None,
    ) -> list[tuple[Membership, User, datetime | None]]:
        attempt_activity = (
            db.select(
                TestAttempt.user_id.label("user_id"),
                func.max(TestAttempt.last_activity_at).label("attempt_activity_at"),
            )
            .join(Membership, Membership.id == TestAttempt.student_membership_id)
            .where(Membership.workspace_id == workspace_id)
            .group_by(TestAttempt.user_id)
            .subquery()
        )
        effective_activity = func.coalesce(
            attempt_activity.c.attempt_activity_at,
            User.last_login_at,
        )
        filters = [
            Membership.workspace_id == workspace_id,
            Membership.status == "ACTIVE",
            effective_activity.is_not(None),
            effective_activity >= since,
        ]
        if role:
            filters.append(Membership.role == role)

        rows = db.session.execute(
            db.select(Membership, User, effective_activity)
            .join(User, User.id == Membership.user_id)
            .outerjoin(attempt_activity, attempt_activity.c.user_id == User.id)
            .where(*filters)
            .order_by(effective_activity.desc(), User.full_name, Membership.id)
        ).all()
        return [(membership, user, activity_at) for membership, user, activity_at in rows]

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

    def list_active_members_by_role_with_subject_counts(
        self,
        workspace_id: int,
        role: str,
        *,
        subject_role: str,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
        enrolled_in_subjects_only: bool = False,
    ) -> tuple[list[tuple[Membership, User, int]], int]:
        """
        Active workspace members of a role with per-member subject assignment counts.
        Counts active subject_memberships in this workspace for the given subject_role.

        When enrolled_in_subjects_only is True, only members with at least one
        active subject enrollment in this workspace are returned (solo teacher view).
        """
        membership_filters = [
            Membership.workspace_id == workspace_id,
            Membership.role == role,
            Membership.status == "ACTIVE",
        ]
        if search:
            term = f"%{search.strip()}%"
            membership_filters.append(
                or_(User.full_name.ilike(term), User.email.ilike(term))
            )

        subject_counts = (
            db.select(
                SubjectMembership.membership_id.label("membership_id"),
                func.count(SubjectMembership.id).label("subject_count"),
            )
            .join(Subject, Subject.id == SubjectMembership.subject_id)
            .where(
                SubjectMembership.deleted_at.is_(None),
                SubjectMembership.status == SubjectMembershipStatus.ACTIVE.value,
                SubjectMembership.subject_role == subject_role,
                Subject.workspace_id == workspace_id,
                Subject.deleted_at.is_(None),
            )
            .group_by(SubjectMembership.membership_id)
            .subquery()
        )

        enrollment_filter = []
        if enrolled_in_subjects_only:
            enrollment_filter.append(
                func.coalesce(subject_counts.c.subject_count, 0) > 0
            )

        total = (
            db.session.execute(
                db.select(func.count())
                .select_from(Membership)
                .join(User, User.id == Membership.user_id)
                .outerjoin(
                    subject_counts,
                    subject_counts.c.membership_id == Membership.id,
                )
                .where(*membership_filters, *enrollment_filter)
            ).scalar_one()
            or 0
        )

        rows = db.session.execute(
            db.select(
                Membership,
                User,
                func.coalesce(subject_counts.c.subject_count, 0),
            )
            .join(User, User.id == Membership.user_id)
            .outerjoin(
                subject_counts,
                subject_counts.c.membership_id == Membership.id,
            )
            .where(*membership_filters, *enrollment_filter)
            .order_by(User.full_name, User.id)
            .offset(offset)
            .limit(limit)
        ).all()

        return [(membership, user, int(count)) for membership, user, count in rows], total
