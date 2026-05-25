from models import QuestionType
from utils.db import db


def seed_question_types():
    defaults = [
        {"name": "MCQ", "code": "MCQ", "description": "Single correct answer"},
        {"name": "TRUE_FALSE", "code": "TRUE_FALSE", "description": "True or false"},
        {"name": "MULTI_SELECT", "code": "MULTI_SELECT", "description": "Multiple correct answers"},
        {"name": "ESSAY", "code": "ESSAY", "description": "Long-form essay answer"},
    ]

    for item in defaults:
        existing = db.session.execute(
            db.select(QuestionType).where(
                (QuestionType.name == item["name"])
                | (QuestionType.code == item["code"])
            )
        ).scalar_one_or_none()
        if existing:
            existing.code = item["code"]
            existing.name = item["name"]
            continue
        db.session.add(QuestionType(**item))
    db.session.commit()
