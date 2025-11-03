from flask import Blueprint

ui_bp = Blueprint("ui", __name__)

from . import routes  # noqa: E402,F401
