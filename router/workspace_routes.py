from flask import Blueprint, g, request

from router.decorators import handle_service_errors, require_auth, require_workspace_membership
from schemas.workspace_schema import (
    CreateWorkspaceSchema,
    UpdateWorkspaceMemberSchema,
    UpdateWorkspaceSchema,
    WorkspaceMemberRemoveQuerySchema,
    WorkspaceMembersListQuerySchema,
    WorkspaceRecentlyActiveQuerySchema,
)
from service.workspace_service import WorkspaceService

workspace_bp = Blueprint("workspaces", __name__)


@workspace_bp.route("", methods=["POST"])
@require_auth
@handle_service_errors
def create_workspace():
    """
    POST /workspaces — authenticated user creates workspace (write).
    Must NOT: used for student join-code flow (see /join-codes/register-student).
    """
    payload = CreateWorkspaceSchema().load(request.get_json() or {})
    result = WorkspaceService().create_workspace(
        user_id=g.current_user.id,
        name=payload["name"],
        kind=payload["kind"],
        slug=payload.get("slug"),
        logo_url=payload.get("logo_url"),
        description=payload.get("description"),
    )
    return {"message": "Workspace created", **result}, 201


@workspace_bp.route("", methods=["GET"])
@require_auth
@handle_service_errors
def list_workspaces():
    """
    GET /workspaces — workspaces accessible after login.
    Read-only.
    """
    items = WorkspaceService().list_accessible_workspaces(
        g.current_user.id,
        is_superadmin=g.current_user.is_superadmin,
    )
    return {"workspaces": items, "count": len(items)}, 200


@workspace_bp.route("/teachers", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def list_institution_workspace_teachers():
    """
    GET /workspaces/teachers — teachers in the active institution workspace.
    Requires X-Workspace-Id. Institution owner or workspace ADMIN only.
    """
    query = WorkspaceMembersListQuerySchema().load(request.args.to_dict())
    return WorkspaceService().list_institution_workspace_teachers(
        g.workspace_id,
        g.membership,
        page=query.get("page"),
        per_page=query.get("per_page"),
        search=query.get("search"),
    ), 200


@workspace_bp.route("/teachers", methods=["DELETE"])
@require_workspace_membership
@handle_service_errors
def remove_institution_workspace_teacher():
    """
    DELETE /workspaces/teachers?membership_id= — remove teacher from institution workspace.
    Requires X-Workspace-Id. Institution owner or workspace ADMIN only.
    """
    query = WorkspaceMemberRemoveQuerySchema().load(request.args.to_dict())
    return WorkspaceService().remove_teacher_from_workspace(
        g.workspace_id,
        g.membership,
        query["membership_id"],
    ), 200


@workspace_bp.route("/students", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def list_institution_workspace_students():
    """
    GET /workspaces/students — students in the active institution workspace.
    Requires X-Workspace-Id. Institution owner or workspace ADMIN only.
    """
    query = WorkspaceMembersListQuerySchema().load(request.args.to_dict())
    return WorkspaceService().list_institution_workspace_students(
        g.workspace_id,
        g.membership,
        page=query.get("page"),
        per_page=query.get("per_page"),
        search=query.get("search"),
    ), 200


@workspace_bp.route("/students", methods=["DELETE"])
@require_workspace_membership
@handle_service_errors
def remove_workspace_student():
    """
    DELETE /workspaces/students?membership_id= — remove student from active workspace.
    Requires X-Workspace-Id. Workspace owner or ADMIN only.
    """
    query = WorkspaceMemberRemoveQuerySchema().load(request.args.to_dict())
    return WorkspaceService().remove_student_from_workspace(
        g.workspace_id,
        g.membership,
        query["membership_id"],
    ), 200


@workspace_bp.route("/members/recently-active", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def list_recently_active_workspace_members():
    """
    GET /workspaces/members/recently-active — members active in the last 24 hours.
    Requires X-Workspace-Id. INSTITUTION or SOLO; workspace owner or ADMIN only.
    """
    query = WorkspaceRecentlyActiveQuerySchema().load(request.args.to_dict())
    return WorkspaceService().list_recently_active_members(
        g.workspace_id,
        g.membership,
        role=query.get("role"),
    ), 200


@workspace_bp.route("/members/<int:membership_id>", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def get_workspace_member_details(membership_id):
    """
    GET /workspaces/members/{membership_id} — student or teacher detail.
    Requires X-Workspace-Id. INSTITUTION or SOLO; workspace owner or ADMIN only.
    """
    return WorkspaceService().get_workspace_member_details(
        g.workspace_id,
        g.membership,
        membership_id,
    ), 200


@workspace_bp.route("/members/<int:membership_id>", methods=["PATCH"])
@require_workspace_membership
@handle_service_errors
def update_workspace_member(membership_id):
    """
    PATCH /workspaces/members/{membership_id} — update member user profile fields.
    Requires X-Workspace-Id. Workspace owner or ADMIN only.
    Updates User fields only (full_name, phone_number, avatar). Email cannot be changed by admins.
    """
    payload = UpdateWorkspaceMemberSchema().load(request.get_json() or {}, partial=True)
    return WorkspaceService().update_workspace_member(
        g.workspace_id,
        g.membership,
        membership_id,
        payload,
    ), 200


@workspace_bp.route("/<int:workspace_id>", methods=["GET"])
@require_auth
@handle_service_errors
def get_workspace(workspace_id):
    data = WorkspaceService().get_workspace(
        workspace_id,
        g.current_user.id,
        is_superadmin=g.current_user.is_superadmin,
    )
    return data, 200


@workspace_bp.route("/<int:workspace_id>", methods=["PATCH"])
@require_auth
@handle_service_errors
def update_workspace(workspace_id):
    payload = UpdateWorkspaceSchema().load(request.get_json() or {}, partial=True)
    workspace = WorkspaceService().update_workspace(
        workspace_id,
        g.current_user.id,
        is_superadmin=g.current_user.is_superadmin,
        data=payload,
    )
    return {"message": "Workspace updated", "id": workspace.id}, 200


@workspace_bp.route("/<int:workspace_id>", methods=["DELETE"])
@require_auth
@handle_service_errors
def delete_workspace(workspace_id):
    WorkspaceService().delete_workspace(
        workspace_id,
        g.current_user.id,
        is_superadmin=g.current_user.is_superadmin,
    )
    return {"message": "Workspace deleted"}, 200
