from router.index_routes import index_bp
from router.health_routes import health_bp
from router.auth_routes import auth_bp
from router.workspace_routes import workspace_bp
from router.invite_routes import invite_bp
from router.join_code_routes import join_bp
from router.subject_routes import subject_bp
from router.question_bank_routes import question_bank_bp
from router.admin_routes import admin_bp


def register_blueprints(app):
    app.register_blueprint(index_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(workspace_bp, url_prefix="/workspaces")
    app.register_blueprint(invite_bp, url_prefix="/invites")
    app.register_blueprint(join_bp, url_prefix="/join-codes")
    app.register_blueprint(subject_bp, url_prefix="/subjects")
    app.register_blueprint(question_bank_bp, url_prefix="/question-banks")
    app.register_blueprint(admin_bp, url_prefix="/admin")
