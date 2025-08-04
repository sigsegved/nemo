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
from pydantic import BaseModel, computed_field


class TradeTick(BaseModel):
    """Model for trade tick data with properties for volatility calculations."""
    
    symbol: str
    price: Decimal  # Last trade price
    size: Decimal  # Trade size
    timestamp: datetime
    side: str  # 'buy' or 'sell'
    
    # Properties for volatility and spread analysis
    bid_price: Optional[Decimal] = None  # Best bid price at time of trade
    ask_price: Optional[Decimal] = None  # Best ask price at time of trade
    high: Optional[Decimal] = None  # Highest price in recent period
    low: Optional[Decimal] = None  # Lowest price in recent period
    open_price: Optional[Decimal] = None  # Opening price for period
    volume: Optional[Decimal] = None  # Total volume in period
    trade_count: Optional[int] = None  # Number of trades in period

    @computed_field
    @property
    def spread(self) -> Optional[Decimal]:
        """Calculate bid-ask spread if both bid and ask prices are available."""
        if self.bid_price is not None and self.ask_price is not None:
            return self.ask_price - self.bid_price
        return None

    @computed_field
    @property
    def mid_price(self) -> Optional[Decimal]:
        """Calculate mid price if both bid and ask prices are available."""
        if self.bid_price is not None and self.ask_price is not None:
            return (self.bid_price + self.ask_price) / 2
        return None

    @computed_field
    @property
    def price_range(self) -> Optional[Decimal]:
        """Calculate price range (high - low) if both are available."""
        if self.high is not None and self.low is not None:
            return self.high - self.low
        return None


class MarketEvent(BaseModel):
    """Model for market events (mark-price, funding, liquidations)."""
    
    symbol: str
    event_type: str
    value: Decimal
    timestamp: datetime


class OrderAck(BaseModel):
    """Model for order acknowledgment."""
    
    order_id: str
    symbol: str
    side: str
    amount: Decimal
    status: str
    timestamp: datetime
    tif: Optional[str] = None  # Time In Force
    message: Optional[str] = None


class Position(BaseModel):
    """Model for trading position."""
    
    symbol: str
    side: str
    size: Decimal
    entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    timestamp: datetime


# TODO: Implement additional core data models
# - MarketData model for OHLCV data
# - OrderBook model for bid/ask data
# - Signal model for trading signals
# - Portfolio model for position tracking
# - RiskMetrics model for risk calculations
