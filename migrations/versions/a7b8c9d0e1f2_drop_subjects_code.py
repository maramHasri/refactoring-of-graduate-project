"""Remove unused subjects.code column

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-04

"""
from alembic import op
import sqlalchemy as sa


revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("subjects", schema=None) as batch_op:
        batch_op.drop_index("ix_subjects_workspace_code")
        batch_op.drop_column("code")


def downgrade():
    raise NotImplementedError("Dropping subjects.code is not reversible automatically")
