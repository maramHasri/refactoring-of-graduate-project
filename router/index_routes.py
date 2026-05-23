from flask import Blueprint, jsonify, redirect

index_bp = Blueprint("index", __name__)


@index_bp.route("/", methods=["GET"])
def index():
    return jsonify(
        {
            "service": "edu_forms",
            "docs": "/apidocs/",
            "health": "/health",
            "enums": "/api/enums",
            "note": "API endpoints use POST/GET on specific paths. Open /apidocs/ to test.",
        }
    )


@index_bp.route("/docs", methods=["GET"])
def docs_redirect():
    return redirect("/apidocs/", code=302)
