from __future__ import annotations

from flask import current_app, render_template

from . import ui_bp


@ui_bp.get("/")
def dashboard():
    """Render the main dashboard shell. Data loads asynchronously via API."""

    return render_template(
        "index.html",
        unit_value=current_app.config.get("UNIT_VALUE", 1),
        display_timezone=current_app.config.get("TIMEZONE", "America/New_York"),
    )
