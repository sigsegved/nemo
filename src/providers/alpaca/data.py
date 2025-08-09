"""
Alpaca data provider implementation.

This module implements the market data streaming and historical data
retrieval functionality for the Alpaca trading platform.
"""

from collections.abc import AsyncIterator
from typing import Any

from ...common.models import MarketEvent, TradeTick
from ...common.provider_base import DataProvider


class AlpacaDataProvider(DataProvider):
    """Alpaca data provider implementation (stub)."""

    def __init__(self, config: dict[str, Any]):
        """Initialize Alpaca data provider.

        Args:
            config: Provider-specific configuration
        """
        self.config = config
        self.api_key = config.get("API_KEY", "")
        self.api_secret = config.get("API_SECRET", "")
        self.rest_url = config.get("REST_URL", "https://paper-api.alpaca.markets/v2")
        self.ws_url = config.get("WS_URL", "wss://stream.data.alpaca.markets/v2/iex")

    async def connect(self) -> None:
        """Establish connection to data source."""
        raise NotImplementedError("Alpaca data provider not yet implemented")

    async def subscribe_trades(self, symbols: list[str]) -> None:
        """Subscribe to trade data for given symbols."""
        raise NotImplementedError("Alpaca data provider not yet implemented")

    async def subscribe_events(self, symbols: list[str]) -> None:
        """Subscribe to market events (mark-price, funding, liquidations)."""
        raise NotImplementedError("Alpaca data provider not yet implemented")

    async def iter_ticks(self) -> AsyncIterator[TradeTick]:
        """Async iterator yielding trade ticks."""
        raise NotImplementedError("Alpaca data provider not yet implemented")
        # Make this a generator to satisfy the type checker
        yield  # pragma: no cover

    async def iter_events(self) -> AsyncIterator[MarketEvent]:
        """Async iterator yielding market events."""
        raise NotImplementedError("Alpaca data provider not yet implemented")
        # Make this a generator to satisfy the type checker
        yield  # pragma: no cover

    async def disconnect(self) -> None:
        """Clean up and disconnect from data source."""
        raise NotImplementedError("Alpaca data provider not yet implemented")
