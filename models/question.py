"""
Question domain: banks contain questions; each question has many lightweight choices.

subject_memberships controls who may write to banks; question_type drives validation rules.
"""
from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from utils.db import db
from utils.enums import QuestionStatus
from utils.mixins import TimestampMixin


class QuestionType(db.Model):
    __tablename__ = "question_types"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(String(50), nullable=False, unique=True)
    code = db.Column(String(50), nullable=True, unique=True)
    description = db.Column(Text, nullable=True)

    questions = relationship("Question", back_populates="question_type", lazy="dynamic")

    def __repr__(self):
        return f"<QuestionType id={self.id} code={self.code}>"


class QuestionChoice(db.Model, TimestampMixin):
    """Answer option belonging to a single question."""

    __tablename__ = "question_choices"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    question_id = db.Column(
        db.Integer,
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    body = db.Column(Text, nullable=False)
    is_correct = db.Column(Boolean, nullable=False, default=False)
    order_index = db.Column(db.Integer, nullable=True)

    question = relationship("Question", back_populates="choices")
    attempt_answers = relationship(
        "AttemptAnswer",
        back_populates="selected_choice",
        lazy="dynamic",
    )

    __table_args__ = (
        Index("ix_question_choices_question_order", "question_id", "order_index"),
    )

    def __repr__(self):
        return f"<QuestionChoice id={self.id} question_id={self.question_id}>"


class QuestionBank(db.Model, TimestampMixin):
    """Subject-centered question bank. Visibility controls who can see it."""

    __tablename__ = "question_banks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(String(255), nullable=False)
    description = db.Column(Text, nullable=True)
    workspace_id = db.Column(
        db.Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id = db.Column(
        db.Integer,
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_membership_id = db.Column(
        db.Integer,
        ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    visibility = db.Column(String(30), nullable=False, default="WORKSPACE")
    is_archived = db.Column(Boolean, nullable=False, default=False)
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    subject = relationship("Subject", back_populates="question_banks")
    created_by = relationship(
        "Membership",
        foreign_keys=[created_by_membership_id],
    )
    questions = relationship(
        "Question",
        back_populates="bank",
        lazy="dynamic",
    )

    __table_args__ = (
        Index("ix_question_banks_workspace_subject", "workspace_id", "subject_id"),
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def __repr__(self):
        return f"<QuestionBank id={self.id} title={self.title}>"


class Question(db.Model, TimestampMixin):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    bank_id = db.Column(
        db.Integer,
        ForeignKey("question_banks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    question_text = db.Column(Text, nullable=False)
    explanation = db.Column(Text, nullable=True)
    question_type_id = db.Column(
        db.Integer,
        ForeignKey("question_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    owner_user_id = db.Column(
        db.Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status = db.Column(
        String(30),
        nullable=False,
        default=QuestionStatus.ACTIVE.value,
        server_default=QuestionStatus.ACTIVE.value,
    )
    topic_id = db.Column(
        db.Integer,
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    points = db.Column(Numeric(6, 2), nullable=True)
    difficulty = db.Column(String(30), nullable=True)

    bank = relationship("QuestionBank", back_populates="questions")
    question_type = relationship("QuestionType", back_populates="questions")
    topic = relationship("Topic", back_populates="questions")
    owner = relationship("User", back_populates="owned_questions")
    choices = relationship(
        "QuestionChoice",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="QuestionChoice.order_index",
        lazy="joined",
    )
    test_questions = relationship(
        "TestQuestion",
        back_populates="question",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    attempt_answers = relationship(
        "AttemptAnswer",
        back_populates="question",
        lazy="dynamic",
    )

    __table_args__ = (
        Index("ix_questions_status", "status"),
        Index("ix_questions_bank_id", "bank_id"),
    )

    def __repr__(self):
        return f"<Question id={self.id} bank_id={self.bank_id}>"


class TestQuestion(db.Model, TimestampMixin):
    __tablename__ = "test_questions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    test_id = db.Column(
        db.Integer,
        ForeignKey("tests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id = db.Column(
        db.Integer,
        ForeignKey("questions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    kind = db.Column(String(50), nullable=False)
    points = db.Column(Numeric(6, 2), nullable=False)
    status = db.Column(
        String(30),
        nullable=False,
        default=QuestionStatus.ACTIVE.value,
        server_default=QuestionStatus.ACTIVE.value,
    )

    test = relationship("Test", back_populates="test_questions")
    question = relationship("Question", back_populates="test_questions")

    __table_args__ = (
        UniqueConstraint("test_id", "question_id", name="unique_test_question"),
        Index("ix_test_questions_test_status", "test_id", "status"),
    )

    def __repr__(self):
        return f"<TestQuestion test_id={self.test_id} question_id={self.question_id}>"
