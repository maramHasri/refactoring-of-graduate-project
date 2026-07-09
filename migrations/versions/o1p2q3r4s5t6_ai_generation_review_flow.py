"""ai generation review flow

Revision ID: o1p2q3r4s5t6
Revises: n0o1p2q3r4s5
Create Date: 2026-07-09 13:50:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "o1p2q3r4s5t6"
down_revision = "n0o1p2q3r4s5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_generation_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("test_id", sa.Integer(), nullable=False),
        sa.Column("created_by_membership_id", sa.Integer(), nullable=False),
        sa.Column("topic_ids_json", sa.Text(), nullable=False),
        sa.Column("learning_objectives_json", sa.Text(), nullable=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("difficulty", sa.String(length=30), nullable=True),
        sa.Column("type_code", sa.String(length=50), nullable=False),
        sa.Column("additional_instructions", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["test_id"], ["tests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["created_by_membership_id"], ["memberships.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_generation_requests_test_id",
        "ai_generation_requests",
        ["test_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_generation_requests_created_by_membership_id",
        "ai_generation_requests",
        ["created_by_membership_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_generation_requests_status",
        "ai_generation_requests",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_ai_generation_requests_test_creator",
        "ai_generation_requests",
        ["test_id", "created_by_membership_id"],
        unique=False,
    )

    op.create_table(
        "ai_generated_questions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("generation_request_id", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("type_code", sa.String(length=50), nullable=False),
        sa.Column("options_json", sa.Text(), nullable=True),
        sa.Column("correct_answer_json", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.String(length=30), nullable=True),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("topic_name", sa.String(length=255), nullable=False),
        sa.Column(
            "points",
            sa.Numeric(precision=6, scale=2),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="PENDING_REVIEW",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["generation_request_id"], ["ai_generation_requests.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_generated_questions_generation_request_id",
        "ai_generated_questions",
        ["generation_request_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_generated_questions_status",
        "ai_generated_questions",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_ai_generated_questions_request_status",
        "ai_generated_questions",
        ["generation_request_id", "status"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_ai_generated_questions_request_status", table_name="ai_generated_questions"
    )
    op.drop_index("ix_ai_generated_questions_status", table_name="ai_generated_questions")
    op.drop_index(
        "ix_ai_generated_questions_generation_request_id",
        table_name="ai_generated_questions",
    )
    op.drop_table("ai_generated_questions")

    op.drop_index("ix_ai_generation_requests_test_creator", table_name="ai_generation_requests")
    op.drop_index("ix_ai_generation_requests_status", table_name="ai_generation_requests")
    op.drop_index(
        "ix_ai_generation_requests_created_by_membership_id",
        table_name="ai_generation_requests",
    )
    op.drop_index("ix_ai_generation_requests_test_id", table_name="ai_generation_requests")
    op.drop_table("ai_generation_requests")
