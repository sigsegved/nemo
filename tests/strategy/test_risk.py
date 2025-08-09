"""
Tests for risk management and trading strategy logic.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.strategy.risk import (
    CircuitBreaker,
    MeanReversionStrategy,
    MomentumStrategy,
    Position,
    PositionSide,
    PositionSizer,
    RiskManager,
    StrategyType,
    TradeSignal,
)
from src.strategy.trigger import TriggerSignal, TriggerType


class TestPositionSizer:
    """Test position sizing logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sizer = PositionSizer(
            max_equity_per_position=Decimal("0.25"),
            max_leverage=Decimal("3.0"),
            base_equity=Decimal("100000"),
        )

    def test_position_sizer_initialization(self):
        """Test position sizer initializes correctly."""
        assert self.sizer.max_equity_per_position == Decimal("0.25")
        assert self.sizer.max_leverage == Decimal("3.0")
        assert self.sizer.base_equity == Decimal("100000")

    def test_mean_reversion_position_sizing(self):
        """Test position sizing for mean reversion strategy."""
        quantity = self.sizer.calculate_position_size(
            "BTCUSD",
            Decimal("50000"),
            StrategyType.MEAN_REVERSION,
            Decimal("1.0"),
        )

        # 25% * $100k * 3x leverage = $75k
        # $75k / $50k per BTC = 1.5 BTC
        expected = Decimal("1.5")
        assert quantity == expected

    def test_momentum_position_sizing(self):
        """Test position sizing for momentum strategy."""
        quantity = self.sizer.calculate_position_size(
            "BTCUSD",
            Decimal("50000"),
            StrategyType.MOMENTUM,
            Decimal("1.0"),
        )

        # 25% * $100k * 2x leverage = $50k
        # $50k / $50k per BTC = 1.0 BTC
        expected = Decimal("1.0")
        assert quantity == expected

    def test_signal_strength_adjustment(self):
        """Test position sizing adjusts for signal strength."""
        full_strength = self.sizer.calculate_position_size(
            "BTCUSD", Decimal("50000"), StrategyType.MEAN_REVERSION, Decimal("1.0")
        )
        half_strength = self.sizer.calculate_position_size(
            "BTCUSD", Decimal("50000"), StrategyType.MEAN_REVERSION, Decimal("0.5")
        )

        assert half_strength == full_strength * Decimal("0.5")

    def test_stop_loss_calculation_long(self):
        """Test stop loss calculation for long position."""
        entry_price = Decimal("50000")
        stop_loss = self.sizer.calculate_stop_loss_price(
            entry_price, PositionSide.LONG, Decimal("0.01")
        )

        expected = Decimal("49500")  # 50000 * 0.99
        assert stop_loss == expected

    def test_stop_loss_calculation_short(self):
        """Test stop loss calculation for short position."""
        entry_price = Decimal("50000")
        stop_loss = self.sizer.calculate_stop_loss_price(
            entry_price, PositionSide.SHORT, Decimal("0.01")
        )

        expected = Decimal("50500")  # 50000 * 1.01
        assert stop_loss == expected


