from __future__ import annotations

from datetime import datetime, timezone

from decimal import Decimal

import sqlalchemy as sa
from flask import current_app, jsonify, request

from app import db
from app.models import Bet, BetResult, Event, Recommendation, RecommendationStatus
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
    limit = max(1, min(limit, 500))

    scope = request.args.get("scope", "live").lower()

    now = datetime.now(timezone.utc)

    query = Recommendation.query.join(Event)

    if scope == "history":
        query = query.filter(
            sa.or_(
                Recommendation.resolved_at.isnot(None),
                sa.and_(
                    Event.commence_time.isnot(None),
                    Event.commence_time < now,
                ),
            )
        )
        query = query.order_by(Recommendation.triggered_at.desc())
    else:
        query = query.filter(
            sa.and_(
                Recommendation.resolved_at.is_(None),
                sa.or_(Event.commence_time.is_(None), Event.commence_time >= now),
            )
        ).order_by(Recommendation.triggered_at.desc())

    recommendations = query.limit(limit).all()

    payload = []
    unit_value = Decimal(str(current_app.config.get("UNIT_VALUE", 1)))
    unit_value_float = float(unit_value)

    for rec in recommendations:
        try:
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
                        "home_score": event.home_score if event else None,
                        "away_score": event.away_score if event else None,
                        "resolved_at": event.resolved_at.isoformat() if event and event.resolved_at else None,
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
                    "outcome": rec.resolved_result.value if rec.resolved_result else None,
                    "resolved_at": rec.resolved_at.isoformat() if rec.resolved_at else None,
                    "closing_price": rec.closing_price,
                }
            )
        except Exception as exc:  # pylint: disable=broad-except
            # Log the exception with the recommendation id to aid debugging and return a helpful error.
            current_app.logger.exception("Failed to build recommendation payload for id=%s: %s", getattr(rec, 'id', None), exc)
            return (
                jsonify(
                    {
                        "error": "Failed to build recommendations payload",
                        "recommendation_id": getattr(rec, "id", None),
                        "message": str(exc),
                    }
                ),
                500,
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


@api_bp.post("/recommendations/<int:rec_id>/resolve")
def resolve_recommendation(rec_id: int):
    data = request.get_json() or {}

    recommendation = Recommendation.query.get_or_404(rec_id)
    event = recommendation.event

    outcome_raw = data.get("outcome")
    if not outcome_raw:
        return jsonify({"error": "Outcome is required"}), 400

    try:
        outcome = BetResult(outcome_raw.lower())
    except ValueError:
        valid = ", ".join([result.value for result in BetResult])
        return jsonify({"error": f"Outcome must be one of: {valid}"}), 400

    closing_price = data.get("closing_price")
    try:
        closing_price_val = int(closing_price) if closing_price is not None else None
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid closing price"}), 400

    home_score = data.get("home_score")
    away_score = data.get("away_score")

    try:
        home_score_val = int(home_score) if home_score is not None else None
        away_score_val = int(away_score) if away_score is not None else None
    except (TypeError, ValueError):
        return jsonify({"error": "Scores must be integers"}), 400

    resolved_at = datetime.now(timezone.utc)

    recommendation.resolved_result = outcome
    recommendation.resolved_at = resolved_at
    recommendation.closing_price = closing_price_val
    if outcome != BetResult.PENDING:
        recommendation.status = RecommendationStatus.SETTLED

    if event:
        event.home_score = home_score_val
        event.away_score = away_score_val
        event.resolved_at = resolved_at

    for bet in recommendation.bets:
        bet.result = outcome
        if bet.settled_at is None:
            bet.settled_at = resolved_at

    db.session.commit()

    current_app.logger.info(
        "Resolved recommendation %s as %s", rec_id, outcome.value
    )

    return jsonify({"status": "resolved", "outcome": outcome.value})


@api_bp.post("/recommendations/bulk_resolve")
def bulk_resolve_recommendations():
    payload = request.get_json() or {}
    items = payload.get("items", [])
    if not isinstance(items, list) or not items:
        return jsonify({"error": "items must be a non-empty list"}), 400

    now = datetime.now(timezone.utc)
    updated = 0

    for entry in items:
        rec_id = entry.get("id")
        event_id = entry.get("event_id")

        recommendation = Recommendation.query.get(rec_id) if rec_id else None
        event = recommendation.event if recommendation else None

        if not event and event_id:
            event = Event.query.get(event_id)

        if not recommendation and event and event.recommendations:
            recommendation = event.recommendations[0]

        if not recommendation:
            continue

        outcome_raw = entry.get("outcome")
        if not outcome_raw:
            continue

        try:
            outcome = BetResult(outcome_raw.lower())
        except ValueError:
            continue

        closing_price_val = None
        closing_price_raw = entry.get("closing_price")
        if closing_price_raw not in (None, "", []):
            try:
                closing_price_val = int(closing_price_raw)
            except (TypeError, ValueError):
                continue

        def _optional_int(value):
            if value in (None, "", []):
                return None
            return int(value)

        try:
            home_score_val = _optional_int(entry.get("home_score"))
            away_score_val = _optional_int(entry.get("away_score"))
        except (TypeError, ValueError):
            continue

        target_event = event or recommendation.event
        if not target_event:
            continue

        target_recommendations = (
            Recommendation.query.filter_by(event_id=target_event.id).all()
            if target_event.id
            else [recommendation]
        )

        for rec in target_recommendations:
            rec.resolved_result = outcome
            rec.resolved_at = now
            rec.closing_price = closing_price_val
            if outcome != BetResult.PENDING:
                rec.status = RecommendationStatus.SETTLED

            for bet in rec.bets:
                bet.result = outcome
                if bet.settled_at is None:
                    bet.settled_at = now

        target_event.home_score = home_score_val
        target_event.away_score = away_score_val
        target_event.resolved_at = now

        updated += len(target_recommendations)

    if updated:
        db.session.commit()

    return jsonify({"status": "ok", "updated": updated})
