from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .. import db


class BaseModel(db.Model):
    __abstract__ = True

    id = Column(Integer, primary_key=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Sportsbook(BaseModel):
    __tablename__ = "sportsbooks"

    key = Column(String(64), unique=True, nullable=False)
    name = Column(String(128), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    odds_snapshots = relationship("OddsSnapshot", back_populates="sportsbook")
    recommendations = relationship("Recommendation", back_populates="sportsbook")
    bets = relationship("Bet", back_populates="sportsbook")


class Event(BaseModel):
    __tablename__ = "events"

    provider = Column(String(64), nullable=False, index=True)
    provider_event_id = Column(String(128), nullable=False)
    sport_key = Column(String(128), nullable=False, index=True)
    commence_time = Column(DateTime(timezone=True), nullable=True)
    home_team = Column(String(128), nullable=False)
    away_team = Column(String(128), nullable=False)
    league = Column(String(128), nullable=True)
    raw = Column(JSON, nullable=True)

    odds_snapshots = relationship("OddsSnapshot", back_populates="event")
    recommendations = relationship("Recommendation", back_populates="event")
    bets = relationship("Bet", back_populates="event")

    __table_args__ = (UniqueConstraint("provider", "provider_event_id", name="uq_event_provider_id"),)


class OddsSnapshot(BaseModel):
    __tablename__ = "odds_snapshots"

    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    sportsbook_id = Column(Integer, ForeignKey("sportsbooks.id"), nullable=False)
    provider = Column(String(64), nullable=False)
    fetched_at = Column(DateTime(timezone=True), nullable=False, index=True)
    market_key = Column(String(32), nullable=False, default="h2h")
    home_price = Column(Integer, nullable=True)
    away_price = Column(Integer, nullable=True)
    draw_price = Column(Integer, nullable=True)
    home_implied_prob = Column(Numeric(scale=6, precision=10), nullable=True)
    away_implied_prob = Column(Numeric(scale=6, precision=10), nullable=True)
    draw_implied_prob = Column(Numeric(scale=6, precision=10), nullable=True)
    raw = Column(JSON, nullable=True)

    event = relationship("Event", back_populates="odds_snapshots")
    sportsbook = relationship("Sportsbook", back_populates="odds_snapshots")

    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "sportsbook_id",
            "provider",
            "market_key",
            "fetched_at",
            name="uq_snapshot_unique_event",
        ),
    )


class MovementDirection(PyEnum):
    REVERSE = "reverse"
    FAVORITE = "favorite"
    UNCHANGED = "unchanged"


class RecommendationStatus(PyEnum):
    PENDING = "pending"
    WAGERED = "wagered"
    SETTLED = "settled"
    DISMISSED = "dismissed"


class Recommendation(BaseModel):
    __tablename__ = "recommendations"

    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    sportsbook_id = Column(Integer, ForeignKey("sportsbooks.id"), nullable=False)
    snapshot_id = Column(Integer, ForeignKey("odds_snapshots.id"), nullable=True)
    triggered_at = Column(DateTime(timezone=True), nullable=False)
    direction = Column(Enum(MovementDirection), nullable=False)
    movement_cents = Column(Integer, nullable=False)
    edge = Column(Numeric(scale=4, precision=8), nullable=True)
    confidence = Column(String(32), nullable=True)
    bet_side = Column(String(64), nullable=False)
    stake_units = Column(Numeric(scale=4, precision=8), nullable=True)
    status = Column(Enum(RecommendationStatus), default=RecommendationStatus.PENDING, nullable=False)
    notes = Column(String(512), nullable=True)
    details = Column(JSON, nullable=True)

    event = relationship("Event", back_populates="recommendations")
    sportsbook = relationship("Sportsbook", back_populates="recommendations")
    snapshot = relationship("OddsSnapshot")
    bets = relationship("Bet", back_populates="recommendation")


class BetResult(PyEnum):
    PENDING = "pending"
    WON = "won"
    LOST = "lost"
    PUSH = "push"
    VOID = "void"


class Bet(BaseModel):
    __tablename__ = "bets"

    sportsbook_id = Column(Integer, ForeignKey("sportsbooks.id"), nullable=False)
    recommendation_id = Column(Integer, ForeignKey("recommendations.id"), nullable=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    bet_side = Column(String(64), nullable=False)
    placed_at = Column(DateTime(timezone=True), nullable=False)
    stake = Column(Numeric(scale=4, precision=12), nullable=False)
    price = Column(Integer, nullable=False)
    result = Column(Enum(BetResult), default=BetResult.PENDING, nullable=False)
    payout = Column(Numeric(scale=4, precision=12), nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(String(512), nullable=True)

    sportsbook = relationship("Sportsbook", back_populates="bets")
    event = relationship("Event", back_populates="bets")
    recommendation = relationship("Recommendation", back_populates="bets")


class LedgerSource(PyEnum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    BET_RESULT = "bet_result"
    ADJUSTMENT = "adjustment"


class BankrollLedger(BaseModel):
    __tablename__ = "bankroll_ledger"

    occurred_at = Column(DateTime(timezone=True), nullable=False)
    amount = Column(Numeric(scale=4, precision=12), nullable=False)
    balance_after = Column(Numeric(scale=4, precision=12), nullable=True)
    source = Column(Enum(LedgerSource), nullable=False)
    recommendation_id = Column(Integer, ForeignKey("recommendations.id"), nullable=True)
    notes = Column(String(512), nullable=True)

    recommendation = relationship("Recommendation")


class ConfigOverride(BaseModel):
    __tablename__ = "config_overrides"

    scope = Column(String(64), nullable=False)
    key = Column(String(128), nullable=False)
    value = Column(JSON, nullable=False)
    description = Column(String(256), nullable=True)

    __table_args__ = (UniqueConstraint("scope", "key", name="uq_config_scope_key"),)
