"""Refactor attempt_answers for test_question snapshots; extend test_attempts runtime fields

Revision ID: g3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa


revision = "g3b4c5d6e7f8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("test_attempts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("submission_source", sa.String(length=30), nullable=True)
        )

    with op.batch_alter_table("attempt_answers", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("test_question_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("selected_choice_indices", sa.Text(), nullable=True)
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

    # Legacy attempt_answers rows are not migrated (no runtime data existed pre-Phase-1).
    op.execute("DELETE FROM attempt_answers")

    with op.batch_alter_table("attempt_answers", schema=None) as batch_op:
        batch_op.drop_constraint("attempt_answers_question_id_fkey", type_="foreignkey")
        batch_op.drop_constraint(
            "attempt_answers_selected_choice_id_fkey", type_="foreignkey"
        )
        batch_op.drop_constraint("unique_attempt_question", type_="unique")
        batch_op.drop_index(batch_op.f("ix_attempt_answers_question_id"))
        batch_op.drop_index(batch_op.f("ix_attempt_answers_selected_choice_id"))
        batch_op.drop_column("question_id")
        batch_op.drop_column("selected_choice_id")
        batch_op.alter_column("test_question_id", nullable=False)
        batch_op.create_foreign_key(
            "attempt_answers_test_question_id_fkey",
            "test_questions",
            ["test_question_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(
            batch_op.f("ix_attempt_answers_test_question_id"),
            ["test_question_id"],
            unique=False,
        )
        batch_op.create_unique_constraint(
            "unique_attempt_test_question",
            ["attempt_id", "test_question_id"],
        )


def downgrade():
    raise NotImplementedError(
        "Attempt answer test_question refactor is not reversible automatically"
    )
