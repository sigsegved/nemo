"""
Data models for the Nemo trading system.

This module contains data structures for:
- Market data (OHLCV, orderbook, trades)
- Trading signals and decisions
- Risk metrics and portfolio state
- Configuration and parameter schemas
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional


class TradeTick:
    """Model for trade tick data."""
    def __init__(self, symbol: str, price: Decimal, size: Decimal, timestamp: datetime, side: str):
        self.symbol = symbol
        self.price = price
        self.size = size
        self.timestamp = timestamp
        self.side = side


class MetricUpdate:
    """Model for metric updates (mark-price, funding, liquidations)."""
    def __init__(self, symbol: str, metric_type: str, value: Decimal, timestamp: datetime):
        self.symbol = symbol
        self.metric_type = metric_type
        self.value = value
        self.timestamp = timestamp


class OrderAck:
    """Model for order acknowledgment."""
    def __init__(self, order_id: str, symbol: str, side: str, notional: Decimal, 
                 status: str, timestamp: datetime, message: Optional[str] = None):
        self.order_id = order_id
        self.symbol = symbol
        self.side = side
        self.notional = notional
        self.status = status
        self.timestamp = timestamp
        self.message = message


class Position:
    """Model for trading position."""
    def __init__(self, symbol: str, side: str, size: Decimal, entry_price: Decimal,
                 current_price: Decimal, unrealized_pnl: Decimal, timestamp: datetime):
        self.symbol = symbol
        self.side = side
        self.size = size
        self.entry_price = entry_price
        self.current_price = current_price
        self.unrealized_pnl = unrealized_pnl
        self.timestamp = timestamp


# TODO: Implement additional core data models
# - MarketData model for OHLCV data
# - OrderBook model for bid/ask data
# - Signal model for trading signals
# - Portfolio model for position tracking
# - RiskMetrics model for risk calculations