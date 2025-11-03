"""Initial schema with core tables for odds tracking and bankroll management.

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2024-02-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sportsbooks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_sportsbooks_key"),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_event_id", sa.String(length=128), nullable=False),
        sa.Column("sport_key", sa.String(length=128), nullable=False),
        sa.Column("commence_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("home_team", sa.String(length=128), nullable=False),
        sa.Column("away_team", sa.String(length=128), nullable=False),
        sa.Column("league", sa.String(length=128), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "provider_event_id", name="uq_event_provider_id"
        ),
    )
    op.create_index(
        op.f("ix_events_provider"),
        "events",
        ["provider"],
    )
    op.create_index(
        op.f("ix_events_sport_key"),
        "events",
        ["sport_key"],
    )

    op.create_table(
        "config_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("description", sa.String(length=256), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "key", name="uq_config_scope_key"),
    )

    op.create_table(
        "bankroll_ledger",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("balance_after", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("source", sa.Enum("DEPOSIT", "WITHDRAWAL", "BET_RESULT", "ADJUSTMENT", name="ledgersource"), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "odds_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("sportsbook_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("market_key", sa.String(length=32), nullable=False),
        sa.Column("home_price", sa.Integer(), nullable=True),
        sa.Column("away_price", sa.Integer(), nullable=True),
        sa.Column("draw_price", sa.Integer(), nullable=True),
        sa.Column("home_implied_prob", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("away_implied_prob", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("draw_implied_prob", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name="fk_odds_snapshots_event_id_events",
        ),
        sa.ForeignKeyConstraint(
            ["sportsbook_id"],
            ["sportsbooks.id"],
            name="fk_odds_snapshots_sportsbook_id_sportsbooks",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id",
            "sportsbook_id",
            "provider",
            "market_key",
            "fetched_at",
            name="uq_snapshot_unique_event",
        ),
    )
    op.create_index(
        op.f("ix_odds_snapshots_event_id"),
        "odds_snapshots",
        ["event_id"],
    )
    op.create_index(
        op.f("ix_odds_snapshots_fetched_at"),
        "odds_snapshots",
        ["fetched_at"],
    )

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("sportsbook_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("direction", sa.Enum("REVERSE", "FAVORITE", "UNCHANGED", name="movementdirection"), nullable=False),
        sa.Column("movement_cents", sa.Integer(), nullable=False),
        sa.Column("edge", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("confidence", sa.String(length=32), nullable=True),
        sa.Column("bet_side", sa.String(length=64), nullable=False),
        sa.Column("stake_units", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("status", sa.Enum("PENDING", "WAGERED", "SETTLED", "DISMISSED", name="recommendationstatus"), nullable=False, server_default="PENDING"),
        sa.Column("notes", sa.String(length=512), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name="fk_recommendations_event_id_events",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["odds_snapshots.id"],
            name="fk_recommendations_snapshot_id_odds_snapshots",
        ),
        sa.ForeignKeyConstraint(
            ["sportsbook_id"],
            ["sportsbooks.id"],
            name="fk_recommendations_sportsbook_id_sportsbooks",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "bets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sportsbook_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=True),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("bet_side", sa.String(length=64), nullable=False),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stake", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("result", sa.Enum("PENDING", "WON", "LOST", "PUSH", "VOID", name="betresult"), nullable=False, server_default="PENDING"),
        sa.Column("payout", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name="fk_bets_event_id_events",
        ),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["recommendations.id"],
            name="fk_bets_recommendation_id_recommendations",
        ),
        sa.ForeignKeyConstraint(
            ["sportsbook_id"],
            ["sportsbooks.id"],
            name="fk_bets_sportsbook_id_sportsbooks",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("bets")
    op.drop_table("recommendations")
    op.drop_table("odds_snapshots")
    op.drop_table("bankroll_ledger")
    op.drop_table("config_overrides")
    op.drop_index(op.f("ix_events_sport_key"), table_name="events")
    op.drop_index(op.f("ix_events_provider"), table_name="events")
    op.drop_table("events")
    op.drop_table("sportsbooks")
    sa.Enum(
        "PENDING", "WON", "LOST", "PUSH", "VOID", name="betresult"
    ).drop(op.get_bind())
    sa.Enum(
        "REVERSE", "FAVORITE", "UNCHANGED", name="movementdirection"
    ).drop(op.get_bind())
    sa.Enum(
        "PENDING", "WAGERED", "SETTLED", "DISMISSED", name="recommendationstatus"
    ).drop(op.get_bind())
    sa.Enum(
        "DEPOSIT", "WITHDRAWAL", "BET_RESULT", "ADJUSTMENT", name="ledgersource"
    ).drop(op.get_bind())
