"""Add percentage snapshot + teacher list index for integrity reports

Revision ID: w9x0y1z2a3b4
Revises: v8w9x0y1z2a3
Create Date: 2026-08-02
"""

from alembic import op
import sqlalchemy as sa


revision = "w9x0y1z2a3b4"
down_revision = "v8w9x0y1z2a3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("proctoring_integrity_reports", schema=None) as batch_op:
        batch_op.add_column(sa.Column("percentage", sa.Float(), nullable=True))
        batch_op.create_index(
            "ix_pir_workspace_teacher_created",
            ["workspace_id", "teacher_membership_id", "created_at"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("proctoring_integrity_reports", schema=None) as batch_op:
        batch_op.drop_index("ix_pir_workspace_teacher_created")
        batch_op.drop_column("percentage")
