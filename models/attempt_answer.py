from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from utils.db import db


class AttemptAnswer(db.Model):
    __tablename__ = "attempt_answers"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    attempt_id = db.Column(
        db.Integer,
        ForeignKey("test_attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id = db.Column(
        db.Integer,
        ForeignKey("questions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    answer_text = db.Column(Text, nullable=True)
    selected_choice_id = db.Column(
        db.Integer,
        ForeignKey("question_choices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_correct = db.Column(Boolean, nullable=True)
    earned_score = db.Column(Numeric(6, 2), nullable=True)

    attempt = relationship("TestAttempt", back_populates="answers")
    question = relationship("Question", back_populates="attempt_answers")
    selected_choice = relationship("QuestionChoice", back_populates="attempt_answers")

    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="unique_attempt_question"),
        Index("ix_attempt_answers_attempt_id", "attempt_id"),
    )

    def __repr__(self):
        return f"<AttemptAnswer id={self.id} attempt_id={self.attempt_id}>"
