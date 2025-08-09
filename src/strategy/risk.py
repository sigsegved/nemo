"""
Risk management and position sizing logic.

This module implements comprehensive risk management including position
sizing, stop-loss logic, drawdown protection, and portfolio-level
risk controls.
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Union
from dataclasses import dataclass

from .vwap import MultiTimeframeVWAP
from .trigger import TriggerEngine, TriggerSignal


class StrategyType(Enum):
    """Types of trading strategies."""
    
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"


class PositionSide(Enum):
    """Position direction."""
    
    LONG = "long"
    SHORT = "short"


@dataclass
class Position:
    """Represents an active trading position."""
    
    symbol: str
    side: PositionSide
    strategy: StrategyType
    entry_price: Decimal
    quantity: Decimal
    entry_time: datetime
    stop_loss_price: Optional[Decimal] = None
    take_profit_price: Optional[Decimal] = None
    trailing_stop_price: Optional[Decimal] = None
    max_hold_time: Optional[timedelta] = None
    
    @property
    def notional_value(self) -> Decimal:
        """Calculate position's notional value."""
        return self.entry_price * self.quantity
    
    @property
    def is_expired(self) -> bool:
        """Check if position has exceeded max hold time."""
        if self.max_hold_time is None:
            return False
        return datetime.now() - self.entry_time > self.max_hold_time


@dataclass
class TradeSignal:
    """Represents a trading signal with entry/exit instructions."""
    
    symbol: str
    strategy: StrategyType
    side: PositionSide
    action: str  # "enter", "exit", "stop_loss", "take_profit"
    price: Decimal
    quantity: Decimal
    timestamp: datetime
    reason: str
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class PositionSizer:
    """Handles position sizing and leverage calculations."""
    
    def __init__(
        self,
        max_equity_per_position: Decimal = Decimal("0.25"),  # 25% max per position
        max_leverage: Decimal = Decimal("3.0"),  # 3x leverage
        base_equity: Decimal = Decimal("100000"),  # $100k base
    ):
        """
        Initialize position sizer.
        
        Args:
            max_equity_per_position: Maximum equity allocation per position
            max_leverage: Maximum leverage allowed
            base_equity: Base equity amount
        """
        self.max_equity_per_position = max_equity_per_position
        self.max_leverage = max_leverage
        self.base_equity = base_equity
    
    def calculate_position_size(
        self,
        symbol: str,
        price: Decimal,
        strategy: StrategyType,
        signal_strength: Decimal = Decimal("1.0"),
    ) -> Decimal:
        """
        Calculate position size based on risk parameters.
        
        Args:
            symbol: Trading symbol
            price: Entry price
            strategy: Strategy type
            signal_strength: Signal strength (0.0 to 1.0)
            
        Returns:
            Position size in base currency
        """
        # Base equity allocation per position
        base_allocation = self.base_equity * self.max_equity_per_position
        
        # Apply leverage based on strategy
        if strategy == StrategyType.MEAN_REVERSION:
            leverage = self.max_leverage  # Full 3x leverage for mean reversion
        else:
            leverage = Decimal("2.0")  # 2x leverage for momentum
        
        # Adjust by signal strength
        adjusted_allocation = base_allocation * signal_strength
        leveraged_allocation = adjusted_allocation * leverage
        
        # Calculate quantity
        quantity = leveraged_allocation / price
        
        return quantity
    
    def calculate_stop_loss_price(
        self,
        entry_price: Decimal,
        side: PositionSide,
        stop_loss_pct: Decimal = Decimal("0.01"),  # 1% stop loss
    ) -> Decimal:
        """Calculate stop loss price."""
        if side == PositionSide.LONG:
            return entry_price * (Decimal("1.0") - stop_loss_pct)
        else:
            return entry_price * (Decimal("1.0") + stop_loss_pct)


