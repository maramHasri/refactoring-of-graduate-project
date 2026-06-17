from flask import Blueprint, current_app, g, request

from router.decorators import handle_service_errors, require_auth, require_workspace_membership
from schemas.workspace_schema import CreateInviteSchema, RegisterThroughInviteSchema
from service.exceptions import ConflictError
from service.invite_service import InviteService
from utils.enums import MembershipRole

invite_bp = Blueprint("invites", __name__)


@invite_bp.route("", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def create_invite():
    """
    POST /invites — create email invitation (write).
    ADMIN: ADMIN/TEACHER/STUDENT. TEACHER: STUDENT only.
    """
    if g.membership and g.membership.role == MembershipRole.STUDENT.value:
        from service.exceptions import ForbiddenError

        raise ForbiddenError("Students cannot send invitations")

    data = CreateInviteSchema().load(request.get_json() or {})
    inviter_role = g.membership.role if g.membership else None
    invite, raw = InviteService().create_invite(
        workspace_id=g.workspace_id,
        email=data["email"],
        assigned_role=data["assigned_role"],
        invited_by_membership_id=g.membership.id if g.membership else None,
        inviter_role=inviter_role,
        is_superadmin=g.current_user.is_superadmin,
    )
    from utils.dev_invite import attach_dev_invite, should_expose_invite_in_response

    response = {
        "invite_id": invite.id,
        "invited_email": invite.invited_email,
        "assigned_role": invite.assigned_role,
        "expires_at": invite.expires_at.isoformat(),
    }
    if should_expose_invite_in_response():
        response = attach_dev_invite(response, raw_token=raw)
        response["preview_url"] = f"{request.url_root.rstrip('/')}/invites/{raw}"
        response["register_url"] = (
            f"{request.url_root.rstrip('/')}/invites/{raw}/register"
        )
        response["accept_url"] = (
            f"{request.url_root.rstrip('/')}/invites/{raw}/accept"
        )
    return response, 201


@invite_bp.route("/<token>", methods=["GET"])
@handle_service_errors
def preview_invite(token):
    """
    GET /invites/{token} — read-only preview. No authentication required.
    """
    data = InviteService().preview_invite(token)
    return data, 200


@invite_bp.route("/<token>/register", methods=["POST"])
@handle_service_errors
def register_through_invite(token):
    """
    POST /invites/{token}/register — new user via invitation (no auth).
    """
    data = RegisterThroughInviteSchema().load(request.get_json() or {})
    try:
        result = InviteService().register_through_invite(
            token, full_name=data["full_name"], password=data["password"]
        )
        return result, 201
    except ConflictError as exc:
        if "already exists" in exc.message.lower():
            return {"message": exc.message}, 409
        raise


@invite_bp.route("/<token>/accept", methods=["POST"])
@require_auth
@handle_service_errors
def accept_invite(token):
    """
    POST /invites/{token}/accept — existing authenticated user joins workspace.
    """
    membership = InviteService().accept_invite(token, g.current_user.id)
    return {
        "message": "Invitation accepted",
        "membership_id": membership.id,
        "workspace_id": membership.workspace_id,
        "role": membership.role,
    }, 200


@invite_bp.route("/<token>/reject", methods=["POST"])
@handle_service_errors
def reject_invite(token):
    """
    POST /invites/{token}/reject — reject invitation (no auth required).
    """
    InviteService().reject_invite(token)
    return {"message": "Invitation rejected"}, 200
