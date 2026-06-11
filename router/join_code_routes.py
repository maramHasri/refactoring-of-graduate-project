from flask import Blueprint, g, request

from router.decorators import handle_service_errors, require_auth
from schemas.auth_schema import JoinWithCodeSchema, RegisterStudentSchema
from service.auth_service import AuthService
from service.join_code_service import JoinCodeService

join_bp = Blueprint("join_codes", __name__)


@join_bp.route("/register-student", methods=["POST"])
@handle_service_errors
def register_student():
    """
    POST /join-codes/register-student — new student account + STUDENT membership via join code.
    """
    data = RegisterStudentSchema().load(request.get_json() or {})
    result = AuthService().register_student_with_join_code(**data)
    return {
        "message": "Student registered. Check your email for the verification code.",
        **result,
    }, 201


@join_bp.route("/join", methods=["POST"])
@require_auth
@handle_service_errors
def join_with_code():
    """
    POST /join-codes/join — existing user joins as STUDENT (write).
    """
    data = JoinWithCodeSchema().load(request.get_json() or {})
    membership = JoinCodeService().join_workspace_with_code(
        user_id=g.current_user.id,
        join_code=data["join_code"],
    )
    return {
        "message": "Joined workspace",
        "membership_id": membership.id,
        "workspace_id": membership.workspace_id,
        "role": membership.role,
    }, 201
