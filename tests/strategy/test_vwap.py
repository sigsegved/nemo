"""
Unit tests for VWAP calculation module.

Tests VWAP accuracy, ring buffer functionality, and performance.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from strategy.vwap import (
    RingBuffer, VWAPCalculator, MultiTimeframeVWAP, VolumeAggregator
)


class TestRingBuffer:
    """Test cases for RingBuffer implementation."""
    
    def test_ring_buffer_initialization(self):
        """Test ring buffer initializes correctly."""
        buffer = RingBuffer(5)
        assert buffer.capacity == 5
        assert buffer.size == 0
        assert buffer.index == 0
        assert len(buffer.get_items()) == 0
    
    def test_ring_buffer_append_within_capacity(self):
        """Test appending items within capacity."""
        buffer = RingBuffer(3)
        
        buffer.append(1)
        assert buffer.size == 1
        assert buffer.get_items() == [1]
        
        buffer.append(2)
        assert buffer.size == 2
        assert buffer.get_items() == [1, 2]
        
        buffer.append(3)
        assert buffer.size == 3
        assert buffer.get_items() == [1, 2, 3]
        assert buffer.is_full()
    
    def test_ring_buffer_circular_overwrite(self):
        """Test circular overwriting when at capacity."""
        buffer = RingBuffer(3)
        
        # Fill buffer
        for i in range(1, 4):
            buffer.append(i)
        
        # Test overwriting
        buffer.append(4)
        assert buffer.size == 3
        assert buffer.get_items() == [2, 3, 4]
        
        buffer.append(5)
        assert buffer.get_items() == [3, 4, 5]
    
    def test_ring_buffer_clear(self):
        """Test buffer clearing."""
        buffer = RingBuffer(3)
        buffer.append(1)
        buffer.append(2)
        
        buffer.clear()
        assert buffer.size == 0
        assert buffer.index == 0
        assert len(buffer.get_items()) == 0


class TestVWAPCalculator:
    """Test cases for VWAP calculation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.calculator = VWAPCalculator(window_minutes=30)
        self.base_time = datetime(2024, 1, 1, 12, 0, 0)
    
    def test_vwap_calculator_initialization(self):
        """Test VWAP calculator initializes correctly."""
        calc = VWAPCalculator(window_minutes=15)
        assert calc.window_minutes == 15
        assert calc.window_seconds == 900
        assert calc._cached_vwap is None
        assert not calc._cache_valid
    
    def test_simple_vwap_calculation(self):
        """Test basic VWAP calculation with known values."""
        # Add test trades: price 100 with volume 10, price 110 with volume 20
        # Expected VWAP = (100*10 + 110*20) / (10+20) = 3200/30 = 106.67
        
        self.calculator.add_trade(
            Decimal('100'), Decimal('10'), self.base_time
        )
        self.calculator.add_trade(
            Decimal('110'), Decimal('20'), self.base_time + timedelta(minutes=1)
        )
        
        vwap = self.calculator.calculate_vwap(self.base_time + timedelta(minutes=2))
        expected = Decimal('3200') / Decimal('30')
        
        assert vwap is not None
        assert abs(vwap - expected) < Decimal('0.01')
    
    def test_vwap_with_time_window(self):
        """Test VWAP respects time window."""
        # Add trades outside window
        old_time = self.base_time - timedelta(minutes=35)
        self.calculator.add_trade(Decimal('50'), Decimal('100'), old_time)
        
        # Add trades within window
        self.calculator.add_trade(
            Decimal('100'), Decimal('10'), self.base_time
        )
        self.calculator.add_trade(
            Decimal('110'), Decimal('20'), self.base_time + timedelta(minutes=1)
        )
        
        vwap = self.calculator.calculate_vwap(self.base_time + timedelta(minutes=2))
        
        # Should only include trades within 30-minute window
        expected = Decimal('3200') / Decimal('30')
        assert vwap is not None
        assert abs(vwap - expected) < Decimal('0.01')
    
    def test_vwap_empty_data(self):
        """Test VWAP returns None with no data."""
        vwap = self.calculator.calculate_vwap()
        assert vwap is None
    
    def test_vwap_deviation_calculation(self):
        """Test price deviation from VWAP calculation."""
        self.calculator.add_trade(Decimal('100'), Decimal('10'), self.base_time)
        
        # Current price 5% above VWAP
        deviation = self.calculator.get_deviation_from_current_price(Decimal('105'))
        assert deviation is not None
        assert abs(deviation - Decimal('0.05')) < Decimal('0.001')
        
        # Current price 3% below VWAP
        deviation = self.calculator.get_deviation_from_current_price(Decimal('97'))
        assert deviation is not None
        assert abs(deviation - Decimal('-0.03')) < Decimal('0.001')
    
    def test_vwap_cache_functionality(self):
        """Test VWAP caching works correctly."""
        self.calculator.add_trade(Decimal('100'), Decimal('10'), self.base_time)
        
        # First calculation
        vwap1 = self.calculator.calculate_vwap(self.base_time)
        assert self.calculator._cache_valid
        assert self.calculator._cached_vwap == vwap1
        
        # Second calculation with same timestamp should use cache
        vwap2 = self.calculator.calculate_vwap(self.base_time)
        assert vwap1 == vwap2
        
        # Adding new trade should invalidate cache
        self.calculator.add_trade(Decimal('110'), Decimal('20'), self.base_time)
        assert not self.calculator._cache_valid
    
    def test_vwap_with_float_inputs(self):
        """Test VWAP handles float inputs correctly."""
        self.calculator.add_trade(100.0, 10.0, self.base_time)
        self.calculator.add_trade(110.0, 20.0, self.base_time + timedelta(minutes=1))
        
        vwap = self.calculator.calculate_vwap(self.base_time + timedelta(minutes=2))
        expected = Decimal('3200') / Decimal('30')
        
        assert vwap is not None
        assert abs(vwap - expected) < Decimal('0.01')


