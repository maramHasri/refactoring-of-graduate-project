"""
Student subject assignment APIs — membership-centric bulk operations.

Reuses subject_memberships with subject_role=STUDENT (same table as subject-centric enroll).
"""
from flask import Blueprint, g, request

from router.decorators import handle_service_errors, require_workspace_membership
from schemas.subject_schema import (
    AssignStudentSubjectsSchema,
    ReplaceStudentSubjectsSchema,
)
from service.subject_service import SubjectService

student_membership_bp = Blueprint("student_memberships", __name__)
_svc = lambda: SubjectService()


@student_membership_bp.route("/subjects", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def assign_subjects_to_student():
    """POST /student-memberships/subjects — assign one or more subjects to a student."""
    data = AssignStudentSubjectsSchema().load(request.get_json() or {})
    result = _svc().assign_subjects_to_student(
        workspace_id=g.workspace_id,
        student_membership_id=data["membership_id"],
        subject_ids=data["subject_ids"],
        actor_membership=g.membership,
    )
    return {"message": "Subjects assigned to student", **result}, 201


@student_membership_bp.route("/<int:membership_id>/subjects", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def list_student_subjects(membership_id):
    """GET /student-memberships/{membership_id}/subjects"""
    result = _svc().list_student_subjects(
        workspace_id=g.workspace_id,
        student_membership_id=membership_id,
        actor_membership=g.membership,
    )
    return result, 200


@student_membership_bp.route("/<int:membership_id>/subjects", methods=["PUT"])
@require_workspace_membership
@handle_service_errors
def replace_student_subjects(membership_id):
    """PUT /student-memberships/{membership_id}/subjects — sync assignments."""
    data = ReplaceStudentSubjectsSchema().load(request.get_json() or {})
    result = _svc().replace_student_subjects(
        workspace_id=g.workspace_id,
        student_membership_id=membership_id,
        subject_ids=data["subject_ids"],
        actor_membership=g.membership,
    )
    return {"message": "Student subject assignments updated", **result}, 200


@student_membership_bp.route(
    "/<int:membership_id>/subjects/<int:subject_id>", methods=["DELETE"]
)
@require_workspace_membership
@handle_service_errors
def remove_student_subject(membership_id, subject_id):
    """DELETE /student-memberships/{membership_id}/subjects/{subject_id}"""
    result = _svc().remove_student_subject(
        workspace_id=g.workspace_id,
        student_membership_id=membership_id,
        subject_id=subject_id,
        actor_membership=g.membership,
    )
    return {"message": "Subject removed from student", **result}, 200
