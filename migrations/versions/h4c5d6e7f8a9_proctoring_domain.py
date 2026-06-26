"""Proctoring domain tables

Revision ID: h4c5d6e7f8a9
Revises: g3b4c5d6e7f8
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "h4c5d6e7f8a9"
down_revision = "g3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "proctoring_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("test_attempt_id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="ACTIVE",
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("violation_score", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tab_switch_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("settings_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("device_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("browser_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["test_attempt_id"], ["test_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("test_attempt_id"),
    )
    with op.batch_alter_table("proctoring_sessions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_proctoring_sessions_workspace_id"),
            ["workspace_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_proctoring_sessions_workspace_status",
            ["workspace_id", "status"],
            unique=False,
        )

    op.create_table(
        "proctoring_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=20), server_default="REST", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["proctoring_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("proctoring_events", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_proctoring_events_session_id"), ["session_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_proctoring_events_event_type"), ["event_type"], unique=False
        )
        batch_op.create_index(
            "ix_proctoring_events_session_occurred",
            ["session_id", "occurred_at"],
            unique=False,
        )

    op.create_table(
        "proctoring_violations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("violation_type", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("score_contribution", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="OPEN",
            nullable=False,
        ),
        sa.Column("reviewed_by_membership_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["proctoring_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["reviewed_by_membership_id"], ["memberships.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("proctoring_violations", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_proctoring_violations_session_id"), ["session_id"], unique=False
        )
        batch_op.create_index(
            "ix_proctoring_violations_session_severity",
            ["session_id", "severity"],
            unique=False,
        )

    op.create_table(
        "proctoring_evidence_packages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("violation_id", sa.Integer(), nullable=False),
        sa.Column("timeline_before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("timeline_after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("screenshots", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("video_clip_ref", sa.String(length=512), nullable=True),
        sa.Column("device_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("browser_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("network_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("event_logs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["violation_id"], ["proctoring_violations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("violation_id"),
    )

    op.create_table(
        "proctoring_audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("violation_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("actor_membership_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["proctoring_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["violation_id"], ["proctoring_violations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["actor_membership_id"], ["memberships.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("proctoring_audit_logs", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_proctoring_audit_logs_session_id"), ["session_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_proctoring_audit_logs_action"), ["action"], unique=False
        )
        batch_op.create_index(
            "ix_proctoring_audit_logs_session_action",
            ["session_id", "action"],
            unique=False,
        )


def downgrade():
    raise NotImplementedError("Proctoring domain migration is not reversible automatically")
