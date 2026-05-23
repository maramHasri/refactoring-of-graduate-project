from flask import Blueprint, g, request

from router.decorators import handle_service_errors, require_auth, require_workspace_membership
from schemas.workspace_schema import CreateWorkspaceSchema, UpdateWorkspaceSchema
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
