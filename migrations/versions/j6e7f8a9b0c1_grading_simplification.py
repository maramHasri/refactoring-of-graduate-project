"""Simplify grading: answer grading_status, drop unused test config columns

Revision ID: j6e7f8a9b0c1
Revises: i5d6e7f8a9b0
Create Date: 2026-06-29
"""
from alembic import op
import sqlalchemy as sa


revision = "j6e7f8a9b0c1"
down_revision = "i5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("attempt_answers", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("grading_status", sa.String(length=30), nullable=True)
        )
        batch_op.create_index(
            batch_op.f("ix_attempt_answers_grading_status"),
            ["grading_status"],
            unique=False,
        )

    op.execute(
        """
        UPDATE attempt_answers
        SET grading_status = 'AUTO_GRADED'
        WHERE earned_score IS NOT NULL OR is_correct IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE attempt_answers
        SET grading_status = 'PENDING_REVIEW'
        WHERE grading_status IS NULL
        """
    )

    with op.batch_alter_table("tests", schema=None) as batch_op:
        batch_op.drop_column("scoring_config")
        batch_op.drop_column("grading_mode")


def downgrade():
    with op.batch_alter_table("tests", schema=None) as batch_op:
        batch_op.add_column(sa.Column("grading_mode", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("scoring_config", sa.Text(), nullable=True))

    with op.batch_alter_table("attempt_answers", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_attempt_answers_grading_status"))
        batch_op.drop_column("grading_status")
