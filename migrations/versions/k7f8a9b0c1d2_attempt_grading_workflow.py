"""Attempt grading workflow columns and audit logs

Revision ID: k7f8a9b0c1d2
Revises: j6e7f8a9b0c1
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa


revision = "k7f8a9b0c1d2"
down_revision = "j6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("test_attempts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("percentage", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "grading_notification_sent_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )

    with op.batch_alter_table("attempt_answers", schema=None) as batch_op:
        batch_op.add_column(sa.Column("teacher_feedback", sa.Text(), nullable=True))

    op.create_table(
        "attempt_grading_audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("attempt_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("actor_membership_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_membership_id"],
            ["memberships.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["test_attempts.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("attempt_grading_audit_logs", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_attempt_grading_audit_logs_attempt_id"),
            ["attempt_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_attempt_grading_audit_logs_action"),
            ["action"],
            unique=False,
        )
        batch_op.create_index(
            "ix_attempt_grading_audit_attempt_action",
            ["attempt_id", "action"],
            unique=False,
        )


def downgrade():
    op.drop_table("attempt_grading_audit_logs")

    with op.batch_alter_table("attempt_answers", schema=None) as batch_op:
        batch_op.drop_column("teacher_feedback")

    with op.batch_alter_table("test_attempts", schema=None) as batch_op:
        batch_op.drop_column("grading_notification_sent_at")
        batch_op.drop_column("graded_at")
        batch_op.drop_column("percentage")
