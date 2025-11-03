"""Add outcome tracking for recommendations and events

Revision ID: 0002_recommendation_outcomes
Revises: 0001_initial_schema
Create Date: 2025-11-02
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_recommendation_outcomes"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recommendations",
        sa.Column("closing_price", sa.Integer(), nullable=True),
    )
    op.add_column(
        "recommendations",
        sa.Column(
            "resolved_result",
            sa.Enum("PENDING", "WON", "LOST", "PUSH", "VOID", name="betresult"),
            nullable=True,
        ),
    )
    op.add_column(
        "recommendations",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column("events", sa.Column("home_score", sa.Integer(), nullable=True))
    op.add_column("events", sa.Column("away_score", sa.Integer(), nullable=True))
    op.add_column("events", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("events", "resolved_at")
    op.drop_column("events", "away_score")
    op.drop_column("events", "home_score")

    op.drop_column("recommendations", "resolved_at")
    op.drop_column("recommendations", "resolved_result")
    op.drop_column("recommendations", "closing_price")
