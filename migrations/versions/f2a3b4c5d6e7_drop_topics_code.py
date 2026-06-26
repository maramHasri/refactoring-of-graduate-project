"""Remove unused topics.code column

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa


revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("topics", schema=None) as batch_op:
        batch_op.drop_column("code")


def downgrade():
    raise NotImplementedError("Dropping topics.code is not reversible automatically")
