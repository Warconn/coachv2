from __future__ import annotations

import logging
from typing import Any, Optional, Type

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import DefaultConfig

# Global extension instances shared between services
db = SQLAlchemy()
migrate = Migrate()


def create_app(config_object: Optional[Type[Any]] = None) -> Flask:
    """
    Application factory so both the API service and worker can share configuration.
    """
    app = Flask(__name__, template_folder="templates", static_folder="static")

    app.config.from_object(DefaultConfig())
    if config_object:
        app.config.from_object(config_object())

    configure_logging(app)

    db.init_app(app)
    migrate.init_app(app, db)

    # Register HTTP routes via blueprints
    from .api.routes import api_bp

    app.register_blueprint(api_bp)

    # Ensure URL generation works behind proxies/load balancers when deployed remotely.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    register_cli_commands(app)

    return app


def configure_logging(app: Flask) -> None:
    """
    Basic structured logging setup for both development and production.
    """
    log_level = app.config.get("LOG_LEVEL", "INFO").upper()
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setLevel(log_level)

    app.logger.setLevel(log_level)
    app.logger.handlers = []
    app.logger.addHandler(handler)


def register_cli_commands(app: Flask) -> None:
    """
    Attach CLI helpers for ad-hoc tasks (e.g., manual ingestion runs).
    """
    from .worker.tasks import run_ingest_cycle

    @app.cli.command("ingest-now")
    def ingest_now():
        """Run the odds ingestion pipeline immediately."""
        run_ingest_cycle(app)
