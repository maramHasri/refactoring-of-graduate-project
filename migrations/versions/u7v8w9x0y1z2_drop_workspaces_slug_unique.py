"""Drop unique constraint on workspaces.slug

Revision ID: u7v8w9x0y1z2
Revises: t6u7v8w9x0y1
Create Date: 2026-08-01
"""

from alembic import op


revision = "u7v8w9x0y1z2"
down_revision = "t6u7v8w9x0y1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("workspaces", schema=None) as batch_op:
        batch_op.drop_constraint("workspaces_slug_key", type_="unique")


def downgrade():
    with op.batch_alter_table("workspaces", schema=None) as batch_op:
        batch_op.create_unique_constraint("workspaces_slug_key", ["slug"])
