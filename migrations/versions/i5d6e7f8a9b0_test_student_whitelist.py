"""Add test student whitelist assignments

Revision ID: i5d6e7f8a9b0
Revises: h4c5d6e7f8a9
Create Date: 2026-06-29
"""
from alembic import op
import sqlalchemy as sa


revision = "i5d6e7f8a9b0"
down_revision = "h4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "test_student_assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("test_id", sa.Integer(), nullable=False),
        sa.Column("student_membership_id", sa.Integer(), nullable=False),
        sa.Column("assigned_by_membership_id", sa.Integer(), nullable=True),
        sa.Column("invite_status", sa.String(length=30), server_default="PENDING", nullable=False),
        sa.Column("invite_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invite_error", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["test_id"], ["tests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["student_membership_id"], ["memberships.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_membership_id"], ["memberships.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "test_id",
            "student_membership_id",
            name="uq_test_student_assignment",
        ),
    )
    with op.batch_alter_table("test_student_assignments", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_test_student_assignments_test_id"),
            ["test_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_test_student_assignments_student_membership_id"),
            ["student_membership_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_test_student_assignments_assigned_by_membership_id"),
            ["assigned_by_membership_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_test_student_assignments_test_invite_status",
            ["test_id", "invite_status"],
            unique=False,
        )


def downgrade():
    op.drop_table("test_student_assignments")
