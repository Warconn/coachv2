from __future__ import annotations

import logging
from typing import Iterable, List

import requests
from flask import current_app
from tenacity import retry, stop_after_attempt, wait_fixed

from ..client import OddsProvider, OddsProviderRegistry

logger = logging.getLogger(__name__)

BASE_URL = "https://api.the-odds-api.com/v4"


class TheOddsAPI(OddsProvider):
    name = "theoddsapi"

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("The Odds API key is required")
        self.api_key = api_key

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def _get(self, path: str, params: dict) -> requests.Response:
        url = f"{BASE_URL}{path}"
        logger.debug("Requesting %s with params %s", url, params)
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response

    def fetch_moneyline_odds(self, sports: Iterable[str]) -> List[dict]:
        results: List[dict] = []
        for sport in sports:
            data = self._fetch_sport_odds(sport)
            results.extend(
                {
                    "provider": self.name,
                    "sport_key": sport,
                    "event": event,
                }
                for event in data
            )
        return results

    def _fetch_sport_odds(self, sport: str) -> List[dict]:
        bookmakers = current_app.config.get("BOOKMAKERS", [])
        params = {
            "apiKey": self.api_key,
            "regions": "us",
            "markets": "h2h",
            "oddsFormat": "american",
            "dateFormat": "iso",
        }
        if bookmakers:
            params["bookmakers"] = ",".join(bookmakers)

        response = self._get(f"/sports/{sport}/odds", params=params)
        remaining = response.headers.get("x-requests-remaining")
        if remaining is not None:
            logger.debug("The Odds API remaining requests: %s", remaining)
        return response.json()


def _register() -> None:
    api_key = current_app.config.get("ODDS_API_KEY")
    try:
        provider = TheOddsAPI(api_key=api_key)
    except ValueError as exc:
        logger.warning("Skipping The Odds API registration: %s", exc)
        return
    OddsProviderRegistry.register(provider)


_register()
