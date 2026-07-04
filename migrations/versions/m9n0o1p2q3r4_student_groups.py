"""Student groups and group memberships

Revision ID: m9n0o1p2q3r4
Revises: l8m9n0p1q2r3
Create Date: 2026-07-04
"""

from alembic import op
import sqlalchemy as sa


revision = "m9n0o1p2q3r4"
down_revision = "l8m9n0p1q2r3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "student_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_membership_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["created_by_membership_id"],
            ["memberships.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subject_id", "name", name="uq_student_groups_subject_name"),
    )
    with op.batch_alter_table("student_groups", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_student_groups_created_by_membership_id"),
            ["created_by_membership_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_student_groups_subject_id"),
            ["subject_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_student_groups_workspace_id"),
            ["workspace_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_student_groups_workspace_subject",
            ["workspace_id", "subject_id"],
            unique=False,
        )

    op.create_table(
        "student_group_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("student_membership_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["student_groups.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_membership_id"],
            ["memberships.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "group_id",
            "student_membership_id",
            name="uq_student_group_member",
        ),
    )
    with op.batch_alter_table("student_group_members", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_student_group_members_group_id"),
            ["group_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_student_group_members_group_student",
            ["group_id", "student_membership_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_student_group_members_student_membership_id"),
            ["student_membership_id"],
            unique=False,
        )


def downgrade():
    op.drop_table("student_group_members")
    op.drop_table("student_groups")
