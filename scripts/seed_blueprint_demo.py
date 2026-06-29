"""
Seed topics + question metadata for blueprint API testing.

Usage (from project root):
    flask shell
    >>> from scripts.seed_blueprint_demo import run
    >>> run()

Or:
    python -c "from app_factory import create_app; from scripts.seed_blueprint_demo import run; app=create_app(); app.app_context().push(); print(run())"
"""
from __future__ import annotations

from decimal import Decimal

from models import Membership, Question, QuestionBank, Subject, Test, Topic
from utils.db import db
from utils.enums import TestStatus


def _ensure_topics(*, subject_id: int, workspace_id: int, names: list[str]) -> list[Topic]:
    topics: list[Topic] = []
    for name in names:
        row = db.session.execute(
            db.select(Topic).where(
                Topic.subject_id == subject_id,
                Topic.workspace_id == workspace_id,
                Topic.name == name,
            )
        ).scalar_one_or_none()
        if not row:
            row = Topic(
                name=name,
                subject_id=subject_id,
                workspace_id=workspace_id,
                description=f"Demo topic: {name}",
            )
            db.session.add(row)
            db.session.flush()
        topics.append(row)
    return topics


def _tag_bank_questions(
    bank_id: int,
    topic_ids: list[int],
    difficulties: tuple[str, ...] = ("EASY", "MEDIUM", "HARD"),
) -> int:
    rows = list(
        db.session.execute(
            db.select(Question)
            .where(Question.bank_id == bank_id, Question.status == "ACTIVE")
            .order_by(Question.id)
        ).scalars().unique().all()
    )
    buckets: list[list[Question]] = [[] for _ in topic_ids]
    for index, question in enumerate(rows):
        buckets[index % len(topic_ids)].append(question)
    for topic_id, bucket in zip(topic_ids, buckets):
        for index, question in enumerate(bucket):
            question.topic_id = topic_id
            question.difficulty = difficulties[index % len(difficulties)]
    return len(rows)


def _ensure_draft_test(*, subject_id: int, membership_id: int, slug: str) -> Test:
    existing = db.session.execute(
        db.select(Test).where(
            Test.subject_id == subject_id,
            Test.status == TestStatus.DRAFT.value,
            Test.slug == slug,
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    test = Test(
        name="Blueprint Demo Exam",
        slug=slug,
        description="Auto-created for random-from-banks blueprint testing",
        subject_id=subject_id,
        total_score=Decimal("100"),
        passing_score=Decimal("50"),
        duration_minutes=30,
        created_by_membership_id=membership_id,
        status=TestStatus.DRAFT.value,
    )
    db.session.add(test)
    db.session.flush()
    return test


def run() -> dict:
    """
    Prepares two demo paths:
    - workspace 21 / subject 24 / banks 19+20 (enriches bank 19; bank 20 if empty skipped)
    - workspace 20 / subject 18 / banks 14+16
  """
    summary: dict = {}

    # --- Path A: test 13 style (workspace 21, subject 24) ---
    topics24 = _ensure_topics(
        subject_id=24,
        workspace_id=21,
        names=["Algebra Basics", "Linear Equations", "Quadratic Functions"],
    )
    tagged19 = _tag_bank_questions(19, [t.id for t in topics24])
    summary["workspace_21"] = {
        "subject_id": 24,
        "workspace_id": 21,
        "topics": [{"id": t.id, "name": t.name} for t in topics24],
        "bank_19_questions_tagged": tagged19,
        "test_id": 13,
        "bank_ids": [19, 20, 21],
    }

    # --- Path B: workspace 20 / subject 18 (screenshot banks) ---
    sub18 = db.session.execute(
        db.select(Subject).where(Subject.id == 18, Subject.workspace_id == 20)
    ).scalar_one_or_none()
    if sub18:
        membership = db.session.execute(
            db.select(Membership).where(Membership.workspace_id == 20).limit(1)
        ).scalar_one_or_none()
        if membership:
            topics18 = _ensure_topics(
                subject_id=18,
                workspace_id=20,
                names=["Network Security", "Cryptography", "Ethical Hacking"],
            )
            tagged14 = _tag_bank_questions(14, [t.id for t in topics18])
            tagged16 = _tag_bank_questions(16, [t.id for t in topics18])
            test = _ensure_draft_test(
                subject_id=18,
                membership_id=membership.id,
                slug="blueprint-demo-ws20",
            )
            summary["workspace_20"] = {
                "subject_id": 18,
                "workspace_id": 20,
                "topics": [{"id": t.id, "name": t.name} for t in topics18],
                "bank_14_questions_tagged": tagged14,
                "bank_16_questions_tagged": tagged16,
                "test_id": test.id,
                "bank_ids": [14, 16],
            }

    db.session.commit()
    return summary
