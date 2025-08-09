"""
Volume Weighted Average Price (VWAP) calculations and analysis.

This module implements sophisticated VWAP calculations for volatility
harvesting strategies, including real-time VWAP tracking, deviation
analysis, and signal generation.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Union

try:
    import numpy as np
    from numba import njit

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    np = None

    # Fallback decorator that does nothing
    def njit(*args, **kwargs):
        def decorator(func):
            return func

        return decorator


@njit
def _calculate_vwap_numba_core(pv_array, volume_array):
    """Core Numba-optimized VWAP calculation."""
    if len(volume_array) == 0:
        return None

    total_volume = volume_array.sum()
    if total_volume == 0:
        return None

    total_pv = pv_array.sum()
    return total_pv / total_volume


class RingBuffer:
    """
    Memory-efficient ring buffer for storing price and volume data.
    Uses fixed-size circular buffer to maintain bounded memory usage.
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.buffer = [None] * capacity
        self.size = 0
        self.index = 0

    def append(self, item):
        """Add item to the buffer, overwriting oldest if at capacity."""
        self.buffer[self.index] = item
        self.index = (self.index + 1) % self.capacity
        if self.size < self.capacity:
            self.size += 1

    def get_items(self) -> list:
        """Get all items in chronological order."""
        if self.size == 0:
            return []

        if self.size < self.capacity:
            return [item for item in self.buffer[: self.size] if item is not None]
        else:
            # Buffer is full, need to reorder from oldest to newest
            oldest_idx = self.index
            return self.buffer[oldest_idx:] + self.buffer[:oldest_idx]

    def is_full(self) -> bool:
        """Check if buffer is at capacity."""
        return self.size == self.capacity

    def clear(self):
        """Clear all items from buffer."""
        self.buffer = [None] * self.capacity
        self.size = 0
        self.index = 0


class VWAPCalculator:
    """
    High-performance VWAP calculator with ring buffers for memory efficiency.
    Supports multiple timeframes and real-time updates.
    """

    def __init__(self, window_minutes: int = 30, max_data_points: int = 10000):
        """
        Initialize VWAP calculator.

        Args:
            window_minutes: VWAP calculation window in minutes
            max_data_points: Maximum data points to store in ring buffer
        """
        self.window_minutes = window_minutes
        self.window_seconds = window_minutes * 60

        # Ring buffer for efficient memory usage
        self.price_volume_buffer = RingBuffer(max_data_points)

        # Cache for performance
        self._cached_vwap: Optional[Decimal] = None
        self._cached_timestamp: Optional[datetime] = None
        self._cache_valid = False

        # Running totals for incremental updates
        self._cumulative_pv = Decimal("0")  # price * volume
        self._cumulative_volume = Decimal("0")

    def add_trade(
        self,
        price: Union[Decimal, float],
        volume: Union[Decimal, float],
        timestamp: datetime,
    ) -> None:
        """
        Add a new trade to the VWAP calculation.

        Args:
            price: Trade price
            volume: Trade volume
            timestamp: Trade timestamp
        """
        if isinstance(price, float):
            price = Decimal(str(price))
        if isinstance(volume, float):
            volume = Decimal(str(volume))

        trade_data = {
            "price": price,
            "volume": volume,
            "timestamp": timestamp,
            "pv": price * volume,
        }

        self.price_volume_buffer.append(trade_data)
        self._cache_valid = False

    def calculate_vwap(
        self, as_of_time: Optional[datetime] = None
    ) -> Optional[Decimal]:
        """
        Calculate VWAP for the specified time window.

        Args:
            as_of_time: Calculate VWAP as of this time. If None, uses latest data.

        Returns:
            VWAP value or None if insufficient data
        """
        if as_of_time is None:
            as_of_time = datetime.now()

        # Check cache validity
        if (
            self._cache_valid
            and self._cached_timestamp == as_of_time
            and self._cached_vwap is not None
        ):
            return self._cached_vwap

        cutoff_time = as_of_time - timedelta(seconds=self.window_seconds)
        valid_trades = []

        for trade in self.price_volume_buffer.get_items():
            if (
                trade
                and trade["timestamp"] > cutoff_time
                and trade["timestamp"] <= as_of_time
            ):
                valid_trades.append(trade)

        if not valid_trades:
            return None

        # Use optimized calculation if available
        if NUMBA_AVAILABLE and len(valid_trades) > 100:
            vwap = self._calculate_vwap_numba(valid_trades)
        else:
            vwap = self._calculate_vwap_python(valid_trades)

        # Update cache
        self._cached_vwap = vwap
        self._cached_timestamp = as_of_time
        self._cache_valid = True

        return vwap

    def _calculate_vwap_python(self, trades: list[dict]) -> Optional[Decimal]:
        """Pure Python VWAP calculation."""
        total_pv = Decimal("0")
        total_volume = Decimal("0")

        for trade in trades:
            total_pv += trade["pv"]
            total_volume += trade["volume"]

        if total_volume == 0:
            return None

        return total_pv / total_volume

    def _calculate_vwap_numba(self, trades: list[dict]) -> Optional[Decimal]:
        """Numba-optimized VWAP calculation (when available)."""
        if not NUMBA_AVAILABLE or np is None:
            # Fallback to Python implementation when Numba/numpy not available
            return self._calculate_vwap_python(trades)

        # Convert trade data to numpy arrays of floats for Numba
        pv_array = np.array([float(trade["pv"]) for trade in trades], dtype=float)
        volume_array = np.array(
            [float(trade["volume"]) for trade in trades], dtype=float
        )
        vwap = _calculate_vwap_numba_core(pv_array, volume_array)
        if vwap is None:
            return None
        return Decimal(str(vwap))

    def get_deviation_from_current_price(
        self,
        current_price: Union[Decimal, float],
        as_of_time: Optional[datetime] = None,
    ) -> Optional[Decimal]:
        """
        Calculate percentage deviation of current price from VWAP.

        Args:
            current_price: Current market price
            as_of_time: Calculate VWAP as of this time. If None, uses latest trade time.

        Returns:
            Percentage deviation (e.g., 0.01 for 1% above VWAP)
        """
        # If no specific time given, use the latest trade time or current time
        if as_of_time is None:
            # Get the latest trade time from buffer
            items = self.price_volume_buffer.get_items()
            if items:
                as_of_time = max(item["timestamp"] for item in items if item)
            else:
                as_of_time = datetime.now()

        vwap = self.calculate_vwap(as_of_time)
        if vwap is None or vwap == 0:
            return None

        if isinstance(current_price, float):
            current_price = Decimal(str(current_price))

        deviation = (current_price - vwap) / vwap
        return deviation

    def clear(self):
        """Clear all data and reset calculator."""
        self.price_volume_buffer.clear()
        self._cached_vwap = None
        self._cached_timestamp = None
        self._cache_valid = False
        self._cumulative_pv = Decimal("0")
        self._cumulative_volume = Decimal("0")