class CircuitBreaker:
    """Implements circuit breaker logic for risk control."""
    
    def __init__(
        self,
        max_consecutive_losses: int = 3,
        pause_duration_hours: int = 2,
        slippage_threshold_bps: Decimal = Decimal("15"),  # 15 basis points
    ):
        """
        Initialize circuit breaker.
        
        Args:
            max_consecutive_losses: Max consecutive stop losses before pause
            pause_duration_hours: Hours to pause trading after circuit break
            slippage_threshold_bps: Slippage threshold in basis points
        """
        self.max_consecutive_losses = max_consecutive_losses
        self.pause_duration = timedelta(hours=pause_duration_hours)
        self.slippage_threshold_bps = slippage_threshold_bps
        
        # State tracking
        self.consecutive_losses = 0
        self.last_circuit_break: Optional[datetime] = None
        self.is_paused = False
    
    def record_trade_outcome(self, is_profitable: bool) -> None:
        """Record the outcome of a trade."""
        if is_profitable:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            
            # Check for circuit break
            if self.consecutive_losses >= self.max_consecutive_losses:
                self.trigger_circuit_break()
    
    def trigger_circuit_break(self) -> None:
        """Trigger circuit breaker pause."""
        self.is_paused = True
        self.last_circuit_break = datetime.now()
        self.consecutive_losses = 0
    
    def check_if_paused(self) -> bool:
        """Check if trading is currently paused."""
        if not self.is_paused:
            return False
            
        if self.last_circuit_break is None:
            return False
            
        # Check if pause duration has elapsed
        if datetime.now() - self.last_circuit_break > self.pause_duration:
            self.is_paused = False
            return False
            
        return True
    
    def check_slippage(self, expected_price: Decimal, actual_price: Decimal) -> bool:
        """
        Check if slippage exceeds threshold.
        
        Returns:
            True if slippage is acceptable, False if circuit break needed
        """
        slippage = abs(actual_price - expected_price) / expected_price
        slippage_bps = slippage * Decimal("10000")  # Convert to basis points
        
        return slippage_bps <= self.slippage_threshold_bps


