"""
Trading trigger logic and signal generation.

This module implements the core trigger mechanisms that determine when
to enter or exit positions based on market conditions, VWAP analysis,
and volatility patterns.
"""

from collections import deque
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional, Union

from .vwap import VolumeAggregator, VWAPCalculator


class TriggerType(Enum):
    """Types of trading triggers."""

    PRICE_DEVIATION = "price_deviation"
    VOLUME_SPIKE = "volume_spike"
    LIQUIDATION_CLUSTER = "liquidation_cluster"
    VWAP_CROSS = "vwap_cross"


class TriggerSignal:
    """Represents a trading trigger signal."""

    def __init__(
        self,
        trigger_type: TriggerType,
        strength: Decimal,
        timestamp: datetime,
        symbol: str,
        metadata: Optional[dict] = None,
    ):
        """
        Initialize trigger signal.

        Args:
            trigger_type: Type of trigger
            strength: Signal strength (0.0 to 1.0)
            timestamp: When trigger occurred
            symbol: Trading symbol
            metadata: Additional trigger-specific data
        """
        self.trigger_type = trigger_type
        self.strength = strength
        self.timestamp = timestamp
        self.symbol = symbol
        self.metadata = metadata or {}

    def __repr__(self):
        return (
            f"TriggerSignal({self.trigger_type.value}, "
            f"strength={self.strength}, symbol={self.symbol})"
        )


