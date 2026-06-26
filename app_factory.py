import os

from flask import Flask
from flask_cors import CORS
from flasgger import Swagger

from config import get_config
from router import register_blueprints
from utils.db import db, migrate


def _init_swagger(app: Flask) -> None:
    template_path = os.path.join(
        os.path.dirname(__file__), "swagger", "template.yml"
    )
    Swagger(
        app,
        template_file=template_path,
        config={
            "headers": [],
            "specs": [
                {
                    "endpoint": "apispec",
                    "route": "/apispec.json",
                    "rule_filter": lambda rule: True,
                    "model_filter": lambda tag: True,
                }
            ],
            "static_url_path": "/flasgger_static",
            "swagger_ui": True,
            "specs_route": "/apidocs/",
        },
    )


def create_app(config_class=None):
    app = Flask(__name__)
    app.config.from_object(config_class or get_config())

    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app)

    import models  # noqa: F401 — register models with SQLAlchemy metadata

    register_blueprints(app)
    _init_swagger(app)

    from router.proctoring_ws import register_proctoring_websocket

    register_proctoring_websocket(app)

    @app.cli.command("seed")
    def seed_command():
        from seeds.run_seeds import run_all_seeds

        run_all_seeds()
        print("Seed data applied successfully.")

    return app