class TestCircuitBreaker:
    """Test circuit breaker logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.breaker = CircuitBreaker(
            max_consecutive_losses=3,
            pause_duration_hours=2,
            slippage_threshold_bps=Decimal("15"),
        )

    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initializes correctly."""
        assert self.breaker.max_consecutive_losses == 3
        assert self.breaker.pause_duration == timedelta(hours=2)
        assert self.breaker.consecutive_losses == 0
        assert not self.breaker.is_paused

    def test_profitable_trade_resets_losses(self):
        """Test profitable trade resets consecutive losses."""
        self.breaker.consecutive_losses = 2
        self.breaker.record_trade_outcome(True)
        assert self.breaker.consecutive_losses == 0

    def test_loss_increments_counter(self):
        """Test losing trade increments counter."""
        self.breaker.record_trade_outcome(False)
        assert self.breaker.consecutive_losses == 1

    def test_circuit_break_triggers_on_max_losses(self):
        """Test circuit breaker triggers after max losses."""
        # Record 2 losses
        self.breaker.record_trade_outcome(False)
        self.breaker.record_trade_outcome(False)
        assert not self.breaker.is_paused

        # Third loss should trigger circuit break
        self.breaker.record_trade_outcome(False)
        assert self.breaker.is_paused
        assert self.breaker.consecutive_losses == 0

    def test_pause_duration_check(self):
        """Test pause duration check."""
        self.breaker.trigger_circuit_break()
        assert self.breaker.check_if_paused()

        # Simulate time passing
        self.breaker.last_circuit_break = datetime.now() - timedelta(hours=3)
        assert not self.breaker.check_if_paused()
        assert not self.breaker.is_paused

    def test_slippage_check_within_threshold(self):
        """Test slippage check within acceptable threshold."""
        expected = Decimal("50000")
        actual = Decimal("50007")  # 1.4 bps slippage
        assert self.breaker.check_slippage(expected, actual)

    def test_slippage_check_exceeds_threshold(self):
        """Test slippage check exceeding threshold."""
        expected = Decimal("50000")
        actual = Decimal("50080")  # 16 bps slippage
        assert not self.breaker.check_slippage(expected, actual)


