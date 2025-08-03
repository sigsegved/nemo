"""
Abstract base classes for data and trade providers.

This module defines the interface contracts that all market data providers
and trade execution providers must implement to ensure consistent behavior
across different broker APIs.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, List
from decimal import Decimal
from .models import TradeTick, MetricUpdate, OrderAck, Position


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
    async def subscribe_metrics(self, symbols: List[str]) -> None:
        """Subscribe to metrics (mark-price, funding, liquidations)."""
        pass
    
    @abstractmethod
    async def iter_ticks(self) -> AsyncIterator[TradeTick]:
        """Async iterator yielding trade ticks."""
        pass
    
    @abstractmethod
    async def iter_metrics(self) -> AsyncIterator[MetricUpdate]:
        """Async iterator yielding metric updates."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up and disconnect from data source."""
        pass


class TradeProvider(ABC):
    """Abstract base class for trading providers."""
    
    @abstractmethod
    async def submit_order(
        self, 
        symbol: str, 
        side: str, 
        notional: Decimal, 
        tif: str = "IOC"
    ) -> OrderAck:
        """Submit an order and return acknowledgment."""
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