from __future__ import annotations

from datetime import datetime, timezone

from decimal import Decimal
from flask import current_app, jsonify, request

from app import db
from app.models import Bet, BetResult, Event, Recommendation
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

    now = datetime.now(timezone.utc)

    recommendations = (
        Recommendation.query.join(Event)
        .filter(
            (Event.commence_time.is_(None)) | (Event.commence_time >= now)
        )
        .order_by(Recommendation.triggered_at.desc())
        .limit(limit)
        .all()
    )

    payload = []
    unit_value = Decimal(str(current_app.config.get("UNIT_VALUE", 1)))
    unit_value_float = float(unit_value)

    for rec in recommendations:
        event = rec.event
        sportsbook = rec.sportsbook
        team = None
        if event:
            if rec.bet_side == "home":
                team = event.home_team
            elif rec.bet_side == "away":
                team = event.away_team

        bets_payload = [
            {
                "id": bet.id,
                "stake_units": float(bet.stake) if bet.stake is not None else None,
                "stake_amount": float(bet.stake * unit_value) if bet.stake is not None else None,
                "price": bet.price,
                "result": bet.result.value if bet.result else None,
                "placed_at": bet.placed_at.isoformat() if bet.placed_at else None,
                "notes": bet.notes,
            }
            for bet in rec.bets
        ]

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
                "movement": rec.direction.value,
                "confidence": rec.confidence,
                "status": rec.status.value if rec.status else None,
                "details": rec.details or {},
                "bet_logged": bool(bets_payload),
                "bet_count": len(bets_payload),
                "bets": bets_payload,
                "unit_value": unit_value_float,
            }
        )

    return jsonify(payload)


@api_bp.post("/ingest")
def trigger_ingestion():
    """Kick off an on-demand ingestion cycle."""

    app = current_app._get_current_object()
    run_ingest_cycle(app)
    return jsonify({"status": "ingestion_started"})


@api_bp.post("/recommendations/<int:rec_id>/bets")
def log_bet(rec_id: int):
    data = request.get_json() or {}

    recommendation = Recommendation.query.get_or_404(rec_id)

    try:
        stake = Decimal(str(data.get("stake", 1)))
    except Exception as exc:  # pylint: disable=broad-except
        return jsonify({"error": f"Invalid stake: {exc}"}), 400

    if stake <= 0:
        return jsonify({"error": "Stake must be positive"}), 400

    details = recommendation.details or {}

    try:
        price = int(data.get("price") or details.get("current_price"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid price"}), 400

    notes = data.get("notes")

    unit_value = Decimal(str(current_app.config.get("UNIT_VALUE", 1)))

    bet = Bet(
        sportsbook_id=recommendation.sportsbook_id,
        recommendation_id=recommendation.id,
        event_id=recommendation.event_id,
        bet_side=recommendation.bet_side,
        placed_at=datetime.now(timezone.utc),
        stake=stake,
        price=price,
        result=BetResult.PENDING,
        notes=notes,
    )

    current_app.logger.info(
        "Logging bet for recommendation %s with stake %s @ %s", rec_id, stake, price
    )

    db.session.add(bet)
    db.session.commit()

    return jsonify(
        {
            "status": "bet_logged",
            "bet_id": bet.id,
            "stake_units": float(stake),
            "stake_amount": float(stake * unit_value),
            "unit_value": float(unit_value),
        }
    )