class PriceDeviationTrigger:
    """
    Monitors price deviation from VWAP and generates signals when
    |Price - VWAP30| / VWAP30 ≥ threshold.
    """

    def __init__(
        self, threshold: Decimal = Decimal("0.01"), vwap_window_minutes: int = 30
    ):
        """
        Initialize price deviation trigger.

        Args:
            threshold: Deviation threshold (e.g., 0.01 for 1%)
            vwap_window_minutes: VWAP calculation window
        """
        self.threshold = threshold
        self.vwap_calculator = VWAPCalculator(window_minutes=vwap_window_minutes)
        self.last_signal_time: Optional[datetime] = None
        self.cooldown_seconds = 60  # Minimum time between signals

    def add_trade(
        self,
        price: Union[Decimal, float],
        volume: Union[Decimal, float],
        timestamp: datetime,
    ) -> None:
        """Add trade data to VWAP calculator."""
        self.vwap_calculator.add_trade(price, volume, timestamp)

    def check_trigger(
        self, current_price: Union[Decimal, float], symbol: str, timestamp: datetime
    ) -> Optional[TriggerSignal]:
        """
        Check if price deviation trigger should fire.

        Args:
            current_price: Current market price
            symbol: Trading symbol
            timestamp: Current timestamp

        Returns:
            TriggerSignal if trigger conditions met, None otherwise
        """
        # Check cooldown
        if (
            self.last_signal_time
            and (timestamp - self.last_signal_time).total_seconds()
            < self.cooldown_seconds
        ):
            return None

        # Calculate deviation
        deviation = self.vwap_calculator.get_deviation_from_current_price(
            current_price, timestamp
        )
        if deviation is None:
            return None

        abs_deviation = abs(deviation)

        if abs_deviation >= self.threshold:
            # Calculate signal strength based on how much threshold is exceeded
            strength = min(abs_deviation / self.threshold, Decimal("2.0")) / Decimal(
                "2.0"
            strength = min(
                abs_deviation / self.threshold, self.MAX_SIGNAL_STRENGTH_FACTOR
            ) / self.MAX_SIGNAL_STRENGTH_FACTOR

            self.last_signal_time = timestamp

            return TriggerSignal(
                trigger_type=TriggerType.PRICE_DEVIATION,
                strength=strength,
                timestamp=timestamp,
                symbol=symbol,
                metadata={
                    "deviation": deviation,
                    "threshold": self.threshold,
                    "vwap": self.vwap_calculator.calculate_vwap(),
                    "current_price": current_price,
                    "direction": "above" if deviation > 0 else "below",
                },
            )

        return None


class VolumeSpikeTrigger:
    """
    Detects volume spikes when 3-min volume ≥ 3× average volume.
    """

    def __init__(
        self,
        spike_multiplier: Decimal = Decimal("3.0"),
        window_minutes: int = 3,
        lookback_periods: int = 10,
    ):
        """
        Initialize volume spike trigger.

        Args:
            spike_multiplier: Multiplier for average volume (e.g., 3.0 for 3x)
            window_minutes: Volume aggregation window
            lookback_periods: Number of periods to calculate average
        """
        self.spike_multiplier = spike_multiplier
        self.volume_aggregator = VolumeAggregator(window_minutes=window_minutes)
        self.lookback_periods = lookback_periods
        self.last_signal_time: Optional[datetime] = None
        self.cooldown_seconds = 180  # 3-minute cooldown

    def add_volume(self, volume: Union[Decimal, float], timestamp: datetime) -> None:
        """Add volume data point."""
        self.volume_aggregator.add_volume(volume, timestamp)

    def check_trigger(
        self, symbol: str, timestamp: datetime
    ) -> Optional[TriggerSignal]:
        """
        Check if volume spike trigger should fire.

        Args:
            symbol: Trading symbol
            timestamp: Current timestamp

        Returns:
            TriggerSignal if trigger conditions met, None otherwise
        """
        # Check cooldown
        if (
            self.last_signal_time
            and (timestamp - self.last_signal_time).total_seconds()
            < self.cooldown_seconds
        ):
            return None

        # Get current and average volume
        current_volume = self.volume_aggregator.get_total_volume(timestamp)
        avg_volume = self.volume_aggregator.get_average_volume(
            periods=self.lookback_periods, as_of_time=timestamp
        )

        if avg_volume is None or avg_volume == 0:
            return None

        volume_ratio = current_volume / avg_volume

        if volume_ratio >= self.spike_multiplier:
            # Calculate signal strength
            strength = min(
                volume_ratio / self.spike_multiplier, Decimal("2.0")
                volume_ratio / self.spike_multiplier, MAX_SIGNAL_STRENGTH
            ) / MAX_SIGNAL_STRENGTH

            self.last_signal_time = timestamp

            return TriggerSignal(
                trigger_type=TriggerType.VOLUME_SPIKE,
                strength=strength,
                timestamp=timestamp,
                symbol=symbol,
                metadata={
                    "current_volume": current_volume,
                    "average_volume": avg_volume,
                    "volume_ratio": volume_ratio,
                    "spike_threshold": self.spike_multiplier,
                },
            )

        return None


class LiquidationTracker:
    """
    Tracks liquidation sums over 3-minute windows to detect liquidation clusters.
    """

    def __init__(
        self, window_minutes: int = 3, min_liquidation_sum: Decimal = Decimal("100000")
    ):
        """
        Initialize liquidation tracker.

        Args:
            window_minutes: Tracking window in minutes
            min_liquidation_sum: Minimum liquidation sum to trigger signal
        """
        self.window_minutes = window_minutes
        self.window_seconds = window_minutes * 60
        self.min_liquidation_sum = min_liquidation_sum
        self.liquidations: deque = deque()
        self.last_signal_time: Optional[datetime] = None
        self.cooldown_seconds = 180  # 3-minute cooldown

    def add_liquidation(
        self, liquidation_value: Union[Decimal, float], timestamp: datetime
    ) -> None:
        """
        Add liquidation event.

        Args:
            liquidation_value: Value of liquidated position
            timestamp: Liquidation timestamp
        """
        if isinstance(liquidation_value, float):
            liquidation_value = Decimal(str(liquidation_value))

        self.liquidations.append({"value": liquidation_value, "timestamp": timestamp})

        # Clean old liquidations
        self._clean_old_liquidations(timestamp)

    def _clean_old_liquidations(self, current_time: datetime) -> None:
        """Remove liquidations outside the tracking window."""
        cutoff_time = current_time - timedelta(seconds=self.window_seconds)

        while self.liquidations and self.liquidations[0]["timestamp"] < cutoff_time:
            self.liquidations.popleft()

    def get_liquidation_sum(self, as_of_time: Optional[datetime] = None) -> Decimal:
        """Get total liquidation value in current window."""
        if as_of_time is None:
            as_of_time = datetime.now()

        self._clean_old_liquidations(as_of_time)

        total = Decimal("0")
        for liquidation in self.liquidations:
            total += liquidation["value"]

        return total

    def check_trigger(
        self, symbol: str, timestamp: datetime
    ) -> Optional[TriggerSignal]:
        """
        Check if liquidation cluster trigger should fire.

        Args:
            symbol: Trading symbol
            timestamp: Current timestamp

        Returns:
            TriggerSignal if trigger conditions met, None otherwise
        """
        # Check cooldown
        if (
            self.last_signal_time
            and (timestamp - self.last_signal_time).total_seconds()
            < self.cooldown_seconds
        ):
            return None

        liquidation_sum = self.get_liquidation_sum(timestamp)

        if liquidation_sum >= self.min_liquidation_sum:
            # Calculate signal strength
            strength = min(
                liquidation_sum / self.min_liquidation_sum, Decimal("2.0")
                liquidation_sum / self.min_liquidation_sum, MAX_STRENGTH_MULTIPLIER
            ) / MAX_STRENGTH_MULTIPLIER

            self.last_signal_time = timestamp

            return TriggerSignal(
                trigger_type=TriggerType.LIQUIDATION_CLUSTER,
                strength=strength,
                timestamp=timestamp,
                symbol=symbol,
                metadata={
                    "liquidation_sum": liquidation_sum,
                    "threshold": self.min_liquidation_sum,
                    "liquidation_count": len(self.liquidations),
                },
            )

        return None


class TriggerEngine:
    """
    Main trigger engine that coordinates all trigger types and generates trading signals.
    """

    def __init__(self, symbol: str):
        """
        Initialize trigger engine for a specific symbol.

        Args:
            symbol: Trading symbol to monitor
        """
        self.symbol = symbol

        # Initialize trigger components
        self.price_deviation_trigger = PriceDeviationTrigger()
        self.volume_spike_trigger = VolumeSpikeTrigger()
        self.liquidation_tracker = LiquidationTracker()

        # Signal history
        self.signal_history: list[TriggerSignal] = []
        self.max_history_length = 1000

    def process_trade(
        self,
        price: Union[Decimal, float],
        volume: Union[Decimal, float],
        timestamp: datetime,
    ) -> list[TriggerSignal]:
        """
        Process a new trade and check all triggers.

        Args:
            price: Trade price
            volume: Trade volume
            timestamp: Trade timestamp

        Returns:
            List of triggered signals
        """
        signals = []

        # Add trade data to relevant triggers
        self.price_deviation_trigger.add_trade(price, volume, timestamp)
        self.volume_spike_trigger.add_volume(volume, timestamp)

        # Check price deviation trigger
        price_signal = self.price_deviation_trigger.check_trigger(
            price, self.symbol, timestamp
        )
        if price_signal:
            signals.append(price_signal)

        # Check volume spike trigger
        volume_signal = self.volume_spike_trigger.check_trigger(self.symbol, timestamp)
        if volume_signal:
            signals.append(volume_signal)

        # Check liquidation trigger
        liquidation_signal = self.liquidation_tracker.check_trigger(
            self.symbol, timestamp
        )
        if liquidation_signal:
            signals.append(liquidation_signal)

        # Store signals in history
        for signal in signals:
            self._add_to_history(signal)

        return signals

    def process_liquidation(
        self, liquidation_value: Union[Decimal, float], timestamp: datetime
    ) -> Optional[TriggerSignal]:
        """
        Process a liquidation event.

        Args:
            liquidation_value: Value of liquidated position
            timestamp: Liquidation timestamp

        Returns:
            TriggerSignal if liquidation cluster detected
        """
        self.liquidation_tracker.add_liquidation(liquidation_value, timestamp)
        signal = self.liquidation_tracker.check_trigger(self.symbol, timestamp)

        if signal:
            self._add_to_history(signal)

        return signal

    def _add_to_history(self, signal: TriggerSignal) -> None:
        """Add signal to history with size limit."""
        self.signal_history.append(signal)

        # Maintain history size limit
        if len(self.signal_history) > self.max_history_length:
            self.signal_history = self.signal_history[-self.max_history_length :]

    def get_recent_signals(
        self, minutes: int = 60, as_of_time: Optional[datetime] = None
    ) -> list[TriggerSignal]:
        """Get signals from the last N minutes."""
        if as_of_time is None:
            as_of_time = datetime.now()

        cutoff_time = as_of_time - timedelta(minutes=minutes)

        return [
            signal for signal in self.signal_history if signal.timestamp >= cutoff_time
        ]

    def get_signal_counts(
        self, minutes: int = 60, as_of_time: Optional[datetime] = None
    ) -> dict[TriggerType, int]:
        """Get count of signals by type in the last N minutes."""
        recent_signals = self.get_recent_signals(minutes, as_of_time)

        counts = dict.fromkeys(TriggerType, 0)

        for signal in recent_signals:
            counts[signal.trigger_type] += 1

        return counts

    def clear_history(self) -> None:
        """Clear signal history."""
        self.signal_history.clear()
