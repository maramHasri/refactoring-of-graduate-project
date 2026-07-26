"""Add test_attempts.termination_reason for proctoring auto-termination.

Revision ID: t6u7v8w9x0y1
Revises: s5t6u7v8w9x0
Create Date: 2026-07-26
"""

from alembic import op
import sqlalchemy as sa


revision = "t6u7v8w9x0y1"
down_revision = "s5t6u7v8w9x0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("test_attempts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("termination_reason", sa.String(length=80), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("test_attempts", schema=None) as batch_op:
        batch_op.drop_column("termination_reason")
