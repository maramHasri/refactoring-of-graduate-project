"""Add verified_at to email_otps for two-step password reset

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa


revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("email_otps", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("email_otps", schema=None) as batch_op:
        batch_op.drop_column("verified_at")
