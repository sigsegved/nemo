"""
Tests for data models in the Nemo trading system.

This module tests Pydantic data models for:
- TradeTick with volatility calculations
- MarketEvent for market-related events
- OrderAck for order acknowledgments
- Position for trading positions
"""

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.common.models import MarketEvent, OrderAck, Position, TradeTick


class TestTradeTick:
    """Test cases for TradeTick model."""

    def test_trade_tick_creation(self):
        """Test basic TradeTick creation with required fields."""
        tick = TradeTick(
            symbol="BTCUSD",
            price=Decimal("50000.00"),
            size=Decimal("0.1"),
            timestamp=datetime.now(),
            side="buy",
        )

        assert tick.symbol == "BTCUSD"
        assert tick.price == Decimal("50000.00")
        assert tick.size == Decimal("0.1")
        assert tick.side == "buy"
        assert isinstance(tick.timestamp, datetime)

    def test_trade_tick_with_optional_fields(self):
        """Test TradeTick with all optional fields for volatility analysis."""
        timestamp = datetime.now()
        tick = TradeTick(
            symbol="ETHUSD",
            price=Decimal("3000.00"),
            size=Decimal("1.5"),
            timestamp=timestamp,
            side="sell",
            bid_price=Decimal("2999.50"),
            ask_price=Decimal("3000.50"),
            high=Decimal("3050.00"),
            low=Decimal("2950.00"),
            open_price=Decimal("2980.00"),
            volume=Decimal("1000.0"),
            trade_count=150,
        )

        assert tick.bid_price == Decimal("2999.50")
        assert tick.ask_price == Decimal("3000.50")
        assert tick.high == Decimal("3050.00")
        assert tick.low == Decimal("2950.00")
        assert tick.open_price == Decimal("2980.00")
        assert tick.volume == Decimal("1000.0")
        assert tick.trade_count == 150

    def test_spread_calculation(self):
        """Test spread computed property."""
        tick = TradeTick(
            symbol="AAPL",
            price=Decimal("150.00"),
            size=Decimal("100"),
            timestamp=datetime.now(),
            side="buy",
            bid_price=Decimal("149.95"),
            ask_price=Decimal("150.05"),
        )

        assert tick.spread == Decimal("0.10")

    def test_spread_calculation_missing_data(self):
        """Test spread calculation with missing bid/ask data."""
        tick = TradeTick(
            symbol="AAPL",
            price=Decimal("150.00"),
            size=Decimal("100"),
            timestamp=datetime.now(),
            side="buy",
        )

        assert tick.spread is None

    def test_mid_price_calculation(self):
        """Test mid_price computed property."""
        tick = TradeTick(
            symbol="GOOGL",
            price=Decimal("2800.00"),
            size=Decimal("10"),
            timestamp=datetime.now(),
            side="buy",
            bid_price=Decimal("2799.00"),
            ask_price=Decimal("2801.00"),
        )

        assert tick.mid_price == Decimal("2800.00")

    def test_mid_price_calculation_missing_data(self):
        """Test mid_price calculation with missing data."""
        tick = TradeTick(
            symbol="GOOGL",
            price=Decimal("2800.00"),
            size=Decimal("10"),
            timestamp=datetime.now(),
            side="buy",
            bid_price=Decimal("2799.00"),
        )

        assert tick.mid_price is None

    def test_price_range_calculation(self):
        """Test price_range computed property."""
        tick = TradeTick(
            symbol="TSLA",
            price=Decimal("800.00"),
            size=Decimal("50"),
            timestamp=datetime.now(),
            side="sell",
            high=Decimal("820.00"),
            low=Decimal("780.00"),
        )

        assert tick.price_range == Decimal("40.00")

    def test_price_range_calculation_missing_data(self):
        """Test price_range calculation with missing data."""
        tick = TradeTick(
            symbol="TSLA",
            price=Decimal("800.00"),
            size=Decimal("50"),
            timestamp=datetime.now(),
            side="sell",
            high=Decimal("820.00"),
        )

        assert tick.price_range is None

    def test_invalid_side(self):
        """Test validation with invalid side parameter."""
        # Note: This test assumes we might want to validate side values in the future
        # For now, Pydantic will accept any string for side
        tick = TradeTick(
            symbol="BTCUSD",
            price=Decimal("50000.00"),
            size=Decimal("0.1"),
            timestamp=datetime.now(),
            side="invalid_side",
        )

        assert tick.side == "invalid_side"  # Currently allows any string

    def test_json_serialization(self):
        """Test JSON serialization of TradeTick."""
        timestamp = datetime(2023, 1, 1, 12, 0, 0)
        tick = TradeTick(
            symbol="BTCUSD",
            price=Decimal("50000.00"),
            size=Decimal("0.1"),
            timestamp=timestamp,
            side="buy",
            bid_price=Decimal("49999.50"),
            ask_price=Decimal("50000.50"),
        )

        json_data = tick.model_dump()

        assert json_data["symbol"] == "BTCUSD"
        assert json_data["price"] == Decimal("50000.00")
        assert json_data["side"] == "buy"
        assert json_data["spread"] == Decimal("1.00")


