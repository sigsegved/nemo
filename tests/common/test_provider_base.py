"""
Tests for abstract provider base classes.

This module tests the abstract base classes:
- DataProvider interface contracts
- TradeProvider interface contracts
- Abstract method implementations
"""

from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal
from typing import List
from unittest.mock import AsyncMock

import pytest

from src.common.models import MarketEvent, OrderAck, Position, TradeTick
from src.common.provider_base import DataProvider, TradeProvider


class MockDataProvider(DataProvider):
    """Mock implementation of DataProvider for testing."""

    def __init__(self):
        self.connected = False
        self.subscribed_symbols = []
        self.subscribed_events = []

    async def connect(self) -> None:
        """Mock connection."""
        self.connected = True

    async def subscribe_trades(self, symbols: list[str]) -> None:
        """Mock trade subscription."""
        self.subscribed_symbols.extend(symbols)

    async def subscribe_events(self, symbols: list[str]) -> None:
        """Mock event subscription."""
        self.subscribed_events.extend(symbols)

    async def iter_ticks(self) -> AsyncIterator[TradeTick]:
        """Mock tick iterator."""
        # Yield test ticks
        yield TradeTick(
            symbol="BTCUSD",
            price=Decimal("50000.00"),
            size=Decimal("0.1"),
            timestamp=datetime.now(),
            side="buy",
        )
        yield TradeTick(
            symbol="ETHUSD",
            price=Decimal("3000.00"),
            size=Decimal("1.0"),
            timestamp=datetime.now(),
            side="sell",
        )

    async def iter_events(self) -> AsyncIterator[MarketEvent]:
        """Mock event iterator."""
        yield MarketEvent(
            symbol="BTCUSD",
            event_type="mark_price",
            value=Decimal("50000.00"),
            timestamp=datetime.now(),
        )

    async def disconnect(self) -> None:
        """Mock disconnection."""
        self.connected = False


class MockTradeProvider(TradeProvider):
    """Mock implementation of TradeProvider for testing."""

    def __init__(self):
        self.connected = False
        self.positions = []
        self.equity = Decimal("100000.00")

    async def connect(self) -> None:
        """Mock connection."""
        self.connected = True

    async def submit_order(
        self, symbol: str, side: str, amount: Decimal, tif: str = "IOC"
    ) -> OrderAck:
        """Mock order submission."""
        return OrderAck(
            order_id="test_order_123",
            symbol=symbol,
            side=side,
            amount=amount,
            status="filled",
            timestamp=datetime.now(),
            tif=tif,
            message=f"Mock order for {amount} {symbol}",
        )

    async def close_position(self, symbol: str) -> OrderAck:
        """Mock position closing."""
        return OrderAck(
            order_id="close_123",
            symbol=symbol,
            side="close",
            amount=Decimal("0"),
            status="filled",
            timestamp=datetime.now(),
            tif="IOC",
            message=f"Closed position for {symbol}",
        )

    async def fetch_positions(self) -> list[Position]:
        """Mock position fetching."""
        return [
            Position(
                symbol="BTCUSD",
                side="long",
                size=Decimal("0.5"),
                entry_price=Decimal("45000.00"),
                current_price=Decimal("50000.00"),
                unrealized_pnl=Decimal("2500.00"),
                timestamp=datetime.now(),
            )
        ]

    async def get_account_equity(self) -> Decimal:
        """Mock account equity."""
        return self.equity

    async def disconnect(self) -> None:
        """Mock disconnection."""
        self.connected = False


