"""Extend test lifecycle and add test question snapshots

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa


revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tests", schema=None) as batch_op:
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("subject_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("total_score", sa.Numeric(8, 2), nullable=True))
        batch_op.add_column(sa.Column("passing_score", sa.Numeric(8, 2), nullable=True))
        batch_op.add_column(sa.Column("scoring_config", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("settings_config", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column("scheduled_publish_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_tests_subject_id", ["subject_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_tests_subject_id",
            "subjects",
            ["subject_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.execute(
        "UPDATE tests SET status = 'PUBLISHED' WHERE status = 'ACTIVE'"
    )

    with op.batch_alter_table("test_questions", schema=None) as batch_op:
        batch_op.alter_column("question_id", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(
            sa.Column(
                "source_type",
                sa.String(length=30),
                nullable=False,
                server_default="QUESTION_BANK",
            )
        )
        batch_op.add_column(sa.Column("source_bank_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("snapshot_question_text", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("snapshot_explanation", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("snapshot_type_code", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("snapshot_topic_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("snapshot_topic_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("snapshot_difficulty", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("snapshot_points", sa.Numeric(6, 2), nullable=True))
        batch_op.add_column(sa.Column("snapshot_choices_json", sa.Text(), nullable=True))
        batch_op.create_index(
            "ix_test_questions_test_source_type",
            ["test_id", "source_type"],
            unique=False,
        )

    op.execute(
        """
        UPDATE test_questions tq
        SET
            source_type = 'QUESTION_BANK',
            source_bank_id = q.bank_id,
            snapshot_question_text = q.question_text,
            snapshot_explanation = q.explanation,
            snapshot_type_code = COALESCE(UPPER(qt.code), qt.name),
            snapshot_topic_id = q.topic_id,
            snapshot_topic_name = tp.name,
            snapshot_difficulty = q.difficulty,
            snapshot_points = q.points,
            snapshot_choices_json = (
                SELECT COALESCE(
                    json_agg(
                        json_build_object(
                            'id', qc.id,
                            'body', qc.body,
                            'is_correct', qc.is_correct,
                            'order_index', qc.order_index
                        )
                        ORDER BY qc.order_index, qc.id
                    )::text,
                    '[]'
                )
                FROM question_choices qc
                WHERE qc.question_id = q.id
            )
        FROM questions q
        LEFT JOIN question_types qt ON qt.id = q.question_type_id
        LEFT JOIN topics tp ON tp.id = q.topic_id
        WHERE tq.question_id = q.id
        """
    )

    op.execute("UPDATE test_questions SET snapshot_question_text = '' WHERE snapshot_question_text IS NULL")
    op.execute("UPDATE test_questions SET snapshot_type_code = 'UNKNOWN' WHERE snapshot_type_code IS NULL")

    with op.batch_alter_table("test_questions", schema=None) as batch_op:
        batch_op.alter_column("snapshot_question_text", existing_type=sa.Text(), nullable=False)
        batch_op.alter_column("snapshot_type_code", existing_type=sa.String(length=50), nullable=False)


def downgrade():
    raise NotImplementedError("Test lifecycle and snapshot migration is not reversible automatically")