class MultiTimeframeVWAP:
    """
    Manages multiple VWAP calculators for different timeframes.
    """

    def __init__(self):
        """Initialize multi-timeframe VWAP calculator."""
        self.calculators = {
            "3min": VWAPCalculator(window_minutes=3),
            "30min": VWAPCalculator(window_minutes=30),
            "1hour": VWAPCalculator(window_minutes=60),
            "4hour": VWAPCalculator(window_minutes=240),
        }

    def add_trade(
        self,
        price: Union[Decimal, float],
        volume: Union[Decimal, float],
        timestamp: datetime,
    ) -> None:
        """Add trade to all timeframe calculators."""
        for calculator in self.calculators.values():
            calculator.add_trade(price, volume, timestamp)

    def get_vwap(
        self, timeframe: str, as_of_time: Optional[datetime] = None
    ) -> Optional[Decimal]:
        """Get VWAP for specific timeframe."""
        if timeframe not in self.calculators:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return self.calculators[timeframe].calculate_vwap(as_of_time)

    def get_all_vwaps(self, as_of_time: Optional[datetime] = None) -> dict:
        """Get VWAPs for all timeframes."""
        return {
            tf: calc.calculate_vwap(as_of_time) for tf, calc in self.calculators.items()
        }

    def get_deviation(
        self,
        timeframe: str,
        current_price: Union[Decimal, float],
        as_of_time: Optional[datetime] = None,
    ) -> Optional[Decimal]:
        """Get price deviation from VWAP for specific timeframe."""
        if timeframe not in self.calculators:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return self.calculators[timeframe].get_deviation_from_current_price(
            current_price, as_of_time
        )


class VolumeAggregator:
    """
    Aggregates volume data over specified time windows.
    """

    def __init__(self, window_minutes: int = 3, max_data_points: int = 5000):
        """
        Initialize volume aggregator.

        Args:
            window_minutes: Aggregation window in minutes
            max_data_points: Maximum data points to store
        """
        self.window_minutes = window_minutes
        self.window_seconds = window_minutes * 60
        self.volume_buffer = RingBuffer(max_data_points)

    def add_volume(self, volume: Union[Decimal, float], timestamp: datetime) -> None:
        """Add volume data point."""
        if isinstance(volume, float):
            volume = Decimal(str(volume))

        volume_data = {"volume": volume, "timestamp": timestamp}

        self.volume_buffer.append(volume_data)

    def get_total_volume(self, as_of_time: Optional[datetime] = None) -> Decimal:
        """Get total volume in the current window."""
        if as_of_time is None:
            as_of_time = datetime.now()

        cutoff_time = as_of_time - timedelta(seconds=self.window_seconds)
        total_volume = Decimal("0")

        for volume_data in self.volume_buffer.get_items():
            if (
                volume_data
                and volume_data["timestamp"] > cutoff_time
                and volume_data["timestamp"] <= as_of_time
            ):
                total_volume += volume_data["volume"]

        return total_volume

    def get_average_volume(
        self, periods: int = 10, as_of_time: Optional[datetime] = None
    ) -> Optional[Decimal]:
        """
        Get average volume over specified number of periods.

        Args:
            periods: Number of window periods to average over
            as_of_time: Calculate average as of this time

        Returns:
            Average volume or None if insufficient data
        """
        if as_of_time is None:
            as_of_time = datetime.now()

        volumes = []
        for i in range(periods):
            period_end = as_of_time - timedelta(seconds=self.window_seconds * i)
            period_start = period_end - timedelta(seconds=self.window_seconds)

            period_volume = Decimal("0")
            for volume_data in self.volume_buffer.get_items():
                if (
                    volume_data
                    and volume_data["timestamp"] > period_start
                    and volume_data["timestamp"] <= period_end
                ):
                    period_volume += volume_data["volume"]

            volumes.append(period_volume)

        if not volumes:
            return None

        return sum(volumes) / Decimal(str(len(volumes)))
