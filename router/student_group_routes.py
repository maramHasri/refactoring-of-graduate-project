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
    """POST /subjects/{subject_id}/groups — create a student group in a subject."""
    data = CreateStudentGroupSchema().load(request.get_json() or {})
    group = _svc().create_group(
        workspace_id=g.workspace_id,
        subject_id=subject_id,
        name=data["name"],
        description=data.get("description"),
        actor_membership=g.membership,
    )
    return {
        "message": "Group created successfully",
        "group": _svc()._serialize_group(group),
    }, 201


@student_group_bp.route("/subjects/<int:subject_id>/groups", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def list_subject_student_groups(subject_id):
    """GET /subjects/{subject_id}/groups — list groups for a subject."""
    items = _svc().list_subject_groups(
        workspace_id=g.workspace_id,
        subject_id=subject_id,
        actor_membership=g.membership,
    )
    return {"groups": items, "count": len(items)}, 200


@student_group_bp.route("/groups/<int:group_id>", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def get_student_group(group_id):
    """GET /groups/{group_id} — group details with member list."""
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
    """PUT /groups/{group_id} — update group name and/or description."""
    data = UpdateStudentGroupSchema().load(request.get_json() or {})
    group = _svc().update_group(
        workspace_id=g.workspace_id,
        group_id=group_id,
        actor_membership=g.membership,
        data=data,
    )
    return {
        "message": "Group updated successfully",
        "group": _svc()._serialize_group(group),
    }, 200


@student_group_bp.route("/groups/<int:group_id>", methods=["DELETE"])
@require_workspace_membership
@handle_service_errors
def delete_student_group(group_id):
    """DELETE /groups/{group_id} — delete group and its memberships only."""
    _svc().delete_group(
        workspace_id=g.workspace_id,
        group_id=group_id,
        actor_membership=g.membership,
    )
    return {"message": "Group deleted successfully"}, 200


@student_group_bp.route("/groups/<int:group_id>/members", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def add_student_group_members(group_id):
    """POST /groups/{group_id}/members — add students to a group."""
    data = AddStudentGroupMembersSchema().load(request.get_json() or {})
    result = _svc().add_members(
        workspace_id=g.workspace_id,
        group_id=group_id,
        student_ids=data["student_ids"],
        actor_membership=g.membership,
    )
    return {
        "message": "Group members updated",
        **result,
    }, 200


@student_group_bp.route(
    "/groups/<int:group_id>/members/<int:student_id>", methods=["DELETE"]
)
@require_workspace_membership
@handle_service_errors
def remove_student_group_member(group_id, student_id):
    """DELETE /groups/{group_id}/members/{student_id} — remove one member."""
    _svc().remove_member(
        workspace_id=g.workspace_id,
        group_id=group_id,
        student_id=student_id,
        actor_membership=g.membership,
    )
    return {"message": "Member removed from group"}, 200