class MeanReversionStrategy:
    """Implements mean reversion trading strategy."""
    
    def __init__(self, position_sizer: PositionSizer):
        """Initialize mean reversion strategy."""
        self.position_sizer = position_sizer
        self.profit_target_hours = 36
        self.stop_loss_pct = Decimal("0.01")  # 1%
    
    def generate_entry_signal(
        self,
        symbol: str,
        current_price: Decimal,
        vwap_30min: Decimal,
        trigger_signals: List[TriggerSignal],
        timestamp: datetime,
    ) -> Optional[TradeSignal]:
        """
        Generate entry signal for mean reversion.
        
        Strategy: Enter against the move when price deviates from VWAP.
        """
        if vwap_30min is None:
            return None
            
        # Check for price deviation trigger
        deviation_signals = [
            sig for sig in trigger_signals 
            if sig.trigger_type.value == "price_deviation"
        ]
        
        if not deviation_signals:
            return None
            
        # Get the strongest deviation signal
        strongest_signal = max(deviation_signals, key=lambda x: x.strength)
        deviation_direction = strongest_signal.metadata.get("direction")
        
        if deviation_direction == "above":
            # Price above VWAP, enter short (mean reversion)
            side = PositionSide.SHORT
        elif deviation_direction == "below":
            # Price below VWAP, enter long (mean reversion)
            side = PositionSide.LONG
        else:
            return None
            
        # Calculate position size
        quantity = self.position_sizer.calculate_position_size(
            symbol, current_price, StrategyType.MEAN_REVERSION, strongest_signal.strength
        )
        
        return TradeSignal(
            symbol=symbol,
            strategy=StrategyType.MEAN_REVERSION,
            side=side,
            action="enter",
            price=current_price,
            quantity=quantity,
            timestamp=timestamp,
            reason=f"Mean reversion entry against {deviation_direction} VWAP deviation",
            metadata={
                "vwap": vwap_30min,
                "deviation": strongest_signal.metadata.get("deviation"),
                "signal_strength": strongest_signal.strength,
            },
        )
    
    def check_exit_conditions(
        self,
        position: Position,
        current_price: Decimal,
        vwap_30min: Decimal,
        timestamp: datetime,
    ) -> Optional[TradeSignal]:
        """Check if position should be exited."""
        
        # Check take profit: VWAP touch
        if self._check_vwap_touch(position, current_price, vwap_30min):
            return TradeSignal(
                symbol=position.symbol,
                strategy=position.strategy,
                side=position.side,
                action="take_profit",
                price=current_price,
                quantity=position.quantity,
                timestamp=timestamp,
                reason="VWAP touch profit target reached",
            )
        
        # Check timeout (36 hours)
        if self._check_timeout(position, timestamp):
            return TradeSignal(
                symbol=position.symbol,
                strategy=position.strategy,
                side=position.side,
                action="exit",
                price=current_price,
                quantity=position.quantity,
                timestamp=timestamp,
                reason="36-hour timeout reached",
            )
        
        # Check stop loss
        if self._check_stop_loss(position, current_price):
            return TradeSignal(
                symbol=position.symbol,
                strategy=position.strategy,
                side=position.side,
                action="stop_loss",
                price=current_price,
                quantity=position.quantity,
                timestamp=timestamp,
                reason="Stop loss triggered",
            )
        
        return None
    
    def _check_vwap_touch(self, position: Position, current_price: Decimal, vwap: Decimal) -> bool:
        """Check if price has touched VWAP for profit taking."""
        if vwap is None:
            return False
            
        if position.side == PositionSide.LONG:
            # Long position: profit when price rises back to VWAP
            return current_price >= vwap
        else:
            # Short position: profit when price falls back to VWAP
            return current_price <= vwap
    
    def _check_timeout(self, position: Position, timestamp: datetime) -> bool:
        """Check if position has reached timeout."""
        return timestamp - position.entry_time > timedelta(hours=self.profit_target_hours)
    
    def _check_stop_loss(self, position: Position, current_price: Decimal) -> bool:
        """Check if stop loss should be triggered."""
        if position.stop_loss_price is None:
            return False
            
        if position.side == PositionSide.LONG:
            return current_price <= position.stop_loss_price
        else:
            return current_price >= position.stop_loss_price


