"""
Data models for the Nemo trading system.

This module contains core data structures for:
- Market data (trades, ticks, metrics)
- Trading positions and order acknowledgments
- Risk metrics and portfolio state
"""

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class TradeTick:
    """
    Represents a single trade tick from market data.
    
    Attributes:
        symbol: Trading symbol (e.g., "BTCUSD")
        price: Trade price in quote currency
        size: Trade size in base currency
        side: Trade side, either "buy" or "sell"
        timestamp: When the trade occurred
        trade_id: Optional unique identifier for the trade
    """
    symbol: str
    price: Decimal
    size: Decimal
    side: str  # "buy" or "sell"
    timestamp: datetime
    trade_id: Optional[str] = None

    def __post_init__(self):
        """Validate trade tick data after initialization."""
        if self.side not in ("buy", "sell"):
            raise ValueError(f"Invalid side '{self.side}'. Must be 'buy' or 'sell'")
        if self.price <= 0:
            raise ValueError(f"Price must be positive, got {self.price}")
        if self.size <= 0:
            raise ValueError(f"Size must be positive, got {self.size}")
        if not self.symbol:
            raise ValueError("Symbol cannot be empty")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "price": str(self.price),
            "size": str(self.size),
            "side": self.side,
            "timestamp": self.timestamp.isoformat(),
            "trade_id": self.trade_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradeTick":
        """Create TradeTick from dictionary."""
        return cls(
            symbol=data["symbol"],
            price=Decimal(data["price"]),
            size=Decimal(data["size"]),
            side=data["side"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            trade_id=data.get("trade_id")
        )


@dataclass
class MetricUpdate:
    """
    Represents a metric update for funding rates, liquidations, or mark prices.
    
    Attributes:
        symbol: Trading symbol the metric applies to
        metric_type: Type of metric ("funding", "liquidation", "mark_price")
        value: The metric value
        timestamp: When the metric was recorded
        additional_data: Optional additional information as key-value pairs
    """
    symbol: str
    metric_type: str  # "funding", "liquidation", "mark_price"
    value: Decimal
    timestamp: datetime
    additional_data: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Validate metric update data after initialization."""
        valid_types = ("funding", "liquidation", "mark_price")
        if self.metric_type not in valid_types:
            raise ValueError(f"Invalid metric_type '{self.metric_type}'. Must be one of {valid_types}")
        if not self.symbol:
            raise ValueError("Symbol cannot be empty")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "metric_type": self.metric_type,
            "value": str(self.value),
            "timestamp": self.timestamp.isoformat(),
            "additional_data": self.additional_data
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricUpdate":
        """Create MetricUpdate from dictionary."""
        return cls(
            symbol=data["symbol"],
            metric_type=data["metric_type"],
            value=Decimal(data["value"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            additional_data=data.get("additional_data")
        )


@dataclass
class Position:
    """
    Represents a trading position.
    
    Attributes:
        symbol: Trading symbol for the position
        side: Position side, either "long" or "short"
        size: Position size in base currency
        entry_price: Average entry price for the position
        mark_price: Current mark price for position valuation
        unrealized_pnl: Unrealized profit and loss
        timestamp: When the position data was recorded
    """
    symbol: str
    side: str  # "long" or "short"
    size: Decimal
    entry_price: Decimal
    mark_price: Decimal
    unrealized_pnl: Decimal
    timestamp: datetime

    def __post_init__(self):
        """Validate position data after initialization."""
        if self.side not in ("long", "short"):
            raise ValueError(f"Invalid side '{self.side}'. Must be 'long' or 'short'")
        if self.size <= 0:
            raise ValueError(f"Size must be positive, got {self.size}")
        if self.entry_price <= 0:
            raise ValueError(f"Entry price must be positive, got {self.entry_price}")
        if self.mark_price <= 0:
            raise ValueError(f"Mark price must be positive, got {self.mark_price}")
        if not self.symbol:
            raise ValueError("Symbol cannot be empty")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "size": str(self.size),
            "entry_price": str(self.entry_price),
            "mark_price": str(self.mark_price),
            "unrealized_pnl": str(self.unrealized_pnl),
            "timestamp": self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Position":
        """Create Position from dictionary."""
        return cls(
            symbol=data["symbol"],
            side=data["side"],
            size=Decimal(data["size"]),
            entry_price=Decimal(data["entry_price"]),
            mark_price=Decimal(data["mark_price"]),
            unrealized_pnl=Decimal(data["unrealized_pnl"]),
            timestamp=datetime.fromisoformat(data["timestamp"])
        )


@dataclass
class OrderAck:
    """
    Represents an order acknowledgment from a trading system.
    
    Attributes:
        order_id: Unique identifier for the order
        symbol: Trading symbol for the order
        side: Order side, either "buy" or "sell"
        size: Total order size
        status: Order status ("filled", "partial", "rejected", "pending")
        timestamp: When the acknowledgment was received
        price: Order price (None for market orders)
        filled_size: Amount of the order that has been filled
        avg_fill_price: Average price of filled portions (None if unfilled)
    """
    order_id: str
    symbol: str
    side: str  # "buy" or "sell"
    size: Decimal
    status: str  # "filled", "partial", "rejected", "pending"
    timestamp: datetime
    price: Optional[Decimal] = None
    filled_size: Decimal = Decimal("0")
    avg_fill_price: Optional[Decimal] = None

    def __post_init__(self):
        """Validate order acknowledgment data after initialization."""
        if self.side not in ("buy", "sell"):
            raise ValueError(f"Invalid side '{self.side}'. Must be 'buy' or 'sell'")
        valid_statuses = ("filled", "partial", "rejected", "pending")
        if self.status not in valid_statuses:
            raise ValueError(f"Invalid status '{self.status}'. Must be one of {valid_statuses}")
        if self.size <= 0:
            raise ValueError(f"Size must be positive, got {self.size}")
        if self.filled_size < 0:
            raise ValueError(f"Filled size cannot be negative, got {self.filled_size}")
        if self.filled_size > self.size:
            raise ValueError(f"Filled size ({self.filled_size}) cannot exceed total size ({self.size})")
        if self.price is not None and self.price <= 0:
            raise ValueError(f"Price must be positive when specified, got {self.price}")
        if self.avg_fill_price is not None and self.avg_fill_price <= 0:
            raise ValueError(f"Average fill price must be positive when specified, got {self.avg_fill_price}")
        if not self.order_id:
            raise ValueError("Order ID cannot be empty")
        if not self.symbol:
            raise ValueError("Symbol cannot be empty")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "size": str(self.size),
            "price": str(self.price) if self.price is not None else None,
            "status": self.status,
            "filled_size": str(self.filled_size),
            "avg_fill_price": str(self.avg_fill_price) if self.avg_fill_price is not None else None,
            "timestamp": self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrderAck":
        """Create OrderAck from dictionary."""
        return cls(
            order_id=data["order_id"],
            symbol=data["symbol"],
            side=data["side"],
            size=Decimal(data["size"]),
            price=Decimal(data["price"]) if data["price"] is not None else None,
            status=data["status"],
            filled_size=Decimal(data["filled_size"]),
            avg_fill_price=Decimal(data["avg_fill_price"]) if data["avg_fill_price"] is not None else None,
            timestamp=datetime.fromisoformat(data["timestamp"])
        )