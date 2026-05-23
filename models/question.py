from sqlalchemy import ForeignKey, Index, Numeric, String, Text, UniqueConstraint
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
        return f"<QuestionType id={self.id} name={self.name}>"


class QuestionChoice(db.Model, TimestampMixin):
    __tablename__ = "question_choices"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(String(255), nullable=False)
    slug = db.Column(String(255), nullable=False, unique=True)
    kind = db.Column(String(50), nullable=False)
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

    owner = relationship("User", back_populates="owned_question_choices")
    questions = relationship(
        "Question",
        back_populates="question_choice",
        lazy="dynamic",
    )
    attempt_answers = relationship(
        "AttemptAnswer",
        back_populates="selected_choice",
        lazy="dynamic",
    )

    __table_args__ = (Index("ix_question_choices_status", "status"),)

    def __repr__(self):
        return f"<QuestionChoice id={self.id} slug={self.slug}>"


class QuestionBank(db.Model):
    """
    Placeholder until full question_banks schema is provided.
    Required for questions.bank_id FK.
    """

    __tablename__ = "question_banks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    questions = relationship(
        "Question",
        back_populates="bank",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<QuestionBank id={self.id}>"


class Question(db.Model, TimestampMixin):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    bank_id = db.Column(
        db.Integer,
        ForeignKey("question_banks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name = db.Column(String(255), nullable=False)
    slug = db.Column(String(255), nullable=False, unique=True)
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
    question_choices_id = db.Column(
        db.Integer,
        ForeignKey("question_choices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    topic_id = db.Column(
        db.Integer,
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    bank = relationship("QuestionBank", back_populates="questions")
    question_type = relationship("QuestionType", back_populates="questions")
    question_choice = relationship("QuestionChoice", back_populates="questions")
    topic = relationship("Topic", back_populates="questions")
    owner = relationship("User", back_populates="owned_questions")
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
        Index("ix_questions_question_type_id", "question_type_id"),
    )

    def __repr__(self):
        return f"<Question id={self.id} slug={self.slug}>"


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
