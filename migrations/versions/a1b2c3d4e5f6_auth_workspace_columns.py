"""Add superadmin, owner_membership_id, join_code

Revision ID: a1b2c3d4e5f6
Revises: fc65c4e81928
Create Date: 2026-05-22

"""
from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "fc65c4e81928"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_superadmin", sa.Boolean(), nullable=False, server_default="false")
        )

    with op.batch_alter_table("workspaces", schema=None) as batch_op:
        batch_op.add_column(sa.Column("owner_membership_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("join_code", sa.String(length=20), nullable=True))
        batch_op.create_index("ix_workspaces_join_code", ["join_code"], unique=True)
        batch_op.create_foreign_key(
            "fk_workspaces_owner_membership_id",
            "memberships",
            ["owner_membership_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade():
    with op.batch_alter_table("workspaces", schema=None) as batch_op:
        batch_op.drop_constraint("fk_workspaces_owner_membership_id", type_="foreignkey")
        batch_op.drop_index("ix_workspaces_join_code")
        batch_op.drop_column("join_code")
        batch_op.drop_column("owner_membership_id")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("is_superadmin")
