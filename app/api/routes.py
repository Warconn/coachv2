from __future__ import annotations

from flask import current_app, jsonify

from . import api_bp


@api_bp.get("/")
def index():
    """
    Simple heartbeat endpoint. Will expand into dashboard view via templates later.
    """
    return jsonify(
        {
            "service": "coachv2",
            "status": "ok",
            "log_level": current_app.config.get("LOG_LEVEL"),
        }
    )
