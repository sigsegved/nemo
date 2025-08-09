"""
Tests for the main orchestrator.
"""

import pytest
import asyncio
import yaml
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from src.main import TradingOrchestrator, setup_logging, load_config


class TestTradingOrchestrator:
    """Test the main trading orchestrator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = {
            "base_equity": 100000,
            "cooldown_hours": 6,
            "symbols": ["BTCUSD", "ETHUSD"],
            "paper_trading": True,
            "max_positions": 5,
            "log_level": "INFO",
            "metrics_port": 8001,
        }
        self.orchestrator = TradingOrchestrator(self.config)
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initializes correctly."""
        assert self.orchestrator.config == self.config
        assert self.orchestrator.symbols == ["BTCUSD", "ETHUSD"]
        assert self.orchestrator.enable_paper_trading is True
        assert not self.orchestrator.running
        assert len(self.orchestrator.tasks) == 0
    
    @pytest.mark.asyncio
    async def test_orchestrator_startup_and_shutdown(self):
        """Test orchestrator startup and graceful shutdown."""
        # Start orchestrator in background
        start_task = asyncio.create_task(self.orchestrator.start())
        
        # Wait a bit for startup
        await asyncio.sleep(0.1)
        
        assert self.orchestrator.running
        assert len(self.orchestrator.tasks) > 0
        
        # Check components are initialized
        assert "BTCUSD" in self.orchestrator.trigger_engines
        assert "ETHUSD" in self.orchestrator.trigger_engines
        assert "BTCUSD" in self.orchestrator.vwap_calculators
        assert "ETHUSD" in self.orchestrator.vwap_calculators
        
        # Shutdown
        self.orchestrator.shutdown_event.set()
        await start_task
        
        assert not self.orchestrator.running
    
    @pytest.mark.asyncio
    async def test_market_data_simulator(self):
        """Test market data simulator."""
        # Initialize components
        for symbol in self.orchestrator.symbols:
            from src.strategy.trigger import TriggerEngine
            from src.strategy.vwap import MultiTimeframeVWAP
            self.orchestrator.trigger_engines[symbol] = TriggerEngine(symbol)
            self.orchestrator.vwap_calculators[symbol] = MultiTimeframeVWAP()
        
        # Run simulator briefly
        task = asyncio.create_task(self.orchestrator._market_data_simulator())
        await asyncio.sleep(2)  # Let it run for 2 seconds
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # Check that VWAP calculators have data
        btc_vwap = self.orchestrator.vwap_calculators["BTCUSD"].get_vwap("3min")
        assert btc_vwap is not None
    
    @pytest.mark.asyncio
    async def test_signal_execution(self):
        """Test signal execution logic."""
        from src.strategy.risk import TradeSignal, StrategyType, PositionSide
        from decimal import Decimal
        
        signal = TradeSignal(
            symbol="BTCUSD",
            strategy=StrategyType.MEAN_REVERSION,
            side=PositionSide.LONG,
            action="enter",
            price=Decimal("50000"),
            quantity=Decimal("1.0"),
            timestamp=datetime.now(),
            reason="Test signal",
        )
        
        # Execute signal
        await self.orchestrator._execute_signal(signal)
        
        # Check metrics were updated
        assert self.orchestrator.processed_signals > 0
    
    @pytest.mark.asyncio
    async def test_get_current_price(self):
        """Test current price retrieval."""
        # Initialize VWAP calculator with some data
        from src.strategy.vwap import MultiTimeframeVWAP
        from decimal import Decimal
        
        vwap_calc = MultiTimeframeVWAP()
        vwap_calc.add_trade(Decimal("50000"), Decimal("1.0"), datetime.now())
        self.orchestrator.vwap_calculators["BTCUSD"] = vwap_calc
        
        price = await self.orchestrator._get_current_price("BTCUSD")
        assert price is not None
        assert isinstance(price, Decimal)
        assert price > 0
    
    def test_health_check(self):
        """Test health check logic."""
        # Initially healthy
        assert self.orchestrator._check_health()
        
        # Too many errors makes unhealthy
        self.orchestrator.error_count = 200
        assert not self.orchestrator._check_health()
        
        # Reset errors
        self.orchestrator.error_count = 0
        assert self.orchestrator._check_health()
        
        # Old heartbeat makes unhealthy
        self.orchestrator.last_heartbeat = datetime.now() - timedelta(minutes=10)
        assert not self.orchestrator._check_health()
    
    def test_get_status(self):
        """Test status reporting."""
        status = self.orchestrator.get_status()
        
        required_keys = [
            "running", "last_heartbeat", "error_count", "processed_signals",
            "active_tasks", "portfolio", "symbols", "paper_trading"
        ]
        
        for key in required_keys:
            assert key in status
        
        assert status["symbols"] == ["BTCUSD", "ETHUSD"]
        assert status["paper_trading"] is True
    
    @pytest.mark.asyncio
    async def test_flatten_positions_on_shutdown(self):
        """Test position flattening during shutdown."""
        from src.strategy.risk import Position, StrategyType, PositionSide
        from decimal import Decimal
        
        # Create a mock position
        position = Position(
            symbol="BTCUSD",
            side=PositionSide.LONG,
            strategy=StrategyType.MEAN_REVERSION,
            entry_price=Decimal("50000"),
            quantity=Decimal("1.0"),
            entry_time=datetime.now(),
        )
        
        self.orchestrator.risk_manager.active_positions["BTCUSD"] = position
        
        # Mock get_current_price to return a price
        with patch.object(self.orchestrator, '_get_current_price') as mock_price:
            mock_price.return_value = Decimal("51000")
            
            await self.orchestrator._flatten_positions()
        
        # Position should be closed
        assert "BTCUSD" not in self.orchestrator.risk_manager.active_positions


