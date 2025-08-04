"""
Abstract base classes for data and trade providers.

This module defines the interface contracts that all market data providers
and trade execution providers must implement to ensure consistent behavior
across different broker APIs.

The async iterator pattern (iter_ticks, iter_metrics) abstracts both WebSocket
and REST connection patterns:
- WebSocket providers yield data as it arrives from real-time streams
- REST providers implement internal polling and yield data at intervals
- Consumer code remains agnostic to the underlying transport mechanism
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, List
from decimal import Decimal
from .models import TradeTick, MarketEvent, OrderAck, Position


class DataProvider(ABC):
    """Abstract base class for market data providers."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to data source."""
        pass

    @abstractmethod
    async def subscribe_trades(self, symbols: List[str]) -> None:
        """Subscribe to trade data for given symbols."""
        pass

    @abstractmethod
    async def subscribe_events(self, symbols: List[str]) -> None:
        """Subscribe to market events (mark-price, funding, liquidations)."""
        pass

    @abstractmethod
    async def iter_ticks(self) -> AsyncIterator[TradeTick]:
        """Async iterator yielding trade ticks.

        For WebSocket providers: yield data as it arrives from the stream.
        For REST providers: implement internal polling and yield data at intervals.
        """
        pass

    @abstractmethod
    async def iter_events(self) -> AsyncIterator[MarketEvent]:
        """Async iterator yielding market events.

        For WebSocket providers: yield data as it arrives from the stream.
        For REST providers: implement internal polling and yield data at intervals.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up and disconnect from data source."""
        pass


class TradeProvider(ABC):
    """Abstract base class for trading providers."""

    @abstractmethod
    async def submit_order(
        self, symbol: str, side: str, amount: Decimal, tif: str = "IOC"
    ) -> OrderAck:
        """Submit an order and return acknowledgment.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSD', 'AAPL')
            side: Order side ('buy' or 'sell')
            amount: Dollar amount of the trade (price × quantity)
            tif: Time In Force - 'IOC' (Immediate or Cancel),
                'GTC' (Good Till Canceled), 'FOK' (Fill or Kill)

        Returns:
            OrderAck: Order acknowledgment with status and details
        """
        pass

    @abstractmethod
    async def close_position(self, symbol: str) -> OrderAck:
        """Close existing position for symbol."""
        pass

    @abstractmethod
    async def fetch_positions(self) -> List[Position]:
        """Fetch all current positions."""
        pass

    @abstractmethod
    async def get_account_equity(self) -> Decimal:
        """Get current account equity."""
        pass

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to trading API."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up and disconnect from trading API."""
        pass
