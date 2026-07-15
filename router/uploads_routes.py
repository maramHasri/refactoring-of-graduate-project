from utils.messages import Messages
from pathlib import Path

from flask import Blueprint, current_app, g, request, send_from_directory
from werkzeug.exceptions import NotFound

from router.decorators import handle_service_errors, require_workspace_membership
from service.exceptions import ValidationError
from service.question_image_service import QuestionImageService

uploads_bp = Blueprint("uploads", __name__)


@uploads_bp.route("/images", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def upload_image():
    """
    POST /uploads/images — standalone image upload (reusable across the platform).

    Upload the image first, then pass returned image_path to question create/update APIs.
    """
    image = request.files.get("image")
    if not image:
        raise ValidationError(Messages.IMAGE_FILE_IS_REQUIRED)

    result = QuestionImageService().upload_image(
        image_file=image,
        workspace_id=g.workspace_id,
        owner_user_id=g.current_user.id,
    )
    return {
        "message": Messages.IMAGE_UPLOADED,
        **result,
    }, 201


@uploads_bp.route("/<path:relative_path>", methods=["GET"])
def serve_uploaded_file(relative_path: str):
    base_dir = Path(current_app.config["QUESTION_IMAGE_STORAGE_DIR"]).parent
    target = base_dir / relative_path
    if not target.exists() or not target.is_file():
        raise NotFound("File not found")
    return send_from_directory(base_dir, relative_path, max_age=3600)
