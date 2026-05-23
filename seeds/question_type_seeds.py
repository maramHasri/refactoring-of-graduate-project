from models import QuestionType
from utils.db import db


def seed_question_types():
    defaults = [
        {"name": "MCQ", "code": "mcq", "description": "Single choice multiple choice"},
        {"name": "TRUE_FALSE", "code": "tf", "description": "True or false question"},
        {"name": "ESSAY", "code": "essay", "description": "Long-form essay answer"},
        {"name": "MULTI_SELECT", "code": "multi_select", "description": "Multiple correct answers"},
    ]

    for item in defaults:
        existing = db.session.execute(
            db.select(QuestionType).where(QuestionType.name == item["name"])
        ).scalar_one_or_none()
        if existing:
            continue
        db.session.add(QuestionType(**item))
    db.session.commit()
