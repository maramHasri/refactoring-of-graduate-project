"""Add profile_image_url (rename from avatar_url) and workspaces.logo_url

Revision ID: n0o1p2q3r4s5
Revises: m9n0o1p2q3r4
Create Date: 2026-07-04
"""

from alembic import op
import sqlalchemy as sa


revision = "n0o1p2q3r4s5"
down_revision = "m9n0o1p2q3r4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "avatar_url",
            new_column_name="profile_image_url",
            existing_type=sa.String(length=255),
            type_=sa.String(length=512),
            existing_nullable=True,
        )

    with op.batch_alter_table("workspaces", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("logo_url", sa.String(length=512), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("workspaces", schema=None) as batch_op:
        batch_op.drop_column("logo_url")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "profile_image_url",
            new_column_name="avatar_url",
            existing_type=sa.String(length=512),
            type_=sa.String(length=255),
            existing_nullable=True,
        )
