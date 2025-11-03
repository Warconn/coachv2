from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from dateutil import parser as date_parser
from flask import current_app
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Event, OddsSnapshot, Sportsbook
from app.services.odds import OddsClient, OddsProviderRegistry
from app.utils.odds import american_to_implied_probability

logger = logging.getLogger(__name__)


def run_ingest_cycle(app) -> None:
    """
    Entry point for scheduled jobs. Sets up the application context and delegates
    to ingestion/persistence logic.
    """
    with app.app_context():
        logger.info("Starting odds ingestion cycle")

        sports = current_app.config.get("ODDS_SPORTS", [])
        if not sports:
            logger.warning("No sports configured for odds ingestion")
            return

        providers = OddsProviderRegistry.load_configured_providers()
        if not providers:
            logger.error("No odds providers could be loaded; skipping run")
            return

        client = OddsClient(providers)
        data = client.fetch_moneyline_odds(sports)

        persist_snapshot_batch(data)


def persist_snapshot_batch(data: List[dict]) -> None:
    """
    Normalize and store odds snapshots for each bookmaker so we can evaluate line movement.
    """
    if not data:
        logger.info("No odds data returned; nothing to persist")
        return

    bookmakers = current_app.config.get("BOOKMAKERS", [])

    _ensure_sportsbooks(bookmakers)
    sportsbook_lookup = _sportsbook_lookup(bookmakers)

    inserted = 0
    skipped = 0

    for event_payload in data:
        provider_name = event_payload.get("provider", "unknown")
        event_data = event_payload.get("event", {})
        sport_key = event_payload.get("sport_key")

        event = _upsert_event(provider_name, sport_key, event_data)

        bookmaker_entries = event_data.get("bookmakers", [])
        if not bookmaker_entries:
            continue

        for bookmaker in bookmaker_entries:
            book_key = bookmaker.get("key")
            if bookmakers and book_key not in bookmakers:
                continue

            sportsbook = sportsbook_lookup.get(book_key)
            if not sportsbook:
                continue

            fetched_at = _parse_datetime(bookmaker.get("last_update"))
            market = _extract_market(bookmaker.get("markets", []), key="h2h")
            if not market:
                continue

            outcomes = _map_outcomes(market.get("outcomes", []))
            home_price = outcomes.get(event.home_team)
            away_price = outcomes.get(event.away_team)
            draw_price = outcomes.get("Draw") or outcomes.get("draw")

            if _snapshot_exists(event.id, sportsbook.id, provider_name, fetched_at):
                skipped += 1
                continue

            snapshot = OddsSnapshot(
                event_id=event.id,
                sportsbook_id=sportsbook.id,
                provider=provider_name,
                fetched_at=fetched_at or datetime.now(timezone.utc),
                market_key=market.get("key", "h2h"),
                home_price=home_price,
                away_price=away_price,
                draw_price=draw_price,
                home_implied_prob=_to_decimal(home_price),
                away_implied_prob=_to_decimal(away_price),
                draw_implied_prob=_to_decimal(draw_price),
                raw={
                    "bookmaker": {
                        "key": bookmaker.get("key"),
                        "title": bookmaker.get("title"),
                    },
                    "market": market,
                },
            )

            db.session.add(snapshot)
            inserted += 1

    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        logger.exception("Failed to persist odds snapshots: %s", exc)
        raise

    logger.info("Persisted %s snapshots (skipped %s duplicates)", inserted, skipped)


def _ensure_sportsbooks(bookmakers: Iterable[str]) -> None:
    if not bookmakers:
        return

    existing = {
        sb.key: sb
        for sb in Sportsbook.query.filter(Sportsbook.key.in_(list(bookmakers))).all()
    }

    for key in bookmakers:
        if key in existing:
            continue
        sportsbook = Sportsbook(key=key, name=key.title())
        db.session.add(sportsbook)

    db.session.commit()


def _sportsbook_lookup(bookmakers: Iterable[str]) -> Dict[str, Sportsbook]:
    if bookmakers:
        records = Sportsbook.query.filter(Sportsbook.key.in_(list(bookmakers))).all()
    else:
        records = Sportsbook.query.all()
    return {record.key: record for record in records}


def _upsert_event(provider: str, sport_key: str, payload: dict) -> Event:
    event = Event.query.filter_by(
        provider=provider, provider_event_id=payload.get("id")
    ).first()

    commence_time = _parse_datetime(payload.get("commence_time"))

    if event:
        event.sport_key = sport_key
        event.commence_time = commence_time
        event.home_team = payload.get("home_team")
        event.away_team = payload.get("away_team")
        event.league = payload.get("sport_title")
        event.raw = payload
    else:
        event = Event(
            provider=provider,
            provider_event_id=payload.get("id"),
            sport_key=sport_key,
            commence_time=commence_time,
            home_team=payload.get("home_team"),
            away_team=payload.get("away_team"),
            league=payload.get("sport_title"),
            raw=payload,
        )
        db.session.add(event)
        db.session.flush()  # ensure ID for relationships

    return event


def _snapshot_exists(
    event_id: int, sportsbook_id: int, provider: str, fetched_at: Optional[datetime]
) -> bool:
    if not fetched_at:
        return False
    return (
        OddsSnapshot.query.filter_by(
            event_id=event_id,
            sportsbook_id=sportsbook_id,
            provider=provider,
            fetched_at=fetched_at,
        ).first()
        is not None
    )


def _extract_market(markets: List[dict], key: str) -> Optional[dict]:
    for market in markets or []:
        if market.get("key") == key:
            return market
    return None


def _map_outcomes(outcomes: List[dict]) -> Dict[str, int]:
    mapped: Dict[str, int] = {}
    for outcome in outcomes or []:
        name = outcome.get("name")
        price = outcome.get("price")
        if name is not None and price is not None:
            mapped[name] = price
    return mapped


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = date_parser.isoparse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        logger.debug("Failed to parse datetime value '%s'", value)
        return None


def _to_decimal(price: Optional[int]):
    if price is None:
        return None
    return american_to_implied_probability(price)
