from sqlalchemy import Boolean, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from utils.db import db
from utils.enums import PaymentStatus, SubscriptionStatus
from utils.mixins import CreatedAtMixin


class Plan(db.Model, CreatedAtMixin):
    __tablename__ = "plans"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(String(100), nullable=False)
    slug = db.Column(String(255), nullable=False, unique=True)
    description = db.Column(Text, nullable=True)
    price = db.Column(Numeric(10, 2), nullable=False)
    billing_cycle = db.Column(String(20), nullable=False)
    is_active = db.Column(Boolean, nullable=False, default=True)

    plan_features = relationship(
        "PlanFeature",
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    workspace_subscriptions = relationship(
        "WorkspaceSubscription",
        back_populates="plan",
        lazy="dynamic",
    )
    subscriptions = relationship(
        "Subscription",
        back_populates="plan",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Plan id={self.id} slug={self.slug}>"


class Feature(db.Model, CreatedAtMixin):
    __tablename__ = "features"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key = db.Column(String(150), nullable=False, unique=True)
    name = db.Column(String(150), nullable=False)
    description = db.Column(Text, nullable=True)

    plan_features = relationship(
        "PlanFeature",
        back_populates="feature",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Feature key={self.key}>"


class PlanFeature(db.Model, CreatedAtMixin):
    __tablename__ = "plan_features"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    plan_id = db.Column(
        db.Integer,
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_id = db.Column(
        db.Integer,
        ForeignKey("features.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enabled = db.Column(Boolean, nullable=False, default=True)
    limit_value = db.Column(Integer, nullable=True)

    plan = relationship("Plan", back_populates="plan_features")
    feature = relationship("Feature", back_populates="plan_features")

    __table_args__ = (
        UniqueConstraint("plan_id", "feature_id", name="unique_plan_feature"),
    )

    def __repr__(self):
        return f"<PlanFeature plan_id={self.plan_id} feature_id={self.feature_id}>"


class WorkspaceSubscription(db.Model, CreatedAtMixin):
    __tablename__ = "workspace_subscriptions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    workspace_id = db.Column(
        db.Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id = db.Column(
        db.Integer,
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status = db.Column(String(30), nullable=False)
    started_at = db.Column(db.DateTime(timezone=True), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    auto_renew = db.Column(Boolean, nullable=False, default=False)

    workspace = relationship("Workspace", back_populates="workspace_subscriptions")
    plan = relationship("Plan", back_populates="workspace_subscriptions")
    payments = relationship(
        "Payment",
        back_populates="workspace_subscription",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    __table_args__ = (
        Index("ix_workspace_subscriptions_workspace_status", "workspace_id", "status"),
    )

    def __repr__(self):
        return f"<WorkspaceSubscription id={self.id} workspace_id={self.workspace_id}>"


class Subscription(db.Model, CreatedAtMixin):
    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    workspace_id = db.Column(
        db.Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id = db.Column(
        db.Integer,
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status = db.Column(
        String(30),
        nullable=False,
        default=SubscriptionStatus.ACTIVE.value,
    )
    started_at = db.Column(db.DateTime(timezone=True), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    auto_renew = db.Column(Boolean, nullable=False, default=False)

    workspace = relationship("Workspace", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")

    __table_args__ = (
        Index("ix_subscriptions_workspace_status", "workspace_id", "status"),
    )

    def __repr__(self):
        return f"<Subscription id={self.id} workspace_id={self.workspace_id}>"


class Payment(db.Model, CreatedAtMixin):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    workspace_subscription_id = db.Column(
        db.Integer,
        ForeignKey("workspace_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = db.Column(String(50), nullable=True)
    transaction_id = db.Column(String(255), nullable=True, index=True)
    amount = db.Column(Numeric(12, 2), nullable=False)
    currency = db.Column(String(10), nullable=False, default="USD")
    status = db.Column(
        String(30),
        nullable=False,
        default=PaymentStatus.PENDING.value,
    )
    request_payload = db.Column(JSONB, nullable=True)
    response_payload = db.Column(JSONB, nullable=True)
    paid_at = db.Column(db.DateTime(timezone=True), nullable=True)

    workspace_subscription = relationship(
        "WorkspaceSubscription",
        back_populates="payments",
    )

    __table_args__ = (
        Index("ix_payments_status", "status"),
    )

    def __repr__(self):
        return f"<Payment id={self.id} status={self.status}>"
