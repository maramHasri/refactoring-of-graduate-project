"""
Subject topics — global taxonomy per subject; teachers may create and manage.
"""
from models import Topic
from repositories.subject_repository import (
    SubjectMembershipRepository,
    SubjectRepository,
)
from repositories.topic_repository import TopicRepository
from repositories.workspace_repository import WorkspaceRepository
from service.exceptions import ConflictError, ForbiddenError, NotFoundError
from utils.academic_rbac import can_manage_subject_topics, can_view_subject_topics
from utils.db import db


class TopicService:
    def __init__(self):
        self.topics = TopicRepository()
        self.subjects = SubjectRepository()
        self.subject_memberships = SubjectMembershipRepository()
        self.workspaces = WorkspaceRepository()

    def create_topic(
        self,
        *,
        workspace_id: int,
        subject_id: int,
        name: str,
        actor_membership,
        code: str | None = None,
    ) -> Topic:
        subject = self._resolve_subject_for_topic_write(
            workspace_id=workspace_id,
            subject_id=subject_id,
            actor_membership=actor_membership,
        )
        name = name.strip()
        if self.topics.find_by_subject_and_name(subject.id, name):
            raise ConflictError("A topic with this name already exists in the subject")

        topic = Topic(
            name=name,
            code=code.strip() if code else None,
            workspace_id=workspace_id,
            subject_id=subject.id,
        )
        self.topics.add(topic)
        db.session.commit()
        return topic

    def list_subject_topics(
        self, *, workspace_id: int, subject_id: int, actor_membership
    ) -> list[dict]:
        self._resolve_subject_for_topic_view(
            workspace_id=workspace_id,
            subject_id=subject_id,
            actor_membership=actor_membership,
        )
        rows = self.topics.list_by_subject(subject_id, workspace_id)
        return [self.serialize_topic(t) for t in rows]

    def get_topic(
        self,
        *,
        workspace_id: int,
        subject_id: int,
        topic_id: int,
        actor_membership,
    ) -> dict:
        self._resolve_subject_for_topic_view(
            workspace_id=workspace_id,
            subject_id=subject_id,
            actor_membership=actor_membership,
        )
        topic = self._get_topic_or_404(topic_id, subject_id, workspace_id)
        return self.serialize_topic(topic)

    def update_topic(
        self,
        *,
        workspace_id: int,
        subject_id: int,
        topic_id: int,
        actor_membership,
        data: dict,
    ) -> Topic:
        self._resolve_subject_for_topic_write(
            workspace_id=workspace_id,
            subject_id=subject_id,
            actor_membership=actor_membership,
        )
        topic = self._get_topic_or_404(topic_id, subject_id, workspace_id)

        if "name" in data and data["name"]:
            name = data["name"].strip()
            existing = self.topics.find_by_subject_and_name(subject_id, name)
            if existing and existing.id != topic.id:
                raise ConflictError("A topic with this name already exists in the subject")
            topic.name = name
        if "code" in data:
            topic.code = data["code"]

        db.session.commit()
        return topic

    def delete_topic(
        self,
        *,
        workspace_id: int,
        subject_id: int,
        topic_id: int,
        actor_membership,
    ) -> None:
        self._resolve_subject_for_topic_write(
            workspace_id=workspace_id,
            subject_id=subject_id,
            actor_membership=actor_membership,
        )
        topic = self._get_topic_or_404(topic_id, subject_id, workspace_id)
        db.session.delete(topic)
        db.session.commit()

    def _resolve_subject_for_topic_write(
        self, *, workspace_id: int, subject_id: int, actor_membership
    ):
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found")

        subject = self.subjects.get_active_by_id(subject_id, workspace_id)
        if not subject:
            raise NotFoundError("Subject not found")

        actor_link = self.subject_memberships.find_active(
            actor_membership.id, subject_id
        )
        if not can_manage_subject_topics(
            workspace, actor_link, actor=actor_membership
        ):
            raise ForbiddenError(
                "You must be assigned to this subject as TEACHER to manage topics"
            )
        return subject

    def _resolve_subject_for_topic_view(
        self, *, workspace_id: int, subject_id: int, actor_membership
    ):
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found")

        subject = self.subjects.get_active_by_id(subject_id, workspace_id)
        if not subject:
            raise NotFoundError("Subject not found")

        actor_link = self.subject_memberships.find_active(
            actor_membership.id, subject_id
        )
        if not can_view_subject_topics(
            workspace, actor_link, actor=actor_membership
        ):
            raise ForbiddenError(
                "You need an active assignment to this subject to access topics"
            )
        return subject

    def _get_topic_or_404(
        self, topic_id: int, subject_id: int, workspace_id: int
    ) -> Topic:
        topic = self.topics.get_in_subject(
            topic_id, subject_id=subject_id, workspace_id=workspace_id
        )
        if not topic:
            raise NotFoundError("Topic not found")
        return topic

    def serialize_topic(self, topic: Topic) -> dict:
        return {
            "id": topic.id,
            "name": topic.name,
            "code": topic.code,
            "subject_id": topic.subject_id,
            "workspace_id": topic.workspace_id,
        }
