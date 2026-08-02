from router.index_routes import index_bp
from router.health_routes import health_bp
from router.auth_routes import auth_bp
from router.user_routes import user_bp
from router.workspace_routes import workspace_bp
from router.invite_routes import invite_bp
from router.join_code_routes import join_bp
from router.student_membership_routes import student_membership_bp
from router.subject_routes import subject_bp
from router.question_bank_routes import question_bank_bp
from router.admin_routes import admin_bp
from router.test_routes import test_bp
from router.attempt_routes import attempt_bp
from router.student_routes import student_bp
from router.grading_routes import grading_bp
from router.proctoring_routes import proctoring_bp
from router.proctoring_integrity_report_routes import integrity_report_bp
from router.template_routes import template_bp
from router.uploads_routes import uploads_bp
from router.student_group_routes import student_group_bp
from router.ai_generation_routes import ai_generation_bp
from router.report_routes import report_bp
from router.super_admin_dashboard_routes import super_admin_dashboard_bp
from router.super_admin_management_routes import super_admin_management_bp


def register_blueprints(app):
    app.register_blueprint(index_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(user_bp, url_prefix="/users")
    app.register_blueprint(workspace_bp, url_prefix="/workspaces")
    app.register_blueprint(invite_bp, url_prefix="/invites")
    app.register_blueprint(join_bp, url_prefix="/join-codes")
    app.register_blueprint(subject_bp, url_prefix="/subjects")
    app.register_blueprint(student_membership_bp, url_prefix="/student-memberships")
    app.register_blueprint(question_bank_bp, url_prefix="/question-banks")
    app.register_blueprint(test_bp, url_prefix="/tests")
    app.register_blueprint(attempt_bp, url_prefix="/tests")
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(grading_bp, url_prefix="/tests")
    app.register_blueprint(proctoring_bp, url_prefix="/tests")
    app.register_blueprint(integrity_report_bp, url_prefix="/proctoring")
    app.register_blueprint(template_bp, url_prefix="/templates")
    app.register_blueprint(uploads_bp, url_prefix="/uploads")
    app.register_blueprint(student_group_bp)
    app.register_blueprint(ai_generation_bp)
    app.register_blueprint(report_bp, url_prefix="/reports")
    app.register_blueprint(super_admin_dashboard_bp, url_prefix="/api/super-admin")
    app.register_blueprint(super_admin_management_bp, url_prefix="/api/super-admin")
    app.register_blueprint(admin_bp, url_prefix="/admin")
