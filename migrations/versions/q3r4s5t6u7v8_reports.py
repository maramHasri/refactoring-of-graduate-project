"""Create reports table

Revision ID: q3r4s5t6u7v8
Revises: p2q3r4s5t6u7
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = "q3r4s5t6u7v8"
down_revision = "p2q3r4s5t6u7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "category",
            sa.String(length=30),
            server_default="OTHER",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="UNREAD",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reports_created_by_user_id"),
        "reports",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(op.f("ix_reports_workspace_id"), "reports", ["workspace_id"])
    op.create_index(op.f("ix_reports_status"), "reports", ["status"])
    op.create_index(
        "ix_reports_status_category",
        "reports",
        ["status", "category"],
        unique=False,
    )
    op.create_index("ix_reports_created_at", "reports", ["created_at"])


def downgrade():
    op.drop_index("ix_reports_created_at", table_name="reports")
    op.drop_index("ix_reports_status_category", table_name="reports")
    op.drop_index(op.f("ix_reports_status"), table_name="reports")
    op.drop_index(op.f("ix_reports_workspace_id"), table_name="reports")
    op.drop_index(op.f("ix_reports_created_by_user_id"), table_name="reports")
    op.drop_table("reports")