class MomentumStrategy:
    """Implements momentum trading strategy."""
    
    def __init__(self, position_sizer: PositionSizer):
        """Initialize momentum strategy."""
        self.position_sizer = position_sizer
        self.max_hold_hours = 72
        self.trailing_stop_pct = Decimal("0.009")  # 0.9%
        self.pullback_threshold = Decimal("0.003")  # 0.3% pullback
    
    def generate_entry_signal(
        self,
        symbol: str,
        current_price: Decimal,
        vwap_3min: Decimal,
        vwap_4h: Decimal,
        trigger_signals: List[TriggerSignal],
        timestamp: datetime,
    ) -> Optional[TradeSignal]:
        """
        Generate entry signal for momentum strategy.
        
        Strategy: Enter with the move after 3-min pullback (using available timeframes).
        """
        if vwap_3min is None or vwap_4h is None:
            return None
            
        # Check for volume spike (momentum confirmation)
        volume_signals = [
            sig for sig in trigger_signals 
            if sig.trigger_type.value == "volume_spike"
        ]
        
        if not volume_signals:
            return None
            
        # Determine momentum direction based on 4h VWAP
        if current_price > vwap_4h * (Decimal("1.0") + self.pullback_threshold):
            # Upward momentum, enter long after pullback
            side = PositionSide.LONG
        elif current_price < vwap_4h * (Decimal("1.0") - self.pullback_threshold):
            # Downward momentum, enter short after pullback
            side = PositionSide.SHORT
        else:
            return None
            
        # Get strongest volume signal
        strongest_signal = max(volume_signals, key=lambda x: x.strength)
        
        # Calculate position size
        quantity = self.position_sizer.calculate_position_size(
            symbol, current_price, StrategyType.MOMENTUM, strongest_signal.strength
        )
        
        return TradeSignal(
            symbol=symbol,
            strategy=StrategyType.MOMENTUM,
            side=side,
            action="enter",
            price=current_price,
            quantity=quantity,
            timestamp=timestamp,
            reason="Momentum entry after pullback",
            metadata={
                "vwap_3min": vwap_3min,
                "vwap_4h": vwap_4h,
                "signal_strength": strongest_signal.strength,
            },
        )
    
    def check_exit_conditions(
        self,
        position: Position,
        current_price: Decimal,
        vwap_4h: Decimal,
        timestamp: datetime,
    ) -> Optional[TradeSignal]:
        """Check if momentum position should be exited."""
        
        # Update trailing stop
        self._update_trailing_stop(position, current_price, vwap_4h)
        
        # Check trailing stop
        if self._check_trailing_stop(position, current_price):
            return TradeSignal(
                symbol=position.symbol,
                strategy=position.strategy,
                side=position.side,
                action="stop_loss",
                price=current_price,
                quantity=position.quantity,
                timestamp=timestamp,
                reason="Trailing stop triggered",
            )
        
        # Check max hold time (72 hours)
        if timestamp - position.entry_time > timedelta(hours=self.max_hold_hours):
            return TradeSignal(
                symbol=position.symbol,
                strategy=position.strategy,
                side=position.side,
                action="exit",
                price=current_price,
                quantity=position.quantity,
                timestamp=timestamp,
                reason="Maximum hold period reached",
            )
        
        return None
    
    def _update_trailing_stop(self, position: Position, current_price: Decimal, vwap_4h: Decimal) -> None:
        """Update trailing stop based on VWAP4h - 0.9%."""
        if vwap_4h is None:
            return
            
        if position.side == PositionSide.LONG:
            # For long positions, trailing stop is below VWAP4h
            new_stop = vwap_4h * (Decimal("1.0") - self.trailing_stop_pct)
            if position.trailing_stop_price is None or new_stop > position.trailing_stop_price:
                position.trailing_stop_price = new_stop
        else:
            # For short positions, trailing stop is above VWAP4h
            new_stop = vwap_4h * (Decimal("1.0") + self.trailing_stop_pct)
            if position.trailing_stop_price is None or new_stop < position.trailing_stop_price:
                position.trailing_stop_price = new_stop
    
    def _check_trailing_stop(self, position: Position, current_price: Decimal) -> bool:
        """Check if trailing stop should be triggered."""
        if position.trailing_stop_price is None:
            return False
            
        if position.side == PositionSide.LONG:
            return current_price <= position.trailing_stop_price
        else:
            return current_price >= position.trailing_stop_price


