from __future__ import annotations

from flask import current_app, jsonify, request

from app.models import Recommendation
from app.worker.tasks import run_ingest_cycle

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


@api_bp.get("/recommendations")
def recommendations_index():
    """Return the most recent reverse line movement recommendations."""

    try:
        limit = int(request.args.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 200))

    recommendations = (
        Recommendation.query.order_by(Recommendation.triggered_at.desc())
        .limit(limit)
        .all()
    )

    payload = []
    for rec in recommendations:
        event = rec.event
        sportsbook = rec.sportsbook
        team = None
        if event:
            if rec.bet_side == "home":
                team = event.home_team
            elif rec.bet_side == "away":
                team = event.away_team

        payload.append(
            {
                "id": rec.id,
                "triggered_at": rec.triggered_at.isoformat() if rec.triggered_at else None,
                "sportsbook": sportsbook.key if sportsbook else None,
                "sportsbook_name": sportsbook.name if sportsbook else None,
                "event": {
                    "id": event.id if event else None,
                    "sport_key": event.sport_key if event else None,
                    "commence_time": event.commence_time.isoformat()
                    if event and event.commence_time
                    else None,
                    "home_team": event.home_team if event else None,
                    "away_team": event.away_team if event else None,
                    "league": event.league if event else None,
                },
                "bet_side": rec.bet_side,
                "team": team,
                "movement_cents": rec.movement_cents,
                "edge": str(rec.edge) if rec.edge is not None else None,
                "confidence": rec.confidence,
                "status": rec.status.value if rec.status else None,
                "details": rec.details or {},
            }
        )

    return jsonify(payload)


@api_bp.post("/ingest")
def trigger_ingestion():
    """Kick off an on-demand ingestion cycle."""

    app = current_app._get_current_object()
    run_ingest_cycle(app)
    return jsonify({"status": "ingestion_started"})
