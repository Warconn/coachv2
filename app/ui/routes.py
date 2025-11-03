from __future__ import annotations

from flask import render_template

from . import ui_bp


@ui_bp.get("/")
def dashboard():
    """Render the main dashboard shell. Data loads asynchronously via API."""

    return render_template("index.html")
