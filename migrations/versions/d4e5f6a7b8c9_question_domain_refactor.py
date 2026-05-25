"""Refactor questions and question_choices for bank-centric domain

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-23

"""
from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    # --- questions: remove legacy choice link + slug; add academic fields ---
    with op.batch_alter_table("questions", schema=None) as batch_op:
        batch_op.drop_index("ix_questions_question_choices_id")
        batch_op.drop_constraint(
            "questions_question_choices_id_fkey", type_="foreignkey"
        )
        batch_op.drop_column("question_choices_id")
        batch_op.drop_column("slug")
        batch_op.alter_column("name", new_column_name="question_text")

    with op.batch_alter_table("questions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("explanation", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("points", sa.Numeric(6, 2), nullable=True))
        batch_op.add_column(
            sa.Column("difficulty", sa.String(length=30), nullable=True)
        )

    # --- question_choices: child rows per question (clear legacy standalone rows) ---
    op.execute("DELETE FROM question_choices")

    with op.batch_alter_table("question_choices", schema=None) as batch_op:
        batch_op.drop_index("ix_question_choices_status")
        batch_op.drop_index("ix_question_choices_owner_user_id")
        batch_op.drop_constraint(
            "question_choices_owner_user_id_fkey", type_="foreignkey"
        )
        batch_op.drop_column("status")
        batch_op.drop_column("owner_user_id")
        batch_op.drop_column("kind")
        batch_op.drop_column("slug")
        batch_op.drop_column("name")

    with op.batch_alter_table("question_choices", schema=None) as batch_op:
        batch_op.add_column(sa.Column("question_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("body", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("is_correct", sa.Boolean(), server_default="false", nullable=False)
        )
        batch_op.add_column(sa.Column("order_index", sa.Integer(), nullable=True))

    op.execute(
        "ALTER TABLE question_choices ALTER COLUMN question_id SET NOT NULL"
    )
    op.execute("ALTER TABLE question_choices ALTER COLUMN body SET NOT NULL")

    with op.batch_alter_table("question_choices", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_question_choices_question_id",
            "questions",
            ["question_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(
            "ix_question_choices_question_id", ["question_id"], unique=False
        )
        batch_op.create_index(
            "ix_question_choices_question_order",
            ["question_id", "order_index"],
            unique=False,
        )


def downgrade():
    raise NotImplementedError("Question domain refactor is not reversible automatically")
