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
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import relationship

from .. import db


class EnumFlexible(TypeDecorator):
    """A SQLAlchemy TypeDecorator that stores enum values as strings but
    accepts either enum.value or enum.name from the database when loading.

    This handles mixed databases where some rows were written using enum
    names and others using enum values.
    """

    impl = String

    def __init__(self, enum_class, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enum_class = enum_class

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        # If an enum member is passed, store its value; otherwise store the raw
        # string (assume it's already a correct value)
        if isinstance(value, self.enum_class):
            return value.value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        # If already an enum member, return
        try:
            # e.g., if SQLAlchemy already converted, just return
            if isinstance(value, self.enum_class):
                return value
        except Exception:
            pass

        # Try matching by value first
        for member in self.enum_class:
            if member.value == value:
                return member

        # Next, try matching by name (case-insensitive)
        try:
            return self.enum_class[value]
        except Exception:
            pass
        try:
            return self.enum_class[value.upper()]
        except Exception:
            pass

        # As a last resort, return the raw string
        return value



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
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

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


class BetResult(PyEnum):
    PENDING = "pending"
    WON = "won"
    LOST = "lost"
    PUSH = "push"
    VOID = "void"


class Recommendation(BaseModel):
    __tablename__ = "recommendations"

    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    sportsbook_id = Column(Integer, ForeignKey("sportsbooks.id"), nullable=False)
    snapshot_id = Column(Integer, ForeignKey("odds_snapshots.id"), nullable=True)
    triggered_at = Column(DateTime(timezone=True), nullable=False)
    direction = Column(
        EnumFlexible(MovementDirection),
        nullable=False,
    )
    movement_cents = Column(Integer, nullable=False)
    edge = Column(Numeric(scale=4, precision=8), nullable=True)
    confidence = Column(String(32), nullable=True)
    bet_side = Column(String(64), nullable=False)
    stake_units = Column(Numeric(scale=4, precision=8), nullable=True)
    status = Column(
        EnumFlexible(RecommendationStatus),
        default=RecommendationStatus.PENDING,
        nullable=False,
    )
    notes = Column(String(512), nullable=True)
    details = Column(JSON, nullable=True)
    closing_price = Column(Integer, nullable=True)
    resolved_result = Column(
        EnumFlexible(BetResult),
        nullable=True,
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    event = relationship("Event", back_populates="recommendations")
    sportsbook = relationship("Sportsbook", back_populates="recommendations")
    snapshot = relationship("OddsSnapshot")
    bets = relationship("Bet", back_populates="recommendation")

class Bet(BaseModel):
    __tablename__ = "bets"

    sportsbook_id = Column(Integer, ForeignKey("sportsbooks.id"), nullable=False)
    recommendation_id = Column(Integer, ForeignKey("recommendations.id"), nullable=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    bet_side = Column(String(64), nullable=False)
    placed_at = Column(DateTime(timezone=True), nullable=False)
    stake = Column(Numeric(scale=4, precision=12), nullable=False)
    price = Column(Integer, nullable=False)
    result = Column(
        EnumFlexible(BetResult),
        default=BetResult.PENDING,
        nullable=False,
    )
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
    source = Column(
        EnumFlexible(LedgerSource),
        nullable=False,
    )
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
