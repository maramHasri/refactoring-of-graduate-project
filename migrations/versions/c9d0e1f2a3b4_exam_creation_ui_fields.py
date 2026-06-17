"""Add auto_distribute_scores to tests

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa


revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tests", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "auto_distribute_scores",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            )
        )


def downgrade():
    raise NotImplementedError("Adding auto_distribute_scores is not reversible automatically")
