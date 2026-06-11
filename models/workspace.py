from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint, event
from sqlalchemy.orm import relationship, validates

from utils.db import db
from utils.enums import InviteStatus, WorkspaceStatus
from utils.mixins import CreatedAtMixin, TimestampMixin, utcnow


class Workspace(db.Model, TimestampMixin):
    __tablename__ = "workspaces"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(String(255), nullable=False)
    slug = db.Column(String(255), nullable=False, unique=True)
    kind = db.Column(String(50), nullable=False)
    owner_user_id = db.Column(
        db.Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    owner_membership_id = db.Column(
        db.Integer,
        ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    join_code = db.Column(String(20), nullable=True, unique=True, index=True)
    status = db.Column(
        String(30),
        nullable=False,
        default=WorkspaceStatus.ACTIVE.value,
        server_default=WorkspaceStatus.ACTIVE.value,
    )
    subject_assignment_mode = db.Column(String(30), nullable=True)
    is_verified_by_superadmin = db.Column(Boolean, nullable=False, default=False)
    rejection_reason = db.Column(Text, nullable=True)

    owner = relationship(
        "User",
        back_populates="owned_workspaces",
        foreign_keys=[owner_user_id],
    )
    owner_membership = relationship(
        "Membership",
        foreign_keys=[owner_membership_id],
        post_update=True,
    )
    memberships = relationship(
        "Membership",
        back_populates="workspace",
        foreign_keys="Membership.workspace_id",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    invites = relationship(
        "WorkspaceInvite",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    profile = relationship(
        "WorkspaceProfile",
        back_populates="workspace",
        uselist=False,
        cascade="all, delete-orphan",
    )
    subjects = relationship(
        "Subject",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    topics = relationship(
        "Topic",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    workspace_subscriptions = relationship(
        "WorkspaceSubscription",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    subscriptions = relationship(
        "Subscription",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    __table_args__ = (
        Index("ix_workspaces_kind", "kind"),
        Index("ix_workspaces_status", "status"),
    )

    def __repr__(self):
        return f"<Workspace id={self.id} slug={self.slug}>"


class Membership(db.Model):
    __tablename__ = "memberships"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = db.Column(
        db.Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = db.Column(String(30), nullable=False)
    status = db.Column(
        String(30),
        nullable=False,
        default="ACTIVE",
        server_default="ACTIVE",
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
    joined_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    user = relationship("User", back_populates="memberships")
    workspace = relationship(
        "Workspace",
        back_populates="memberships",
        foreign_keys=[workspace_id],
    )
    sent_invites = relationship(
        "WorkspaceInvite",
        back_populates="invited_by",
        foreign_keys="WorkspaceInvite.invited_by_membership_id",
        lazy="dynamic",
    )
    created_subjects = relationship(
        "Subject",
        back_populates="created_by",
        foreign_keys="Subject.created_by_membership_id",
        lazy="dynamic",
    )
    subject_memberships = relationship(
        "SubjectMembership",
        back_populates="membership",
        foreign_keys="SubjectMembership.membership_id",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    created_tests = relationship(
        "Test",
        back_populates="created_by",
        foreign_keys="Test.created_by_membership_id",
        lazy="dynamic",
    )
    test_attempts = relationship(
        "TestAttempt",
        back_populates="student_membership",
        foreign_keys="TestAttempt.student_membership_id",
        lazy="dynamic",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "workspace_id", name="unique_user_workspace"),
        Index("ix_memberships_workspace_role", "workspace_id", "role"),
        Index("ix_memberships_workspace_status", "workspace_id", "status"),
    )

    def __repr__(self):
        return f"<Membership id={self.id} user_id={self.user_id} workspace_id={self.workspace_id} role={self.role}>"


class WorkspaceInvite(db.Model, CreatedAtMixin):
    __tablename__ = "workspace_invites"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    workspace_id = db.Column(
        db.Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email = db.Column(String(255), nullable=False)
    assigned_role = db.Column(String(30), nullable=False)
    token_hash = db.Column(String(255), nullable=False, unique=True)
    invited_by_membership_id = db.Column(
        db.Integer,
        ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = db.Column(
        String(30),
        nullable=False,
        default=InviteStatus.PENDING.value,
        server_default=InviteStatus.PENDING.value,
    )
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    accepted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    rejected_at = db.Column(db.DateTime(timezone=True), nullable=True)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True)

    workspace = relationship("Workspace", back_populates="invites")
    invited_by = relationship(
        "Membership",
        back_populates="sent_invites",
        foreign_keys=[invited_by_membership_id],
    )

    __table_args__ = (
        Index("ix_workspace_invites_workspace_email", "workspace_id", "email"),
        Index("ix_workspace_invites_status", "status"),
    )

    @validates("email")
    def _normalize_email(self, _key, value: str) -> str:
        if value is not None:
            return value.lower().strip()
        return value

    @property
    def invited_email(self) -> str:
        """API alias for invitation email (stored in `email` column)."""
        return self.email

    def __repr__(self):
        return f"<WorkspaceInvite id={self.id} email={self.email} status={self.status}>"


@event.listens_for(WorkspaceInvite, "before_insert")
@event.listens_for(WorkspaceInvite, "before_update")
def _ensure_invite_email_lowercase(_mapper, _connection, target: WorkspaceInvite):
    if target.email:
        target.email = target.email.lower().strip()


class WorkspaceProfile(db.Model, TimestampMixin):
    __tablename__ = "workspace_profiles"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    workspace_id = db.Column(
        db.Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    description = db.Column(Text, nullable=True)
    country = db.Column(String(120), nullable=True)
    city = db.Column(String(120), nullable=True)
    logo = db.Column(String(255), nullable=True)
    website_url = db.Column(String(255), nullable=True)

    workspace = relationship("Workspace", back_populates="profile")

    def __repr__(self):
        return f"<WorkspaceProfile workspace_id={self.workspace_id}>"