class TestMeanReversionStrategy:
    """Test mean reversion strategy logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sizer = PositionSizer()
        self.strategy = MeanReversionStrategy(self.sizer)

    def test_entry_signal_above_vwap(self):
        """Test entry signal when price is above VWAP."""
        trigger_signal = TriggerSignal(
            TriggerType.PRICE_DEVIATION,
            Decimal("0.8"),
            datetime.now(),
            "BTCUSD",
            {"direction": "above", "deviation": Decimal("0.015")},
        )

        signal = self.strategy.generate_entry_signal(
            "BTCUSD",
            Decimal("51000"),  # Current price
            Decimal("50000"),  # VWAP 30min
            [trigger_signal],
            datetime.now(),
        )

        assert signal is not None
        assert signal.side == PositionSide.SHORT  # Mean reversion: sell high
        assert signal.strategy == StrategyType.MEAN_REVERSION
        assert signal.action == "enter"

    def test_entry_signal_below_vwap(self):
        """Test entry signal when price is below VWAP."""
        trigger_signal = TriggerSignal(
            TriggerType.PRICE_DEVIATION,
            Decimal("0.8"),
            datetime.now(),
            "BTCUSD",
            {"direction": "below", "deviation": Decimal("-0.015")},
        )

        signal = self.strategy.generate_entry_signal(
            "BTCUSD",
            Decimal("49000"),  # Current price
            Decimal("50000"),  # VWAP 30min
            [trigger_signal],
            datetime.now(),
        )

        assert signal is not None
        assert signal.side == PositionSide.LONG  # Mean reversion: buy low
        assert signal.strategy == StrategyType.MEAN_REVERSION

    def test_no_entry_without_triggers(self):
        """Test no entry signal without price deviation triggers."""
        signal = self.strategy.generate_entry_signal(
            "BTCUSD", Decimal("50000"), Decimal("50000"), [], datetime.now()
        )
        assert signal is None

    def test_vwap_touch_exit_long(self):
        """Test VWAP touch exit for long position."""
        position = Position(
            symbol="BTCUSD",
            side=PositionSide.LONG,
            strategy=StrategyType.MEAN_REVERSION,
            entry_price=Decimal("49000"),
            quantity=Decimal("1.0"),
            entry_time=datetime.now(),
        )

        # Price touches VWAP from below
        exit_signal = self.strategy.check_exit_conditions(
            position, Decimal("50000"), Decimal("50000"), datetime.now()
        )

        assert exit_signal is not None
        assert exit_signal.action == "take_profit"
        assert "VWAP touch" in exit_signal.reason

    def test_timeout_exit(self):
        """Test timeout exit after 36 hours."""
        old_time = datetime.now() - timedelta(hours=37)
        position = Position(
            symbol="BTCUSD",
            side=PositionSide.LONG,
            strategy=StrategyType.MEAN_REVERSION,
            entry_price=Decimal("49000"),
            quantity=Decimal("1.0"),
            entry_time=old_time,
        )

        exit_signal = self.strategy.check_exit_conditions(
            position, Decimal("49500"), Decimal("49800"), datetime.now()
        )

        assert exit_signal is not None
        assert exit_signal.action == "exit"
        assert "timeout" in exit_signal.reason


class TestMomentumStrategy:
    """Test momentum strategy logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sizer = PositionSizer()
        self.strategy = MomentumStrategy(self.sizer)

    def test_upward_momentum_entry(self):
        """Test entry signal for upward momentum."""
        volume_signal = TriggerSignal(
            TriggerType.VOLUME_SPIKE,
            Decimal("0.9"),
            datetime.now(),
            "BTCUSD",
            {"volume_ratio": Decimal("3.5")},
        )

        signal = self.strategy.generate_entry_signal(
            "BTCUSD",
            Decimal("52000"),  # Current price
            Decimal("51000"),  # VWAP 3min
            Decimal("50000"),  # VWAP 4h (below current - momentum up)
            [volume_signal],
            datetime.now(),
        )

        assert signal is not None
        assert signal.side == PositionSide.LONG
        assert signal.strategy == StrategyType.MOMENTUM

    def test_downward_momentum_entry(self):
        """Test entry signal for downward momentum."""
        volume_signal = TriggerSignal(
            TriggerType.VOLUME_SPIKE,
            Decimal("0.9"),
            datetime.now(),
            "BTCUSD",
            {"volume_ratio": Decimal("3.5")},
        )

        signal = self.strategy.generate_entry_signal(
            "BTCUSD",
            Decimal("48000"),  # Current price
            Decimal("49000"),  # VWAP 3min
            Decimal("50000"),  # VWAP 4h (above current - momentum down)
            [volume_signal],
            datetime.now(),
        )

        assert signal is not None
        assert signal.side == PositionSide.SHORT
        assert signal.strategy == StrategyType.MOMENTUM

    def test_trailing_stop_update_long(self):
        """Test trailing stop updates for long position."""
        position = Position(
            symbol="BTCUSD",
            side=PositionSide.LONG,
            strategy=StrategyType.MOMENTUM,
            entry_price=Decimal("50000"),
            quantity=Decimal("1.0"),
            entry_time=datetime.now(),
        )

        # Update trailing stop with VWAP4h
        self.strategy._update_trailing_stop(
            position, Decimal("52000"), Decimal("51000")
        )

        # Trailing stop should be VWAP4h - 0.9%
        expected_stop = Decimal("51000") * Decimal("0.991")
        assert position.trailing_stop_price == expected_stop

    def test_max_hold_time_exit(self):
        """Test exit after maximum hold time."""
        old_time = datetime.now() - timedelta(hours=73)
        position = Position(
            symbol="BTCUSD",
            side=PositionSide.LONG,
            strategy=StrategyType.MOMENTUM,
            entry_price=Decimal("50000"),
            quantity=Decimal("1.0"),
            entry_time=old_time,
        )

        exit_signal = self.strategy.check_exit_conditions(
            position, Decimal("52000"), Decimal("51000"), datetime.now()
        )

        assert exit_signal is not None
        assert exit_signal.action == "exit"
        assert "Maximum hold period" in exit_signal.reason


