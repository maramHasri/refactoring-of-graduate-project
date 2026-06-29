from pathlib import Path

from flask import Blueprint, send_file

from router.decorators import handle_service_errors, require_workspace_membership

template_bp = Blueprint("templates", __name__)

_EXAM_QUESTIONS_CSV = (
    Path(__file__).resolve().parent.parent
    / "resources"
    / "templates"
    / "exam_questions_template.csv"
)


@template_bp.route("/exam-questions-csv", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def download_exam_questions_csv_template():
    return send_file(
        _EXAM_QUESTIONS_CSV,
        mimetype="text/csv",
        as_attachment=True,
        download_name="exam_questions_template.csv",
    )
