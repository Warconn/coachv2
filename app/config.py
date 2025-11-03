from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

# Load environment variables as early as possible for both Flask and worker contexts.
load_dotenv(dotenv_path=ENV_PATH, override=False)


class DefaultConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "development-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'coachv2.db'}"
    )
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # Odds provider configuration
    ODDS_API_KEY = os.getenv("THE_ODDS_API_KEY", "")
    ODDS_PROVIDERS = [
        provider.strip()
        for provider in os.getenv(
            "ODDS_PROVIDERS", "theoddsapi"
        ).split(",")
        if provider.strip()
    ]
    BOOKMAKERS = [
        book.strip()
        for book in os.getenv(
            "BOOKMAKERS", "draftkings,fanduel,betmgm,caesars"
        ).split(",")
        if book.strip()
    ]
    ODDS_SPORTS = [
        sport.strip()
        for sport in os.getenv(
            "ODDS_SPORTS",
            "americanfootball_nfl,basketball_nba,baseball_mlb,icehockey_nhl",
        ).split(",")
        if sport.strip()
    ]

    INGEST_CRON_MORNING = os.getenv("INGEST_CRON_MORNING", "0 9 * * *")
    INGEST_CRON_EVENING = os.getenv("INGEST_CRON_EVENING", "0 19 * * *")
    TIMEZONE = os.getenv("TIMEZONE", "America/New_York")

    MOVEMENT_THRESHOLD_CENTS = int(os.getenv("MOVEMENT_THRESHOLD_CENTS", "20"))
    MOVEMENT_COOLDOWN_MINUTES = int(os.getenv("MOVEMENT_COOLDOWN_MINUTES", "180"))
    MOVEMENT_MEDIUM_MULTIPLIER = float(os.getenv("MOVEMENT_MEDIUM_MULTIPLIER", "2.0"))
    MOVEMENT_HIGH_MULTIPLIER = float(os.getenv("MOVEMENT_HIGH_MULTIPLIER", "3.0"))