class TestRiskManager:
    """Test integrated risk manager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.risk_manager = RiskManager(base_equity=Decimal("100000"))

    def test_risk_manager_initialization(self):
        """Test risk manager initializes correctly."""
        assert len(self.risk_manager.active_positions) == 0
        assert len(self.risk_manager.cooldown_until) == 0
        assert self.risk_manager.is_trading_allowed("BTCUSD")

    def test_trading_not_allowed_during_circuit_break(self):
        """Test trading is blocked during circuit break."""
        self.risk_manager.circuit_breaker.trigger_circuit_break()
        assert not self.risk_manager.is_trading_allowed("BTCUSD")

    def test_trading_not_allowed_during_cooldown(self):
        """Test trading is blocked during cooldown."""
        self.risk_manager.cooldown_until["BTCUSD"] = datetime.now() + timedelta(hours=1)
        assert not self.risk_manager.is_trading_allowed("BTCUSD")

    def test_signal_generation_with_triggers(self):
        """Test signal generation with trigger data."""
        trigger_signal = TriggerSignal(
            TriggerType.PRICE_DEVIATION,
            Decimal("0.8"),
            datetime.now(),
            "BTCUSD",
            {"direction": "above", "deviation": Decimal("0.015")},
        )

        vwap_data = {
            "3min": Decimal("50500"),
            "30min": Decimal("50000"),
            "4hour": Decimal("49500"),
        }

        signals = self.risk_manager.generate_signals(
            "BTCUSD", Decimal("51000"), vwap_data, [trigger_signal], datetime.now()
        )

        # Should generate mean reversion signal (price above VWAP)
        assert len(signals) >= 1
        mean_rev_signals = [
            s for s in signals if s.strategy == StrategyType.MEAN_REVERSION
        ]
        assert len(mean_rev_signals) > 0
        assert mean_rev_signals[0].side == PositionSide.SHORT

    def test_position_entry_and_exit_cycle(self):
        """Test complete position entry and exit cycle."""
        entry_signal = TradeSignal(
            symbol="BTCUSD",
            strategy=StrategyType.MEAN_REVERSION,
            side=PositionSide.LONG,
            action="enter",
            price=Decimal("50000"),
            quantity=Decimal("1.0"),
            timestamp=datetime.now(),
            reason="Test entry",
        )

        # Enter position
        success = self.risk_manager.execute_signal(entry_signal)
        assert success
        assert "BTCUSD" in self.risk_manager.active_positions

        position = self.risk_manager.active_positions["BTCUSD"]
        assert position.stop_loss_price is not None

        # Exit position
        exit_signal = TradeSignal(
            symbol="BTCUSD",
            strategy=StrategyType.MEAN_REVERSION,
            side=PositionSide.LONG,
            action="take_profit",
            price=Decimal("51000"),
            quantity=Decimal("1.0"),
            timestamp=datetime.now(),
            reason="Test exit",
        )

        success = self.risk_manager.execute_signal(exit_signal)
        assert success
        assert "BTCUSD" not in self.risk_manager.active_positions

    def test_stop_loss_creates_cooldown(self):
        """Test stop loss execution creates cooldown period."""
        # Enter position first
        entry_signal = TradeSignal(
            symbol="BTCUSD",
            strategy=StrategyType.MEAN_REVERSION,
            side=PositionSide.LONG,
            action="enter",
            price=Decimal("50000"),
            quantity=Decimal("1.0"),
            timestamp=datetime.now(),
            reason="Test entry",
        )
        self.risk_manager.execute_signal(entry_signal)

        # Stop loss exit
        stop_loss_signal = TradeSignal(
            symbol="BTCUSD",
            strategy=StrategyType.MEAN_REVERSION,
            side=PositionSide.LONG,
            action="stop_loss",
            price=Decimal("49000"),
            quantity=Decimal("1.0"),
            timestamp=datetime.now(),
            reason="Stop loss",
        )

        self.risk_manager.execute_signal(stop_loss_signal)

        # Should be on cooldown
        assert not self.risk_manager.is_trading_allowed("BTCUSD")
        assert "BTCUSD" in self.risk_manager.cooldown_until

    def test_portfolio_summary(self):
        """Test portfolio summary generation."""
        summary = self.risk_manager.get_portfolio_summary()

        assert "active_positions" in summary
        assert "total_notional_value" in summary
        assert "circuit_breaker_active" in summary
        assert "consecutive_losses" in summary
        assert "symbols_on_cooldown" in summary

        assert summary["active_positions"] == 0
        assert not summary["circuit_breaker_active"]


class TestPositionModel:
    """Test Position model."""

    def test_position_notional_value(self):
        """Test position notional value calculation."""
        position = Position(
            symbol="BTCUSD",
            side=PositionSide.LONG,
            strategy=StrategyType.MEAN_REVERSION,
            entry_price=Decimal("50000"),
            quantity=Decimal("2.5"),
            entry_time=datetime.now(),
        )

        assert position.notional_value == Decimal("125000")

    def test_position_expiry_check(self):
        """Test position expiry check."""
        old_time = datetime.now() - timedelta(hours=2)
        position = Position(
            symbol="BTCUSD",
            side=PositionSide.LONG,
            strategy=StrategyType.MOMENTUM,
            entry_price=Decimal("50000"),
            quantity=Decimal("1.0"),
            entry_time=old_time,
            max_hold_time=timedelta(hours=1),
        )

        assert position.is_expired


class TestIntegration:
    """Integration tests for risk management system."""

    def setup_method(self):
        """Set up test fixtures."""
        self.risk_manager = RiskManager()

    def test_complete_mean_reversion_scenario(self):
        """Test complete mean reversion trading scenario."""
        # Setup: Price deviation trigger above VWAP
        trigger_signal = TriggerSignal(
            TriggerType.PRICE_DEVIATION,
            Decimal("0.9"),
            datetime.now(),
            "BTCUSD",
            {"direction": "above", "deviation": Decimal("0.02")},
        )

        vwap_data = {
            "3min": Decimal("51200"),
            "30min": Decimal("50000"),
            "4hour": Decimal("49000"),
        }

        # Generate entry signal
        signals = self.risk_manager.generate_signals(
            "BTCUSD", Decimal("51000"), vwap_data, [trigger_signal], datetime.now()
        )

        assert len(signals) > 0
        entry_signal = signals[0]
        assert entry_signal.strategy == StrategyType.MEAN_REVERSION
        assert (
            entry_signal.side == PositionSide.SHORT
        )  # Mean reversion against upward move

        # Execute entry
        success = self.risk_manager.execute_signal(entry_signal)
        assert success
        assert "BTCUSD" in self.risk_manager.active_positions

        # Check exit when price touches VWAP
        exit_signals = self.risk_manager.generate_signals(
            "BTCUSD", Decimal("50000"), vwap_data, [], datetime.now()
        )

        assert len(exit_signals) > 0
        exit_signal = exit_signals[0]
        assert exit_signal.action in ["take_profit", "exit"]

        # Execute exit
        success = self.risk_manager.execute_signal(exit_signal)
        assert success
        assert "BTCUSD" not in self.risk_manager.active_positions

    def test_circuit_breaker_integration(self):
        """Test circuit breaker integration with trading."""
        # Simulate 3 consecutive losing trades
        symbols = ["BTC_TEST_A", "BTC_TEST_B", "BTC_TEST_C"]
        for symbol in symbols:
            # Enter position
            entry_signal = TradeSignal(
                symbol=symbol,
                strategy=StrategyType.MEAN_REVERSION,
                side=PositionSide.LONG,
                action="enter",
                price=Decimal("50000"),
                quantity=Decimal("1.0"),
                timestamp=datetime.now(),
                reason="Test",
            )
            self.risk_manager.execute_signal(entry_signal)

            # Stop loss exit
            stop_signal = TradeSignal(
                symbol=symbol,
                strategy=StrategyType.MEAN_REVERSION,
                side=PositionSide.LONG,
                action="stop_loss",
                price=Decimal("49000"),
                quantity=Decimal("1.0"),
                timestamp=datetime.now(),
                reason="Stop loss",
            )
            self.risk_manager.execute_signal(stop_signal)

        # Circuit breaker should now be active
        assert not self.risk_manager.is_trading_allowed("NEWBTC")

        summary = self.risk_manager.get_portfolio_summary()
        assert summary["circuit_breaker_active"]