class TestDataProviderInterface:
    """Test cases for DataProvider abstract interface."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that abstract DataProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            DataProvider()

    @pytest.mark.asyncio
    async def test_mock_data_provider_implementation(self):
        """Test mock implementation of DataProvider."""
        provider = MockDataProvider()

        # Test connection
        assert not provider.connected
        await provider.connect()
        assert provider.connected

        # Test subscription
        symbols = ["BTCUSD", "ETHUSD"]
        await provider.subscribe_trades(symbols)
        assert provider.subscribed_symbols == symbols

        await provider.subscribe_events(symbols)
        assert provider.subscribed_events == symbols

        # Test disconnection
        await provider.disconnect()
        assert not provider.connected

    @pytest.mark.asyncio
    async def test_tick_iteration(self):
        """Test async iteration over trade ticks."""
        provider = MockDataProvider()
        await provider.connect()

        ticks = []
        async for tick in provider.iter_ticks():
            ticks.append(tick)
            if len(ticks) >= 2:  # Limit for test
                break

        assert len(ticks) == 2
        assert ticks[0].symbol == "BTCUSD"
        assert ticks[1].symbol == "ETHUSD"
        assert all(isinstance(tick, TradeTick) for tick in ticks)

    @pytest.mark.asyncio
    async def test_event_iteration(self):
        """Test async iteration over market events."""
        provider = MockDataProvider()
        await provider.connect()

        events = []
        async for event in provider.iter_events():
            events.append(event)
            break  # Only get first event for test

        assert len(events) == 1
        assert events[0].symbol == "BTCUSD"
        assert events[0].event_type == "mark_price"
        assert isinstance(events[0], MarketEvent)


class TestTradeProviderInterface:
    """Test cases for TradeProvider abstract interface."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that abstract TradeProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            TradeProvider()

    @pytest.mark.asyncio
    async def test_mock_trade_provider_implementation(self):
        """Test mock implementation of TradeProvider."""
        provider = MockTradeProvider()

        # Test connection
        assert not provider.connected
        await provider.connect()
        assert provider.connected

        # Test disconnection
        await provider.disconnect()
        assert not provider.connected

    @pytest.mark.asyncio
    async def test_order_submission(self):
        """Test order submission functionality."""
        provider = MockTradeProvider()
        await provider.connect()

        # Submit buy order
        order_ack = await provider.submit_order(
            symbol="BTCUSD", side="buy", amount=Decimal("1000.00"), tif="IOC"
        )

        assert isinstance(order_ack, OrderAck)
        assert order_ack.symbol == "BTCUSD"
        assert order_ack.side == "buy"
        assert order_ack.amount == Decimal("1000.00")
        assert order_ack.status == "filled"
        assert order_ack.order_id == "test_order_123"

    @pytest.mark.asyncio
    async def test_order_submission_with_default_tif(self):
        """Test order submission with default TIF parameter."""
        provider = MockTradeProvider()
        await provider.connect()

        # Submit order without specifying TIF (should default to "IOC")
        order_ack = await provider.submit_order(
            symbol="ETHUSD", side="sell", amount=Decimal("500.00")
        )

        assert isinstance(order_ack, OrderAck)
        assert order_ack.symbol == "ETHUSD"
        assert order_ack.side == "sell"

    @pytest.mark.asyncio
    async def test_position_closing(self):
        """Test position closing functionality."""
        provider = MockTradeProvider()
        await provider.connect()

        close_ack = await provider.close_position("BTCUSD")

        assert isinstance(close_ack, OrderAck)
        assert close_ack.symbol == "BTCUSD"
        assert close_ack.side == "close"
        assert close_ack.order_id == "close_123"

    @pytest.mark.asyncio
    async def test_position_fetching(self):
        """Test position fetching functionality."""
        provider = MockTradeProvider()
        await provider.connect()

        positions = await provider.fetch_positions()

        assert isinstance(positions, list)
        assert len(positions) == 1
        assert isinstance(positions[0], Position)
        assert positions[0].symbol == "BTCUSD"
        assert positions[0].side == "long"

    @pytest.mark.asyncio
    async def test_account_equity(self):
        """Test account equity retrieval."""
        provider = MockTradeProvider()
        await provider.connect()

        equity = await provider.get_account_equity()

        assert isinstance(equity, Decimal)
        assert equity == Decimal("100000.00")


class TestProviderInterfaceContracts:
    """Test that provider interfaces enforce proper contracts."""

    def test_data_provider_abstract_methods(self):
        """Test that DataProvider has all required abstract methods."""
        abstract_methods = DataProvider.__abstractmethods__
        expected_methods = {
            "connect",
            "subscribe_trades",
            "subscribe_events",
            "iter_ticks",
            "iter_events",
            "disconnect",
        }

        assert abstract_methods == expected_methods

    def test_trade_provider_abstract_methods(self):
        """Test that TradeProvider has all required abstract methods."""
        abstract_methods = TradeProvider.__abstractmethods__
        expected_methods = {
            "submit_order",
            "close_position",
            "fetch_positions",
            "get_account_equity",
            "connect",
            "disconnect",
        }

        assert abstract_methods == expected_methods

    def test_method_signatures(self):
        """Test that abstract methods have expected signatures."""
        # This is more of a documentation test
        import inspect

        # Check DataProvider method signatures
        connect_sig = inspect.signature(DataProvider.connect)
        assert len(connect_sig.parameters) == 1  # Only 'self'

        subscribe_trades_sig = inspect.signature(DataProvider.subscribe_trades)
        assert len(subscribe_trades_sig.parameters) == 2  # 'self' and 'symbols'

        # Check TradeProvider method signatures
        submit_order_sig = inspect.signature(TradeProvider.submit_order)
        assert len(submit_order_sig.parameters) == 5  # self, symbol, side, amount, tif

        # Check default parameter for tif
        tif_param = submit_order_sig.parameters["tif"]
        assert tif_param.default == "IOC"


class TestAsyncPatterns:
    """Test async/await patterns in provider interfaces."""

    @pytest.mark.asyncio
    async def test_async_context_usage(self):
        """Test providers can be used in async context managers."""

        class AsyncContextProvider(MockDataProvider):
            async def __aenter__(self):
                await self.connect()
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                await self.disconnect()

        # Test using async context manager
        async with AsyncContextProvider() as provider:
            assert provider.connected
            await provider.subscribe_trades(["BTCUSD"])
            assert "BTCUSD" in provider.subscribed_symbols

        # Should be disconnected after context
        assert not provider.connected

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test that provider operations can be run concurrently."""
        import asyncio

        provider = MockTradeProvider()
        await provider.connect()

        # Run multiple operations concurrently
        tasks = [
            provider.submit_order("BTCUSD", "buy", Decimal("1000")),
            provider.fetch_positions(),
            provider.get_account_equity(),
        ]

        results = await asyncio.gather(*tasks)

        assert isinstance(results[0], OrderAck)  # Order ack
        assert isinstance(results[1], list)  # Positions list
        assert isinstance(results[2], Decimal)  # Equity
