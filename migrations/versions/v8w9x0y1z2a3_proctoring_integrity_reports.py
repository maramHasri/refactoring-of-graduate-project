"""Create proctoring_integrity_reports table

Revision ID: v8w9x0y1z2a3
Revises: u7v8w9x0y1z2
Create Date: 2026-08-02
"""

from alembic import op
import sqlalchemy as sa


revision = "v8w9x0y1z2a3"
down_revision = "u7v8w9x0y1z2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "proctoring_integrity_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("attempt_id", sa.Integer(), nullable=False),
        sa.Column("test_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("teacher_membership_id", sa.Integer(), nullable=True),
        sa.Column("student_membership_id", sa.Integer(), nullable=False),
        sa.Column("proctoring_session_id", sa.Integer(), nullable=True),
        sa.Column("student_name", sa.String(length=255), nullable=False),
        sa.Column("teacher_name", sa.String(length=255), nullable=True),
        sa.Column("subject_name", sa.String(length=255), nullable=True),
        sa.Column("test_name", sa.String(length=255), nullable=False),
        sa.Column("workspace_name", sa.String(length=255), nullable=False),
        sa.Column("risk_percentage", sa.Float(), nullable=False),
        sa.Column("effective_violation_score", sa.Integer(), nullable=False),
        sa.Column("violations_count", sa.Integer(), nullable=False),
        sa.Column("high_severity_count", sa.Integer(), nullable=False),
        sa.Column("medium_severity_count", sa.Integer(), nullable=False),
        sa.Column("low_severity_count", sa.Integer(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("raw_score", sa.Float(), nullable=True),
        sa.Column("maximum_score", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submission_source", sa.String(length=30), nullable=False),
        sa.Column("termination_reason", sa.String(length=80), nullable=True),
        sa.Column("recommendation", sa.String(length=40), nullable=False),
        sa.Column("recommendation_reason", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("reviewed_by_membership_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"], ["test_attempts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["test_id"], ["tests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["teacher_membership_id"], ["memberships.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["student_membership_id"], ["memberships.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["proctoring_session_id"],
            ["proctoring_sessions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_membership_id"],
            ["memberships.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "attempt_id", name="uq_proctoring_integrity_reports_attempt"
        ),
    )
    op.create_index(
        "ix_proctoring_integrity_reports_attempt_id",
        "proctoring_integrity_reports",
        ["attempt_id"],
        unique=True,
    )
    op.create_index(
        "ix_proctoring_integrity_reports_test_id",
        "proctoring_integrity_reports",
        ["test_id"],
    )
    op.create_index(
        "ix_proctoring_integrity_reports_subject_id",
        "proctoring_integrity_reports",
        ["subject_id"],
    )
    op.create_index(
        "ix_proctoring_integrity_reports_workspace_id",
        "proctoring_integrity_reports",
        ["workspace_id"],
    )
    op.create_index(
        "ix_proctoring_integrity_reports_teacher_membership_id",
        "proctoring_integrity_reports",
        ["teacher_membership_id"],
    )
    op.create_index(
        "ix_proctoring_integrity_reports_student_membership_id",
        "proctoring_integrity_reports",
        ["student_membership_id"],
    )
    op.create_index(
        "ix_proctoring_integrity_reports_proctoring_session_id",
        "proctoring_integrity_reports",
        ["proctoring_session_id"],
    )
    op.create_index(
        "ix_proctoring_integrity_reports_status",
        "proctoring_integrity_reports",
        ["status"],
    )
    op.create_index(
        "ix_pir_workspace_status_created",
        "proctoring_integrity_reports",
        ["workspace_id", "status", "created_at"],
    )
    op.create_index(
        "ix_pir_workspace_test",
        "proctoring_integrity_reports",
        ["workspace_id", "test_id"],
    )
    op.create_index(
        "ix_pir_workspace_subject",
        "proctoring_integrity_reports",
        ["workspace_id", "subject_id"],
    )


def downgrade():
    op.drop_table("proctoring_integrity_reports")
