"""
Subject topics — curriculum taxonomy per subject.
"""
from models import Topic
from repositories.question_repository import QuestionRepository
from repositories.subject_repository import (
    SubjectMembershipRepository,
    SubjectRepository,
)
from repositories.topic_repository import TopicRepository
from repositories.workspace_repository import WorkspaceRepository
from service.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from utils.academic_rbac import can_manage_subjects, can_view_subject_topics
from utils.db import db


class TopicService:
    def __init__(self):
        self.topics = TopicRepository()
        self.subjects = SubjectRepository()
        self.subject_memberships = SubjectMembershipRepository()
        self.workspaces = WorkspaceRepository()
        self.questions = QuestionRepository()

    def create_topic(
        self,
        *,
        workspace_id: int,
        subject_id: int,
        name: str,
        actor_membership,
        description: str | None = None,
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
            description=(description or "").strip() or None,
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
        if "description" in data:
            topic.description = (data.get("description") or "").strip() or None

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
        question_count = self.questions.count_by_topic_id(topic.id)
        if question_count > 0:
            raise ValidationError(
                f"Cannot delete topic: {question_count} question(s) still reference it"
            )
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

        if not can_manage_subjects(workspace, actor_membership):
            raise ForbiddenError("Only workspace owner or admin can manage topics")
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
            "description": topic.description,
            "subject_id": topic.subject_id,
            "workspace_id": topic.workspace_id,
            "created_at": topic.created_at.isoformat() if topic.created_at else None,
            "updated_at": topic.updated_at.isoformat() if topic.updated_at else None,
        }
