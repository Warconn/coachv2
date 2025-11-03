from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from flask import current_app

from app.models import (
    MovementDirection,
    Recommendation,
    RecommendationStatus,
)
from app.utils.odds import american_to_implied_probability

logger = logging.getLogger(__name__)


@dataclass
class MovementResult:
    bet_side: str
    movement_cents: int
    probability_delta: Decimal
    previous_price: int
    current_price: int
    previous_probability: Decimal
    current_probability: Decimal


def detect_reverse_line_move(snapshot, previous_snapshot) -> Optional[Recommendation]:
    """
    Decide whether the incoming snapshot represents a reverse moneyline move worth flagging.
    Returns a Recommendation instance ready to be persisted if criteria are met.
    """

    if previous_snapshot is None:
        return None

    movement = _evaluate_movement(snapshot, previous_snapshot)
    if movement is None:
        return None

    threshold_cents = current_app.config.get("MOVEMENT_THRESHOLD_CENTS", 15)
    cooldown_minutes = current_app.config.get("MOVEMENT_COOLDOWN_MINUTES", 180)
    medium_multiplier = current_app.config.get("MOVEMENT_MEDIUM_MULTIPLIER", 2.0)
    high_multiplier = current_app.config.get("MOVEMENT_HIGH_MULTIPLIER", 3.0)

    if movement.movement_cents < threshold_cents:
        return None

    if not _passes_cooldown(snapshot, movement.bet_side, cooldown_minutes):
        return None

    confidence = _confidence_bucket(
        movement.movement_cents, threshold_cents, medium_multiplier, high_multiplier
    )

    recommendation = Recommendation(
        event_id=snapshot.event_id,
        sportsbook_id=snapshot.sportsbook_id,
        snapshot_id=snapshot.id,
        triggered_at=snapshot.fetched_at,
        direction=MovementDirection.REVERSE,
        movement_cents=movement.movement_cents,
        edge=movement.probability_delta,
        confidence=confidence,
        bet_side=movement.bet_side,
        stake_units=None,
        status=RecommendationStatus.PENDING,
        details={
            "previous_price": movement.previous_price,
            "current_price": movement.current_price,
            "previous_probability": str(movement.previous_probability),
            "current_probability": str(movement.current_probability),
            "probability_delta": str(movement.probability_delta),
            "threshold_cents": threshold_cents,
        },
    )

    return recommendation


def _evaluate_movement(snapshot, previous_snapshot) -> Optional[MovementResult]:
    previous = _snapshot_prices(previous_snapshot)
    current = _snapshot_prices(snapshot)

    if previous is None or current is None:
        return None

    underdog_side = _identify_underdog(previous)
    current_underdog_side = _identify_underdog(current)

    if underdog_side is None or current_underdog_side is None:
        return None

    # If the underdog flipped sides between snapshots, skip – that usually means market turmoil.
    if underdog_side != current_underdog_side:
        logger.debug(
            "Underdog switched sides for event %s; skipping reverse movement check",
            snapshot.event_id,
        )
        return None

    prev_price = previous[underdog_side]["price"]
    current_price = current[underdog_side]["price"]

    if prev_price is None or current_price is None:
        return None

    movement_cents = prev_price - current_price
    if movement_cents <= 0:
        # Line moved away from the underdog or remained unchanged.
        return None

    prev_prob = previous[underdog_side]["probability"].quantize(Decimal("0.000001"))
    current_prob = current[underdog_side]["probability"].quantize(Decimal("0.000001"))
    prob_delta = (current_prob - prev_prob).quantize(Decimal("0.0001"))

    if prob_delta <= Decimal("0"):
        # Safety check – we expect the underdog probability to increase for a reverse move.
        return None

    return MovementResult(
        bet_side=underdog_side,
        movement_cents=int(movement_cents),
        probability_delta=prob_delta,
        previous_price=prev_price,
        current_price=current_price,
        previous_probability=prev_prob,
        current_probability=current_prob,
    )


def _snapshot_prices(snapshot):
    if snapshot.home_price is None or snapshot.away_price is None:
        return None

    home_prob = american_to_implied_probability(snapshot.home_price)
    away_prob = american_to_implied_probability(snapshot.away_price)

    return {
        "home": {"price": snapshot.home_price, "probability": home_prob},
        "away": {"price": snapshot.away_price, "probability": away_prob},
    }


def _identify_underdog(data) -> Optional[str]:
    home_prob = data["home"]["probability"]
    away_prob = data["away"]["probability"]

    if home_prob is None or away_prob is None:
        return None

    if home_prob == away_prob:
        return None

    return "home" if home_prob < away_prob else "away"


def _passes_cooldown(snapshot, bet_side: str, cooldown_minutes: int) -> bool:
    if cooldown_minutes <= 0:
        return True

    window_start = snapshot.fetched_at - timedelta(minutes=cooldown_minutes)

    existing = (
        Recommendation.query.filter_by(
            event_id=snapshot.event_id,
            sportsbook_id=snapshot.sportsbook_id,
            bet_side=bet_side,
        )
        .filter(Recommendation.triggered_at >= window_start)
        .first()
    )

    return existing is None


def _confidence_bucket(
    movement_cents: int, threshold: int, medium_multiplier: float, high_multiplier: float
) -> str:
    if movement_cents >= threshold * high_multiplier:
        return "high"
    if movement_cents >= threshold * medium_multiplier:
        return "medium"
    return "low"
