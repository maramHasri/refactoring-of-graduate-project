"""Add optional image paths for questions

Revision ID: l8m9n0p1q2r3
Revises: k7f8a9b0c1d2
Create Date: 2026-07-02
"""

from alembic import op
import sqlalchemy as sa


revision = "l8m9n0p1q2r3"
down_revision = "k7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("questions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("image_path", sa.String(length=512), nullable=True))

    with op.batch_alter_table("test_questions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("snapshot_image_path", sa.String(length=512), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("test_questions", schema=None) as batch_op:
        batch_op.drop_column("snapshot_image_path")

    with op.batch_alter_table("questions", schema=None) as batch_op:
        batch_op.drop_column("image_path")