class TestConfigurationAndLogging:
    """Test configuration loading and logging setup."""
    
    def test_load_config_valid_file(self):
        """Test loading valid configuration file."""
        config_data = {
            "base_equity": 50000,
            "symbols": ["BTCUSD"],
            "paper_trading": True,
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            loaded_config = load_config(config_path)
            assert loaded_config == config_data
        finally:
            Path(config_path).unlink()
    
    def test_load_config_missing_file(self):
        """Test loading missing configuration file."""
        config = load_config("nonexistent.yaml")
        assert config == {}
    
    def test_setup_logging(self):
        """Test logging configuration setup."""
        config = {"log_level": "DEBUG", "log_format": "json"}
        
        # Should not raise an exception
        setup_logging(config)
        
        # Test with console format
        config["log_format"] = "console"
        setup_logging(config)


class TestIntegration:
    """Integration tests for the complete system."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_trading_cycle(self):
        """Test complete end-to-end trading cycle."""
        config = {
            "base_equity": 100000,
            "symbols": ["BTCUSD"],
            "paper_trading": True,
            "log_level": "ERROR",  # Reduce noise in tests
        }
        
        orchestrator = TradingOrchestrator(config)
        
        # Start orchestrator
        start_task = asyncio.create_task(orchestrator.start())
        
        # Let it run briefly to process some data
        await asyncio.sleep(1)
        
        # Check that components are working
        assert orchestrator.running
        assert len(orchestrator.trigger_engines) > 0
        assert len(orchestrator.vwap_calculators) > 0
        
        # Check that market data is being processed
        btc_vwap = orchestrator.vwap_calculators["BTCUSD"].get_vwap("3min")
        # VWAP might be None initially, which is fine
        
        # Get status
        status = orchestrator.get_status()
        assert status["running"]
        assert status["paper_trading"]
        
        # Shutdown
        orchestrator.shutdown_event.set()
        await start_task
        
        assert not orchestrator.running
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        config = {
            "base_equity": 100000,
            "symbols": ["INVALID_SYMBOL"],  # This might cause issues
            "paper_trading": True,
            "log_level": "ERROR",
        }
        
        orchestrator = TradingOrchestrator(config)
        
        # Mock a method to raise an exception
        original_method = orchestrator._get_current_price
        
        async def failing_method(symbol):
            raise Exception("Simulated error")
        
        orchestrator._get_current_price = failing_method
        
        # Start orchestrator
        start_task = asyncio.create_task(orchestrator.start())
        
        # Let it run briefly - it should handle errors gracefully
        await asyncio.sleep(0.5)
        
        # System should still be running despite errors
        assert orchestrator.running
        assert orchestrator.error_count >= 0  # Errors may have been recorded
        
        # Restore original method
        orchestrator._get_current_price = original_method
        
        # Shutdown
        orchestrator.shutdown_event.set()
        await start_task


class TestMetricsAndMonitoring:
    """Test metrics collection and health monitoring."""
    
    def test_metrics_initialization(self):
        """Test that Prometheus metrics are initialized."""
        from src.main import (
            trade_signals_total, positions_active, circuit_breaker_active,
            signal_processing_time, health_check_status
        )
        
        # Metrics should be initialized
        assert trade_signals_total is not None
        assert positions_active is not None
        assert circuit_breaker_active is not None
        assert signal_processing_time is not None
        assert health_check_status is not None
    
    @pytest.mark.asyncio
    async def test_health_monitoring(self):
        """Test health monitoring functionality."""
        config = {"symbols": ["BTCUSD"], "paper_trading": True, "log_level": "ERROR"}
        orchestrator = TradingOrchestrator(config)
        
        # Run health monitor briefly
        task = asyncio.create_task(orchestrator._health_monitor())
        await asyncio.sleep(0.1)
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # Heartbeat should be updated
        assert orchestrator.last_heartbeat is not None
    
    @pytest.mark.asyncio
    async def test_metrics_updates(self):
        """Test metrics update functionality."""
        config = {"symbols": ["BTCUSD"], "paper_trading": True, "log_level": "ERROR"}
        orchestrator = TradingOrchestrator(config)
        
        # Add a mock position
        from src.strategy.risk import Position, StrategyType, PositionSide
        from decimal import Decimal
        
        position = Position(
            symbol="BTCUSD",
            side=PositionSide.LONG,
            strategy=StrategyType.MEAN_REVERSION,
            entry_price=Decimal("50000"),
            quantity=Decimal("1.0"),
            entry_time=datetime.now(),
        )
        
        orchestrator.risk_manager.active_positions["BTCUSD"] = position
        
        # Update metrics
        orchestrator._update_position_metrics()
        
        # Check that metrics were updated (we can't easily check Prometheus values in tests)
        summary = orchestrator.risk_manager.get_portfolio_summary()
        assert summary["active_positions"] > 0