class RiskManager:
    """Main risk management coordinator."""
    
    def __init__(
        self,
        base_equity: Decimal = Decimal("100000"),
        cooldown_hours: int = 6,
    ):
        """Initialize risk manager."""
        self.position_sizer = PositionSizer(base_equity=base_equity)
        self.circuit_breaker = CircuitBreaker()
        self.mean_reversion = MeanReversionStrategy(self.position_sizer)
        self.momentum = MomentumStrategy(self.position_sizer)
        
        # Position tracking
        self.active_positions: Dict[str, Position] = {}
        self.cooldown_until: Dict[str, datetime] = {}
        self.cooldown_duration = timedelta(hours=cooldown_hours)
    
    def is_trading_allowed(self, symbol: str) -> bool:
        """Check if trading is allowed for symbol."""
        # Check circuit breaker
        if self.circuit_breaker.check_if_paused():
            return False
            
        # Check symbol-specific cooldown
        if symbol in self.cooldown_until:
            if datetime.now() < self.cooldown_until[symbol]:
                return False
            else:
                del self.cooldown_until[symbol]
        
        return True
    
    def generate_signals(
        self,
        symbol: str,
        current_price: Decimal,
        vwap_data: Dict[str, Decimal],
        trigger_signals: List[TriggerSignal],
        timestamp: datetime,
    ) -> List[TradeSignal]:
        """Generate trading signals based on market data."""
        signals = []
        
        if not self.is_trading_allowed(symbol):
            return signals
            
        # Check existing positions for exit signals
        if symbol in self.active_positions:
            position = self.active_positions[symbol]
            
            if position.strategy == StrategyType.MEAN_REVERSION:
                exit_signal = self.mean_reversion.check_exit_conditions(
                    position, current_price, vwap_data.get("30min"), timestamp
                )
            else:  # MOMENTUM
                exit_signal = self.momentum.check_exit_conditions(
                    position, current_price, vwap_data.get("4hour"), timestamp
                )
            
            if exit_signal:
                signals.append(exit_signal)
        
        else:
            # Generate entry signals for new positions
            
            # Mean reversion entry
            mean_rev_signal = self.mean_reversion.generate_entry_signal(
                symbol, current_price, vwap_data.get("30min"), trigger_signals, timestamp
            )
            if mean_rev_signal:
                signals.append(mean_rev_signal)
            
            # Momentum entry
            momentum_signal = self.momentum.generate_entry_signal(
                symbol, current_price, vwap_data.get("3min"), 
                vwap_data.get("4hour"), trigger_signals, timestamp
            )
            if momentum_signal:
                signals.append(momentum_signal)
        
        return signals
    
    def execute_signal(self, signal: TradeSignal) -> bool:
        """Execute a trading signal."""
        if signal.action == "enter":
            return self._enter_position(signal)
        elif signal.action in ["exit", "stop_loss", "take_profit"]:
            return self._exit_position(signal)
        
        return False
    
    def _enter_position(self, signal: TradeSignal) -> bool:
        """Enter a new position."""
        # Check if we already have a position
        if signal.symbol in self.active_positions:
            return False
            
        # Create position
        position = Position(
            symbol=signal.symbol,
            side=signal.side,
            strategy=signal.strategy,
            entry_price=signal.price,
            quantity=signal.quantity,
            entry_time=signal.timestamp,
        )
        
        # Set stop loss
        position.stop_loss_price = self.position_sizer.calculate_stop_loss_price(
            signal.price, signal.side
        )
        
        # Set max hold time for momentum
        if signal.strategy == StrategyType.MOMENTUM:
            position.max_hold_time = timedelta(hours=72)
        
        self.active_positions[signal.symbol] = position
        return True
    
    def _exit_position(self, signal: TradeSignal) -> bool:
        """Exit an existing position."""
        if signal.symbol not in self.active_positions:
            return False
            
        position = self.active_positions[signal.symbol]
        
        # Calculate P&L
        if position.side == PositionSide.LONG:
            pnl = (signal.price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - signal.price) * position.quantity
            
        is_profitable = pnl > 0
        
        # Record outcome for circuit breaker
        self.circuit_breaker.record_trade_outcome(is_profitable)
        
        # Set cooldown if stop loss
        if signal.action == "stop_loss":
            self.cooldown_until[signal.symbol] = datetime.now() + self.cooldown_duration
        
        # Remove position
        del self.active_positions[signal.symbol]
        
        return True
    
    def get_portfolio_summary(self) -> Dict:
        """Get current portfolio summary."""
        total_positions = len(self.active_positions)
        total_notional = sum(pos.notional_value for pos in self.active_positions.values())
        
        return {
            "active_positions": total_positions,
            "total_notional_value": total_notional,
            "circuit_breaker_active": self.circuit_breaker.check_if_paused(),
            "consecutive_losses": self.circuit_breaker.consecutive_losses,
            "symbols_on_cooldown": len(self.cooldown_until),
        }
