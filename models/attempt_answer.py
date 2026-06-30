import json

from sqlalchemy import ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from utils.db import db
from utils.mixins import TimestampMixin


class AttemptAnswer(db.Model, TimestampMixin):
    """
    Student response to a single test_questions snapshot row.
    Answers reference test_question_id (not questions.id) so snapshot-only
    exam items (AI/manual with question_id=null) are supported.
    """

    __tablename__ = "attempt_answers"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    attempt_id = db.Column(
        db.Integer,
        ForeignKey("test_attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    test_question_id = db.Column(
        db.Integer,
        ForeignKey("test_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    answer_text = db.Column(Text, nullable=True)
    selected_choice_indices = db.Column(Text, nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)
    earned_score = db.Column(Numeric(6, 2), nullable=True)
    grading_status = db.Column(String(30), nullable=True, index=True)

    attempt = relationship("TestAttempt", back_populates="answers")
    test_question = relationship("TestQuestion", back_populates="attempt_answers")

    __table_args__ = (
        UniqueConstraint(
            "attempt_id",
            "test_question_id",
            name="unique_attempt_test_question",
        ),
        Index("ix_attempt_answers_attempt_id", "attempt_id"),
    )

    def get_selected_indices(self) -> list[int]:
        if not self.selected_choice_indices:
            return []
        try:
            data = json.loads(self.selected_choice_indices)
        except (TypeError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []
        return [int(i) for i in data if isinstance(i, (int, float)) and i >= 0]

    def set_selected_indices(self, indices: list[int] | None) -> None:
        if not indices:
            self.selected_choice_indices = None
            return
        self.selected_choice_indices = json.dumps(sorted(set(int(i) for i in indices)))

    def __repr__(self):
        return (
            f"<AttemptAnswer id={self.id} attempt_id={self.attempt_id} "
            f"test_question_id={self.test_question_id}>"
        )
