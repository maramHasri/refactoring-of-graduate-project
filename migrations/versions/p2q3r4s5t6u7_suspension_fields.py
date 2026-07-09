"""Add suspension metadata to users and workspaces

Revision ID: p2q3r4s5t6u7
Revises: o1p2q3r4s5t6
Create Date: 2026-07-09
"""

from alembic import op
import sqlalchemy as sa


revision = "p2q3r4s5t6u7"
down_revision = "o1p2q3r4s5t6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("suspension_reason", sa.Text(), nullable=True))

    with op.batch_alter_table("workspaces", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("suspension_reason", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("workspaces", schema=None) as batch_op:
        batch_op.drop_column("suspension_reason")
        batch_op.drop_column("suspended_at")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("suspension_reason")
        batch_op.drop_column("suspended_at")
