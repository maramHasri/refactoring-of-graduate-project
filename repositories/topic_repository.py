from models import Topic
from repositories.base_repository import BaseRepository
from utils.db import db


class TopicRepository(BaseRepository):
    def get_by_id(self, topic_id: int) -> Topic | None:
        return db.session.get(Topic, topic_id)

    def get_in_subject(
        self, topic_id: int, *, subject_id: int, workspace_id: int
    ) -> Topic | None:
        return db.session.execute(
            db.select(Topic).where(
                Topic.id == topic_id,
                Topic.subject_id == subject_id,
                Topic.workspace_id == workspace_id,
            )
        ).scalar_one_or_none()

    def list_by_subject(self, subject_id: int, workspace_id: int) -> list[Topic]:
        return list(
            db.session.execute(
                db.select(Topic)
                .where(
                    Topic.subject_id == subject_id,
                    Topic.workspace_id == workspace_id,
                )
                .order_by(Topic.name)
            ).scalars().all()
        )

    def find_by_subject_and_name(
        self, subject_id: int, name: str
    ) -> Topic | None:
        return db.session.execute(
            db.select(Topic).where(
                Topic.subject_id == subject_id,
                Topic.name == name,
            )
        ).scalar_one_or_none()
