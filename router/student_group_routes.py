from utils.messages import Messages
from flask import Blueprint, g, request

from router.decorators import handle_service_errors, require_workspace_membership
from schemas.student_group_schema import (
    AddStudentGroupMembersSchema,
    CreateStudentGroupSchema,
    UpdateStudentGroupSchema,
)
from service.student_group_service import StudentGroupService

student_group_bp = Blueprint("student_groups", __name__)
_svc = lambda: StudentGroupService()


@student_group_bp.route("/subjects/<int:subject_id>/groups", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def create_student_group(subject_id):
    """POST /subjects/{subject_id}/groups — assigned subject teacher creates a group."""
    data = CreateStudentGroupSchema().load(request.get_json() or {})
    group = _svc().create_group(
        workspace_id=g.workspace_id,
        subject_id=subject_id,
        name=data["name"],
        description=data.get("description"),
        actor_membership=g.membership,
    )
    return {
        "message": Messages.GROUP_CREATED_SUCCESSFULLY,
        "group": _svc()._serialize_group(group),
    }, 201


@student_group_bp.route("/subjects/<int:subject_id>/groups", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def list_subject_student_groups(subject_id):
    """GET /subjects/{subject_id}/groups — teacher: own groups; admin: all groups."""
    items = _svc().list_subject_groups(
        workspace_id=g.workspace_id,
        subject_id=subject_id,
        actor_membership=g.membership,
    )
    return {"groups": items, "count": len(items)}, 200


@student_group_bp.route(
    "/subjects/<int:subject_id>/groups/available-students", methods=["GET"]
)
@require_workspace_membership
@handle_service_errors
def list_group_available_students(subject_id):
    """GET /subjects/{subject_id}/groups/available-students — enrolled students + group status."""
    items = _svc().list_available_students(
        workspace_id=g.workspace_id,
        subject_id=subject_id,
        actor_membership=g.membership,
    )
    return {"students": items, "count": len(items)}, 200


@student_group_bp.route("/groups/<int:group_id>", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def get_student_group(group_id):
    """GET /groups/{group_id} — owner or workspace admin."""
    data = _svc().get_group(
        workspace_id=g.workspace_id,
        group_id=group_id,
        actor_membership=g.membership,
    )
    return data, 200


@student_group_bp.route("/groups/<int:group_id>", methods=["PUT"])
@require_workspace_membership
@handle_service_errors
def update_student_group(group_id):
    """PUT /groups/{group_id} — group owner only."""
    data = UpdateStudentGroupSchema().load(request.get_json() or {})
    group = _svc().update_group(
        workspace_id=g.workspace_id,
        group_id=group_id,
        actor_membership=g.membership,
        data=data,
    )
    return {
        "message": Messages.GROUP_UPDATED_SUCCESSFULLY,
        "group": _svc()._serialize_group(group),
    }, 200


@student_group_bp.route("/groups/<int:group_id>", methods=["DELETE"])
@require_workspace_membership
@handle_service_errors
def delete_student_group(group_id):
    """DELETE /groups/{group_id} — group owner only; hard-deletes members."""
    _svc().delete_group(
        workspace_id=g.workspace_id,
        group_id=group_id,
        actor_membership=g.membership,
    )
    return {"message": Messages.GROUP_DELETED_SUCCESSFULLY}, 200


@student_group_bp.route("/groups/<int:group_id>/members", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def add_student_group_members(group_id):
    """POST /groups/{group_id}/members — owner only; atomic subject-wide uniqueness."""
    data = AddStudentGroupMembersSchema().load(request.get_json() or {})
    result = _svc().add_members(
        workspace_id=g.workspace_id,
        group_id=group_id,
        student_ids=data["student_ids"],
        actor_membership=g.membership,
    )
    return {
        "message": Messages.GROUP_MEMBERS_UPDATED,
        **result,
    }, 200


@student_group_bp.route(
    "/groups/<int:group_id>/members/<int:student_id>", methods=["DELETE"]
)
@require_workspace_membership
@handle_service_errors
def remove_student_group_member(group_id, student_id):
    """DELETE /groups/{group_id}/members/{student_id} — owner only; keeps subject enrollment."""
    _svc().remove_member(
        workspace_id=g.workspace_id,
        group_id=group_id,
        student_id=student_id,
        actor_membership=g.membership,
    )
    return {"message": Messages.MEMBER_REMOVED_FROM_GROUP}, 200
