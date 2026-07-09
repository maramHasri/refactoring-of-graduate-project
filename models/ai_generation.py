from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import relationship

from utils.db import db
from utils.enums import AIGeneratedQuestionStatus, AIGenerationRequestStatus
from utils.mixins import TimestampMixin


class AIGenerationRequest(db.Model, TimestampMixin):
    __tablename__ = "ai_generation_requests"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    test_id = db.Column(
        db.Integer,
        ForeignKey("tests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_membership_id = db.Column(
        db.Integer,
        ForeignKey("memberships.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_ids_json = db.Column(Text, nullable=False)
    learning_objectives_json = db.Column(Text, nullable=True)
    count = db.Column(db.Integer, nullable=False)
    difficulty = db.Column(String(30), nullable=True)
    type_code = db.Column(String(50), nullable=False)
    additional_instructions = db.Column(Text, nullable=True)
    status = db.Column(
        String(30),
        nullable=False,
        default=AIGenerationRequestStatus.PENDING.value,
        server_default=AIGenerationRequestStatus.PENDING.value,
        index=True,
    )
    error_message = db.Column(Text, nullable=True)

    test = relationship("Test", foreign_keys=[test_id])
    created_by_membership = relationship(
        "Membership",
        foreign_keys=[created_by_membership_id],
    )
    generated_questions = relationship(
        "AIGeneratedQuestion",
        back_populates="generation_request",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    __table_args__ = (
        Index(
            "ix_ai_generation_requests_test_creator",
            "test_id",
            "created_by_membership_id",
        ),
    )


class AIGeneratedQuestion(db.Model, TimestampMixin):
    __tablename__ = "ai_generated_questions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    generation_request_id = db.Column(
        db.Integer,
        ForeignKey("ai_generation_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_text = db.Column(Text, nullable=False)
    type_code = db.Column(String(50), nullable=False)
    options_json = db.Column(Text, nullable=True)
    correct_answer_json = db.Column(Text, nullable=True)
    explanation = db.Column(Text, nullable=True)
    difficulty = db.Column(String(30), nullable=True)
    topic_id = db.Column(db.Integer, nullable=False)
    topic_name = db.Column(String(255), nullable=False)
    points = db.Column(db.Numeric(6, 2), nullable=False, server_default="1")
    status = db.Column(
        String(30),
        nullable=False,
        default=AIGeneratedQuestionStatus.PENDING_REVIEW.value,
        server_default=AIGeneratedQuestionStatus.PENDING_REVIEW.value,
        index=True,
    )

    generation_request = relationship(
        "AIGenerationRequest",
        back_populates="generated_questions",
        foreign_keys=[generation_request_id],
    )

    __table_args__ = (
        Index("ix_ai_generated_questions_request_status", "generation_request_id", "status"),
    )
