"""Add tests.target_total_score for auto-distribute target

Revision ID: s5t6u7v8w9x0
Revises: r4s5t6u7v8w9
Create Date: 2026-07-24
"""

from alembic import op
import sqlalchemy as sa


revision = "s5t6u7v8w9x0"
down_revision = "r4s5t6u7v8w9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tests", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("target_total_score", sa.Numeric(8, 2), nullable=True)
        )

    # Preserve prior teacher intent for exams that already had auto-distribute ON.
    op.execute(
        """
        UPDATE tests
        SET target_total_score = total_score
        WHERE auto_distribute_scores IS TRUE
          AND total_score IS NOT NULL
          AND target_total_score IS NULL
        """
    )


def downgrade():
    with op.batch_alter_table("tests", schema=None) as batch_op:
        batch_op.drop_column("target_total_score")