class TestMarketEvent:
    """Test cases for MarketEvent model."""

    def test_market_event_creation(self):
        """Test basic MarketEvent creation."""
        event = MarketEvent(
            symbol="BTCUSD",
            event_type="mark_price",
            value=Decimal("50000.00"),
            timestamp=datetime.now(),
        )

        assert event.symbol == "BTCUSD"
        assert event.event_type == "mark_price"
        assert event.value == Decimal("50000.00")
        assert isinstance(event.timestamp, datetime)

    def test_funding_rate_event(self):
        """Test MarketEvent for funding rate."""
        timestamp = datetime.now()
        event = MarketEvent(
            symbol="ETHUSD-PERP",
            event_type="funding_rate",
            value=Decimal("0.0001"),
            timestamp=timestamp,
        )

        assert event.event_type == "funding_rate"
        assert event.value == Decimal("0.0001")

    def test_liquidation_event(self):
        """Test MarketEvent for liquidation."""
        event = MarketEvent(
            symbol="BTCUSD",
            event_type="liquidation",
            value=Decimal("1000000.00"),
            timestamp=datetime.now(),
        )

        assert event.event_type == "liquidation"
        assert event.value == Decimal("1000000.00")


class TestOrderAck:
    """Test cases for OrderAck model."""

    def test_order_ack_creation(self):
        """Test basic OrderAck creation."""
        ack = OrderAck(
            order_id="12345",
            symbol="AAPL",
            side="buy",
            amount=Decimal("1000.00"),
            status="filled",
            timestamp=datetime.now(),
            tif="IOC",
        )

        assert ack.order_id == "12345"
        assert ack.symbol == "AAPL"
        assert ack.side == "buy"
        assert ack.amount == Decimal("1000.00")
        assert ack.status == "filled"

    def test_order_ack_with_message(self):
        """Test OrderAck with optional message."""
        ack = OrderAck(
            order_id="67890",
            symbol="GOOGL",
            side="sell",
            amount=Decimal("5000.00"),
            status="partial",
            timestamp=datetime.now(),
            tif="GTC",
            message="Partially filled: 50 shares",
        )

        assert ack.message == "Partially filled: 50 shares"

    def test_order_ack_without_message(self):
        """Test OrderAck without optional message."""
        ack = OrderAck(
            order_id="67890",
            symbol="GOOGL",
            side="sell",
            amount=Decimal("5000.00"),
            status="filled",
            timestamp=datetime.now(),
            tif="IOC",
        )

        assert ack.message is None


class TestPosition:
    """Test cases for Position model."""

    def test_position_creation(self):
        """Test basic Position creation."""
        position = Position(
            symbol="BTCUSD",
            side="long",
            size=Decimal("0.5"),
            entry_price=Decimal("45000.00"),
            current_price=Decimal("50000.00"),
            unrealized_pnl=Decimal("2500.00"),
            timestamp=datetime.now(),
        )

        assert position.symbol == "BTCUSD"
        assert position.side == "long"
        assert position.size == Decimal("0.5")
        assert position.entry_price == Decimal("45000.00")
        assert position.current_price == Decimal("50000.00")
        assert position.unrealized_pnl == Decimal("2500.00")

    def test_short_position(self):
        """Test short position creation."""
        position = Position(
            symbol="ETHUSD",
            side="short",
            size=Decimal("2.0"),
            entry_price=Decimal("3200.00"),
            current_price=Decimal("3000.00"),
            unrealized_pnl=Decimal("400.00"),
            timestamp=datetime.now(),
        )

        assert position.side == "short"
        assert position.unrealized_pnl == Decimal("400.00")


class TestModelValidation:
    """Test Pydantic validation features."""

    def test_required_field_validation(self):
        """Test that required fields are validated."""
        with pytest.raises(ValidationError):
            TradeTick(
                symbol="BTCUSD",
                price=Decimal("50000.00"),
                # Missing required fields: size, timestamp, side
            )

    def test_decimal_validation(self):
        """Test that Decimal fields are properly validated."""
        # This should work
        tick = TradeTick(
            symbol="BTCUSD",
            price="50000.00",  # String should be converted to Decimal
            size="0.1",
            timestamp=datetime.now(),
            side="buy",
        )

        assert isinstance(tick.price, Decimal)
        assert isinstance(tick.size, Decimal)

    def test_datetime_validation(self):
        """Test datetime field validation."""
        tick = TradeTick(
            symbol="BTCUSD",
            price=Decimal("50000.00"),
            size=Decimal("0.1"),
            timestamp=datetime.now(),
            side="buy",
        )

        assert isinstance(tick.timestamp, datetime)
