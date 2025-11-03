from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Protocol

from flask import current_app

logger = logging.getLogger(__name__)


class OddsProvider(Protocol):
    """
    Protocol describing a provider implementation. Concrete providers should be
    thin wrappers around third-party APIs so we can swap implementations easily.
    """

    name: str

    def fetch_moneyline_odds(self, sports: Iterable[str]) -> List[dict]:
        ...


class OddsProviderRegistry:
    """
    Registry with deferred imports so the worker can dynamically load only the
    providers needed at runtime based on configuration.
    """

    _providers: Dict[str, OddsProvider] = {}

    @classmethod
    def register(cls, provider: OddsProvider) -> None:
        logger.debug("Registering odds provider %s", provider.name)
        cls._providers[provider.name] = provider

    @classmethod
    def get(cls, name: str) -> OddsProvider:
        try:
            return cls._providers[name]
        except KeyError as exc:
            raise KeyError(f"Odds provider '{name}' is not registered") from exc

    @classmethod
    def load_configured_providers(cls) -> List[OddsProvider]:
        """
        Instantiate providers listed in config; provider modules register themselves
        via side effects when imported.
        """
        provider_names = current_app.config.get("ODDS_PROVIDERS", [])
        logger.info("Configured odds providers: %s", provider_names)

        # Lazy import to avoid circular dependencies
        from .providers import theoddsapi  # noqa: F401

        providers = []
        for name in provider_names:
            try:
                providers.append(cls.get(name))
            except KeyError:
                logger.warning("No odds provider found for name '%s'", name)
        return providers


class OddsClient:
    """
    Facade that coordinates calls to all configured providers and aggregates
    the results into a single response for the ingestion pipeline.
    """

    def __init__(self, providers: Iterable[OddsProvider]):
        self.providers = list(providers)

    def fetch_moneyline_odds(self, sports: Iterable[str]) -> List[dict]:
        aggregated: List[dict] = []
        for provider in self.providers:
            logger.info("Fetching odds from %s", provider.name)
            try:
                aggregated.extend(provider.fetch_moneyline_odds(sports))
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Provider %s failed: %s", provider.name, exc)
        return aggregated

