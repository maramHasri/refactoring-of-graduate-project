"""
Subject APIs — workspace-scoped academic entities.

Uses X-Workspace-Id for tenant context.
subject_memberships stores per-subject TEACHER/STUDENT roles (separate from membership.role).
"""
from flask import Blueprint, g, request

from router.decorators import handle_service_errors, require_workspace_membership
from schemas.subject_schema import (
    AssignMembershipToSubjectSchema,
    CreateSubjectSchema,
    UpdateSubjectSchema,
)
from schemas.topic_schema import CreateTopicSchema, UpdateTopicSchema
from service.question_bank_service import QuestionBankService
from service.subject_service import SubjectService
from service.topic_service import TopicService

subject_bp = Blueprint("subjects", __name__)
_svc = lambda: SubjectService()
_topic_svc = lambda: TopicService()


@subject_bp.route("", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def create_subject():
    """POST /subjects — owner/admin creates a subject in the active workspace."""
    data = CreateSubjectSchema().load(request.get_json() or {})
    subject = _svc().create_subject(
        workspace_id=g.workspace_id,
        name=data["name"],
        description=data.get("description"),
        actor_membership=g.membership,
    )
    return {"message": "Subject created", "subject": _svc()._serialize_subject(subject)}, 201


@subject_bp.route("", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def list_subjects():
    """GET /subjects — list non-deleted subjects (filtered by role)."""
    items = _svc().list_workspace_subjects(g.workspace_id, g.membership)
    return {"subjects": items, "count": len(items)}, 200


@subject_bp.route("/<int:subject_id>", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def get_subject(subject_id):
    """GET /subjects/{id} — subject details."""
    data = _svc().get_subject(subject_id, g.workspace_id, g.membership)
    return data, 200


@subject_bp.route("/<int:subject_id>", methods=["PATCH"])
@require_workspace_membership
@handle_service_errors
def update_subject(subject_id):
    """PATCH /subjects/{id} — owner/admin updates subject."""
    data = UpdateSubjectSchema().load(request.get_json() or {}, partial=True)
    subject = _svc().update_subject(
        subject_id, g.workspace_id, g.membership, data
    )
    return {"message": "Subject updated", "subject": _svc()._serialize_subject(subject)}, 200


@subject_bp.route("/<int:subject_id>", methods=["DELETE"])
@require_workspace_membership
@handle_service_errors
def delete_subject(subject_id):
    """DELETE /subjects/{id} — soft delete / archive (no hard delete)."""
    subject = _svc().archive_subject(subject_id, g.workspace_id, g.membership)
    return {"message": "Subject archived", "subject": _svc()._serialize_subject(subject)}, 200


@subject_bp.route("/<int:subject_id>/teachers", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def assign_teacher(subject_id):
    """POST /subjects/{id}/teachers — assign teacher (subject_role=TEACHER)."""
    data = AssignMembershipToSubjectSchema().load(request.get_json() or {})
    link = _svc().assign_teacher_to_subject(
        workspace_id=g.workspace_id,
        subject_id=subject_id,
        teacher_membership_id=data["membership_id"],
        actor_membership=g.membership,
    )
    return {
        "message": "Teacher assigned to subject",
        "assignment": _svc()._serialize_assignment(link),
    }, 201


@subject_bp.route(
    "/<int:subject_id>/teachers/<int:membership_id>", methods=["DELETE"]
)
@require_workspace_membership
@handle_service_errors
def remove_teacher(subject_id, membership_id):
    """DELETE /subjects/{id}/teachers/{membership_id}"""
    _svc().remove_teacher_from_subject(
        workspace_id=g.workspace_id,
        subject_id=subject_id,
        teacher_membership_id=membership_id,
        actor_membership=g.membership,
    )
    return {"message": "Teacher removed from subject"}, 200


@subject_bp.route("/<int:subject_id>/teachers", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def list_teachers(subject_id):
    """GET /subjects/{id}/teachers"""
    items = _svc().list_subject_teachers(subject_id, g.workspace_id, g.membership)
    return {"teachers": items, "count": len(items)}, 200


@subject_bp.route("/<int:subject_id>/students", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def enroll_student(subject_id):
    """POST /subjects/{id}/students — admin/owner or assigned subject teacher."""
    data = AssignMembershipToSubjectSchema().load(request.get_json() or {})
    link = _svc().enroll_student_in_subject(
        workspace_id=g.workspace_id,
        subject_id=subject_id,
        student_membership_id=data["membership_id"],
        actor_membership=g.membership,
    )
    return {
        "message": "Student enrolled in subject",
        "assignment": _svc()._serialize_assignment(link),
    }, 201


@subject_bp.route(
    "/<int:subject_id>/students/<int:membership_id>", methods=["DELETE"]
)
@require_workspace_membership
@handle_service_errors
def remove_student(subject_id, membership_id):
    """DELETE /subjects/{id}/students/{membership_id}"""
    _svc().remove_student_from_subject(
        workspace_id=g.workspace_id,
        subject_id=subject_id,
        student_membership_id=membership_id,
        actor_membership=g.membership,
    )
    return {"message": "Student removed from subject"}, 200


@subject_bp.route("/<int:subject_id>/students", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def list_students(subject_id):
    """GET /subjects/{id}/students — teachers only see students in subjects they teach."""
    items = _svc().list_subject_students(subject_id, g.workspace_id, g.membership)
    return {"students": items, "count": len(items)}, 200


@subject_bp.route("/<int:subject_id>/topics", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def create_subject_topic(subject_id):
    """
    POST /subjects/{id}/topics — workspace admin/owner or subject-assigned TEACHER.
    """
    data = CreateTopicSchema().load(request.get_json() or {})
    topic = _topic_svc().create_topic(
        workspace_id=g.workspace_id,
        subject_id=subject_id,
        name=data["name"],
        code=data.get("code"),
        actor_membership=g.membership,
    )
    return {
        "message": "Topic created",
        "topic": _topic_svc().serialize_topic(topic),
    }, 201


@subject_bp.route("/<int:subject_id>/topics", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def list_subject_topics(subject_id):
    """GET /subjects/{id}/topics — anyone with active subject assignment (or admin)."""
    items = _topic_svc().list_subject_topics(
        workspace_id=g.workspace_id,
        subject_id=subject_id,
        actor_membership=g.membership,
    )
    return {"topics": items, "count": len(items)}, 200


@subject_bp.route("/<int:subject_id>/topics/<int:topic_id>", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def get_subject_topic(subject_id, topic_id):
    """GET /subjects/{id}/topics/{topicId}"""
    topic = _topic_svc().get_topic(
        workspace_id=g.workspace_id,
        subject_id=subject_id,
        topic_id=topic_id,
        actor_membership=g.membership,
    )
    return {"topic": topic}, 200


@subject_bp.route("/<int:subject_id>/topics/<int:topic_id>", methods=["PATCH"])
@require_workspace_membership
@handle_service_errors
def update_subject_topic(subject_id, topic_id):
    """PATCH /subjects/{id}/topics/{topicId} — admin or subject TEACHER."""
    data = UpdateTopicSchema().load(request.get_json() or {}, partial=True)
    topic = _topic_svc().update_topic(
        workspace_id=g.workspace_id,
        subject_id=subject_id,
        topic_id=topic_id,
        actor_membership=g.membership,
        data=data,
    )
    return {
        "message": "Topic updated",
        "topic": _topic_svc().serialize_topic(topic),
    }, 200


@subject_bp.route("/<int:subject_id>/topics/<int:topic_id>", methods=["DELETE"])
@require_workspace_membership
@handle_service_errors
def delete_subject_topic(subject_id, topic_id):
    """DELETE /subjects/{id}/topics/{topicId} — admin or subject TEACHER."""
    _topic_svc().delete_topic(
        workspace_id=g.workspace_id,
        subject_id=subject_id,
        topic_id=topic_id,
        actor_membership=g.membership,
    )
    return {"message": "Topic deleted"}, 200


@subject_bp.route("/<int:subject_id>/question-banks", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def list_subject_question_banks(subject_id):
    """GET /subjects/{id}/question-banks — visibility rules applied."""
    items = QuestionBankService().list_subject_question_banks(
        workspace_id=g.workspace_id,
        subject_id=subject_id,
        actor_membership=g.membership,
    )
    return {"question_banks": items, "count": len(items)}, 200
