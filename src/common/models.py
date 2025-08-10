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


class OHLCV(BaseModel):
    """Model for OHLCV candlestick data."""

    symbol: str
    timestamp: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal
    trade_count: Optional[int] = None

    @computed_field
    @property
    def typical_price(self) -> Decimal:
        """Calculate typical price (H+L+C)/3."""
        return (self.high_price + self.low_price + self.close_price) / 3

    @computed_field
    @property
    def price_range(self) -> Decimal:
        """Calculate price range (H-L)."""
        return self.high_price - self.low_price

    @computed_field
    @property
    def body_size(self) -> Decimal:
        """Calculate candle body size |C-O|."""
        return abs(self.close_price - self.open_price)


class FundingRate(BaseModel):
    """Model for funding rate data."""

    symbol: str
    timestamp: datetime
    rate: Decimal  # Funding rate as decimal (e.g., 0.0001 for 0.01%)
    predicted_rate: Optional[Decimal] = None

    @computed_field
    @property
    def rate_bps(self) -> Decimal:
        """Convert funding rate to basis points."""
        return self.rate * Decimal("10000")


class BacktestTrade(BaseModel):
    """Model for a backtested trade with full execution details."""

    trade_id: str
    symbol: str
    strategy: str
    side: str  # 'long' or 'short'
    entry_time: datetime
    entry_price: Decimal
    exit_time: Optional[datetime] = None
    exit_price: Optional[Decimal] = None
    quantity: Decimal
    entry_reason: str
    exit_reason: Optional[str] = None
    pnl: Optional[Decimal] = None
    pnl_pct: Optional[Decimal] = None
    fees: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")
    funding_cost: Decimal = Decimal("0")
    max_drawdown_pct: Optional[Decimal] = None
    max_runup_pct: Optional[Decimal] = None
    hold_duration_hours: Optional[Decimal] = None

    @computed_field
    @property
    def is_closed(self) -> bool:
        """Check if trade is closed."""
        return self.exit_time is not None and self.exit_price is not None

    @computed_field
    @property
    def notional_value(self) -> Decimal:
        """Calculate notional value of trade."""
        return self.entry_price * self.quantity

    @computed_field
    @property
    def total_cost(self) -> Decimal:
        """Calculate total cost including fees and funding."""
        return self.fees + abs(self.funding_cost)


class BacktestMetrics(BaseModel):
    """Model for comprehensive backtest performance metrics."""

    start_date: datetime
    end_date: datetime
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    total_pnl: Decimal
    total_return_pct: Decimal
    sharpe_ratio: Optional[Decimal] = None
    sortino_ratio: Optional[Decimal] = None
    max_drawdown_pct: Decimal
    max_runup_pct: Decimal
    avg_trade_duration_hours: Decimal
    avg_winning_trade_pct: Decimal
    avg_losing_trade_pct: Decimal
    profit_factor: Decimal
    calmar_ratio: Optional[Decimal] = None
    total_fees: Decimal
    total_funding_cost: Decimal
    total_slippage: Decimal

    @computed_field
    @property
    def gross_pnl(self) -> Decimal:
        """Calculate gross P&L before costs."""
        return (
            self.total_pnl
            + self.total_fees
            + abs(self.total_funding_cost)
            + self.total_slippage
        )

    @computed_field
    @property
    def expectancy(self) -> Decimal:
        """Calculate expectancy per trade."""
        if self.total_trades == 0:
            return Decimal("0")
        return self.total_pnl / self.total_trades


class MarketRegime(BaseModel):
    """Model for market regime classification."""

    timestamp: datetime
    symbol: str
    regime: str  # 'liquidation_noise', 'fundamental', 'macro', 'neutral'
    confidence: Decimal  # 0.0 to 1.0
    indicators: dict  # Supporting indicators and values
    headline_present: bool = False
    volume_anomaly: bool = False
    price_volatility: Decimal = Decimal("0")


# TODO: Implement additional core data models
# - OrderBook model for bid/ask data
# - Signal model for trading signals
# - Portfolio model for position tracking
# - RiskMetrics model for risk calculations
