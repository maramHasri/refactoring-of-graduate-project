"""Add usage_count to question_banks

Revision ID: x0y1z2a3b4c5
Revises: w9x0y1z2a3b4
Create Date: 2026-08-07
"""

from alembic import op
import sqlalchemy as sa


revision = "x0y1z2a3b4c5"
down_revision = "w9x0y1z2a3b4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("question_banks", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "usage_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade():
    with op.batch_alter_table("question_banks", schema=None) as batch_op:
        batch_op.drop_column("usage_count")