class TestMultiTimeframeVWAP:
    """Test cases for multi-timeframe VWAP."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mtf_vwap = MultiTimeframeVWAP()
        self.base_time = datetime(2024, 1, 1, 12, 0, 0)
    
    def test_multi_timeframe_initialization(self):
        """Test multi-timeframe VWAP initializes correctly."""
        assert '3min' in self.mtf_vwap.calculators
        assert '30min' in self.mtf_vwap.calculators
        assert '1hour' in self.mtf_vwap.calculators
        assert '4hour' in self.mtf_vwap.calculators
    
    def test_add_trade_to_all_timeframes(self):
        """Test trade is added to all timeframe calculators."""
        self.mtf_vwap.add_trade(Decimal('100'), Decimal('10'), self.base_time)
        
        # All calculators should have the trade
        for calc in self.mtf_vwap.calculators.values():
            vwap = calc.calculate_vwap(self.base_time)
            assert vwap == Decimal('100')
    
    def test_get_specific_timeframe_vwap(self):
        """Test getting VWAP for specific timeframe."""
        self.mtf_vwap.add_trade(Decimal('100'), Decimal('10'), self.base_time)
        
        vwap_3min = self.mtf_vwap.get_vwap('3min')
        vwap_30min = self.mtf_vwap.get_vwap('30min')
        
        assert vwap_3min == Decimal('100')
        assert vwap_30min == Decimal('100')
    
    def test_get_all_vwaps(self):
        """Test getting all VWAPs at once."""
        self.mtf_vwap.add_trade(Decimal('100'), Decimal('10'), self.base_time)
        
        all_vwaps = self.mtf_vwap.get_all_vwaps()
        
        assert len(all_vwaps) == 4
        for timeframe in ['3min', '30min', '1hour', '4hour']:
            assert timeframe in all_vwaps
            assert all_vwaps[timeframe] == Decimal('100')
    
    def test_invalid_timeframe_error(self):
        """Test error on invalid timeframe."""
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            self.mtf_vwap.get_vwap('invalid')
        
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            self.mtf_vwap.get_deviation('invalid', Decimal('100'))


class TestVolumeAggregator:
    """Test cases for volume aggregation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.aggregator = VolumeAggregator(window_minutes=3)
        self.base_time = datetime(2024, 1, 1, 12, 0, 0)
    
    def test_volume_aggregator_initialization(self):
        """Test volume aggregator initializes correctly."""
        agg = VolumeAggregator(window_minutes=5)
        assert agg.window_minutes == 5
        assert agg.window_seconds == 300
    
    def test_volume_aggregation(self):
        """Test basic volume aggregation."""
        # Add volumes within window
        self.aggregator.add_volume(Decimal('100'), self.base_time)
        self.aggregator.add_volume(Decimal('200'), self.base_time + timedelta(minutes=1))
        self.aggregator.add_volume(Decimal('150'), self.base_time + timedelta(minutes=2))
        
        total_volume = self.aggregator.get_total_volume(self.base_time + timedelta(minutes=2, seconds=30))
        assert total_volume == Decimal('450')
    
    def test_volume_window_filtering(self):
        """Test volume aggregation respects time window."""
        # Add volume outside window
        old_time = self.base_time - timedelta(minutes=5)
        self.aggregator.add_volume(Decimal('1000'), old_time)
        
        # Add volumes within window
        self.aggregator.add_volume(Decimal('100'), self.base_time)
        self.aggregator.add_volume(Decimal('200'), self.base_time + timedelta(minutes=1))
        
        total_volume = self.aggregator.get_total_volume(self.base_time + timedelta(minutes=2))
        # Should only include volumes within 3-minute window
        assert total_volume == Decimal('300')
    
    def test_average_volume_calculation(self):
        """Test average volume calculation over multiple periods."""
        # Add consistent volume over multiple periods
        for i in range(5):
            period_start = self.base_time - timedelta(minutes=3*i)
            self.aggregator.add_volume(Decimal('100'), period_start)
            self.aggregator.add_volume(Decimal('200'), period_start + timedelta(minutes=1))
        
        avg_volume = self.aggregator.get_average_volume(
            periods=3, as_of_time=self.base_time + timedelta(minutes=1)
        )
        
        # Each period should have 300 total volume
        assert avg_volume == Decimal('300')
    
    def test_float_volume_handling(self):
        """Test volume aggregator handles float inputs."""
        self.aggregator.add_volume(100.5, self.base_time)
        self.aggregator.add_volume(200.25, self.base_time + timedelta(minutes=1))
        
        total_volume = self.aggregator.get_total_volume(self.base_time + timedelta(minutes=2))
        expected = Decimal('100.5') + Decimal('200.25')
        assert total_volume == expected


