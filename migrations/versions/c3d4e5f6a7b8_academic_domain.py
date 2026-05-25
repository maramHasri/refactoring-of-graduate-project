"""Academic domain: subjects, subject_memberships, question_banks

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-23

"""
from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("subjects", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false")
        )
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
        )

    op.rename_table("memberships_subjects", "subject_memberships")

    with op.batch_alter_table("subject_memberships", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "subject_role",
                sa.String(length=30),
                nullable=False,
                server_default="TEACHER",
            )
        )
        batch_op.add_column(
            sa.Column("assigned_by_membership_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=30),
                nullable=False,
                server_default="ACTIVE",
            )
        )
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_subject_memberships_assigned_by",
            "memberships",
            ["assigned_by_membership_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_subject_memberships_subject_role",
            ["subject_id", "subject_role"],
            unique=False,
        )

    with op.batch_alter_table("question_banks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("title", sa.String(length=255), nullable=True))
    op.execute("UPDATE question_banks SET title = 'Legacy Bank' WHERE title IS NULL")
    with op.batch_alter_table("question_banks", schema=None) as batch_op:
        batch_op.alter_column("title", nullable=False)
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("workspace_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("subject_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("created_by_membership_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "visibility",
                sa.String(length=30),
                nullable=True,
                server_default="WORKSPACE",
            )
        )
        batch_op.add_column(
            sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false")
        )
        batch_op.add_column(
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            )
        )
        batch_op.create_foreign_key(
            "fk_question_banks_workspace",
            "workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_question_banks_subject",
            "subjects",
            ["subject_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_question_banks_created_by",
            "memberships",
            ["created_by_membership_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_question_banks_workspace_id", ["workspace_id"])
        batch_op.create_index("ix_question_banks_subject_id", ["subject_id"])


def downgrade():
    with op.batch_alter_table("question_banks", schema=None) as batch_op:
        batch_op.drop_index("ix_question_banks_subject_id")
        batch_op.drop_index("ix_question_banks_workspace_id")
        batch_op.drop_constraint("fk_question_banks_created_by", type_="foreignkey")
        batch_op.drop_constraint("fk_question_banks_subject", type_="foreignkey")
        batch_op.drop_constraint("fk_question_banks_workspace", type_="foreignkey")
        for col in (
            "updated_at",
            "created_at",
            "deleted_at",
            "is_archived",
            "visibility",
            "created_by_membership_id",
            "subject_id",
            "workspace_id",
            "description",
            "title",
        ):
            batch_op.drop_column(col)

    with op.batch_alter_table("subject_memberships", schema=None) as batch_op:
        batch_op.drop_index("ix_subject_memberships_subject_role")
        batch_op.drop_constraint("fk_subject_memberships_assigned_by", type_="foreignkey")
        for col in (
            "deleted_at",
            "updated_at",
            "status",
            "assigned_by_membership_id",
            "subject_role",
        ):
            batch_op.drop_column(col)

    op.rename_table("subject_memberships", "memberships_subjects")

    with op.batch_alter_table("subjects", schema=None) as batch_op:
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("is_archived")
