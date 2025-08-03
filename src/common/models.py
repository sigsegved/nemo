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
    """Model for trade tick data with properties for volatility calculations."""

    def __init__(
        self,
        symbol: str,
        price: Decimal,
        size: Decimal,
        timestamp: datetime,
        side: str,
        bid_price: Optional[Decimal] = None,
        ask_price: Optional[Decimal] = None,
        high: Optional[Decimal] = None,
        low: Optional[Decimal] = None,
        open_price: Optional[Decimal] = None,
        volume: Optional[Decimal] = None,
        trade_count: Optional[int] = None,
    ):
        self.symbol = symbol
        self.price = price  # Last trade price
        self.size = size  # Trade size
        self.timestamp = timestamp
        self.side = side  # 'buy' or 'sell'

        # Properties for volatility and spread analysis
        self.bid_price = bid_price  # Best bid price at time of trade
        self.ask_price = ask_price  # Best ask price at time of trade
        self.high = high  # Highest price in recent period
        self.low = low  # Lowest price in recent period
        self.open_price = open_price  # Opening price for period
        self.volume = volume  # Total volume in period
        self.trade_count = trade_count  # Number of trades in period

    @property
    def spread(self) -> Optional[Decimal]:
        """Calculate bid-ask spread if both bid and ask prices are available."""
        if self.bid_price is not None and self.ask_price is not None:
            return self.ask_price - self.bid_price
        return None

    @property
    def mid_price(self) -> Optional[Decimal]:
        """Calculate mid price if both bid and ask prices are available."""
        if self.bid_price is not None and self.ask_price is not None:
            return (self.bid_price + self.ask_price) / 2
        return None

    @property
    def price_range(self) -> Optional[Decimal]:
        """Calculate price range (high - low) if both are available."""
        if self.high is not None and self.low is not None:
            return self.high - self.low
        return None


class MetricUpdate:
    """Model for metric updates (mark-price, funding, liquidations)."""

    def __init__(
        self, symbol: str, metric_type: str, value: Decimal, timestamp: datetime
    ):
        self.symbol = symbol
        self.metric_type = metric_type
        self.value = value
        self.timestamp = timestamp


class OrderAck:
    """Model for order acknowledgment."""

    def __init__(
        self,
        order_id: str,
        symbol: str,
        side: str,
        notional: Decimal,
        status: str,
        timestamp: datetime,
        message: Optional[str] = None,
    ):
        self.order_id = order_id
        self.symbol = symbol
        self.side = side
        self.notional = notional
        self.status = status
        self.timestamp = timestamp
        self.message = message


class Position:
    """Model for trading position."""

    def __init__(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        entry_price: Decimal,
        current_price: Decimal,
        unrealized_pnl: Decimal,
        timestamp: datetime,
    ):
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