# Integration tests
class TestVWAPIntegration:
    """Integration tests for VWAP system components."""
    
    def test_real_world_vwap_scenario(self):
        """Test VWAP calculation with realistic market data."""
        calculator = VWAPCalculator(window_minutes=30)
        base_time = datetime(2024, 1, 1, 9, 30, 0)  # Market open
        
        # Simulate realistic trading pattern
        trades = [
            (Decimal('100.50'), Decimal('1000'), base_time),
            (Decimal('100.75'), Decimal('1500'), base_time + timedelta(minutes=5)),
            (Decimal('100.25'), Decimal('800'), base_time + timedelta(minutes=10)),
            (Decimal('101.00'), Decimal('2000'), base_time + timedelta(minutes=15)),
            (Decimal('100.80'), Decimal('1200'), base_time + timedelta(minutes=20)),
        ]
        
        for price, volume, timestamp in trades:
            calculator.add_trade(price, volume, timestamp)
        
        vwap = calculator.calculate_vwap(base_time + timedelta(minutes=25))
        
        # Manual calculation for verification
        total_pv = (Decimal('100.50') * Decimal('1000') + 
                   Decimal('100.75') * Decimal('1500') + 
                   Decimal('100.25') * Decimal('800') + 
                   Decimal('101.00') * Decimal('2000') + 
                   Decimal('100.80') * Decimal('1200'))
        total_volume = Decimal('6500')
        expected_vwap = total_pv / total_volume
        
        assert vwap is not None
        assert abs(vwap - expected_vwap) < Decimal('0.001')
        
        # Test deviation calculation
        current_price = Decimal('102.00')
        deviation = calculator.get_deviation_from_current_price(current_price)
        expected_deviation = (current_price - expected_vwap) / expected_vwap
        
        assert deviation is not None
        assert abs(deviation - expected_deviation) < Decimal('0.001')


if __name__ == '__main__':
    # Run tests if executed directly
    pytest.main([__file__, '-v'])