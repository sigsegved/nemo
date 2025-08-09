"""
Main orchestrator for the Nemo Volatility Harvest Bot.

This module serves as the entry point and coordinates all components
of the trading system including data providers, strategy execution,
risk management, and trade execution.
"""

import argparse
import asyncio
import signal
import sys
import logging
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import asdict

import yaml
import structlog
import uvloop
from prometheus_client import Counter, Histogram, Gauge, start_http_server

from .strategy.risk import RiskManager, TradeSignal
from .strategy.trigger import TriggerEngine
from .strategy.vwap import MultiTimeframeVWAP


# Prometheus metrics
trade_signals_total = Counter('nemo_trade_signals_total', 'Total trade signals generated', ['symbol', 'strategy', 'action'])
positions_active = Gauge('nemo_positions_active', 'Number of active positions')
circuit_breaker_active = Gauge('nemo_circuit_breaker_active', 'Circuit breaker status (1=active, 0=inactive)')
signal_processing_time = Histogram('nemo_signal_processing_seconds', 'Time spent processing signals')
health_check_status = Gauge('nemo_health_check_status', 'Health check status (1=healthy, 0=unhealthy)')


class TradingOrchestrator:
    """
    Main orchestrator that coordinates all trading system components.
    
    Manages:
    - Risk management and position tracking
    - Strategy execution and signal processing
    - Market data processing and VWAP calculations
    - Graceful shutdown and cleanup
    - Health monitoring and metrics
    """
    
    def __init__(self, config: Dict):
        """Initialize the trading orchestrator."""
        self.config = config
        self.logger = structlog.get_logger("nemo.orchestrator")
        
        # Core components
        self.risk_manager = RiskManager(
            base_equity=Decimal(str(config.get("base_equity", 100000))),
            cooldown_hours=config.get("cooldown_hours", 6),
        )
        
        # Per-symbol components
        self.trigger_engines: Dict[str, TriggerEngine] = {}
        self.vwap_calculators: Dict[str, MultiTimeframeVWAP] = {}
        
        # Async management
        self.tasks: Set[asyncio.Task] = set()
        self.shutdown_event = asyncio.Event()
        self.running = False
        
        # Health monitoring
        self.last_heartbeat = datetime.now()
        self.error_count = 0
        self.processed_signals = 0
        
        # Trading configuration
        self.symbols = config.get("symbols", ["BTCUSD", "ETHUSD"])
        self.enable_paper_trading = config.get("paper_trading", True)
        self.max_positions = config.get("max_positions", 5)
        
        self.logger.info("Trading orchestrator initialized", 
                        symbols=self.symbols, 
                        paper_trading=self.enable_paper_trading)
    
    async def start(self) -> None:
        """Start the trading orchestrator."""
        self.logger.info("Starting trading orchestrator")
        self.running = True
        
        try:
            # Initialize components for each symbol
            for symbol in self.symbols:
                self.trigger_engines[symbol] = TriggerEngine(symbol)
                self.vwap_calculators[symbol] = MultiTimeframeVWAP()
            
            # Start monitoring tasks
            self.tasks.add(asyncio.create_task(self._health_monitor()))
            self.tasks.add(asyncio.create_task(self._metrics_updater()))
            
            # Start main trading loop
            self.tasks.add(asyncio.create_task(self._trading_loop()))
            
            # Start market data simulation (for demo purposes)
            self.tasks.add(asyncio.create_task(self._market_data_simulator()))
            
            self.logger.info("All trading tasks started")
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
        except Exception as e:
            self.logger.error("Error in orchestrator main loop", error=str(e))
            self.error_count += 1
            raise
        finally:
            await self._shutdown()
    
    async def _trading_loop(self) -> None:
        """Main trading loop that processes signals and manages positions."""
        self.logger.info("Starting main trading loop")
        
        while not self.shutdown_event.is_set():
            try:
                # Process each symbol
                for symbol in self.symbols:
                    await self._process_symbol(symbol)
                
                # Update metrics
                self._update_position_metrics()
                
                # Brief pause to prevent overwhelming the system
                await asyncio.sleep(0.1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in trading loop", symbol=symbol, error=str(e))
                self.error_count += 1
                await asyncio.sleep(1)  # Pause on error
    
    async def _process_symbol(self, symbol: str) -> None:
        """Process trading logic for a specific symbol."""
        try:
            with signal_processing_time.time():
                # Get current market data (simulated for demo)
                current_price = await self._get_current_price(symbol)
                if current_price is None:
                    return
                
                # Get VWAP data
                vwap_calculator = self.vwap_calculators[symbol]
                vwap_data = {
                    "3min": vwap_calculator.get_vwap("3min"),
                    "30min": vwap_calculator.get_vwap("30min"),
                    "4hour": vwap_calculator.get_vwap("4hour"),
                }
                
                # Get recent trigger signals
                trigger_engine = self.trigger_engines[symbol]
                recent_signals = trigger_engine.get_recent_signals(minutes=5)
                
                # Generate trading signals
                trade_signals = self.risk_manager.generate_signals(
                    symbol=symbol,
                    current_price=current_price,
                    vwap_data=vwap_data,
                    trigger_signals=recent_signals,
                    timestamp=datetime.now(),
                )
                
                # Execute signals
                for signal in trade_signals:
                    await self._execute_signal(signal)
                    
        except Exception as e:
            self.logger.error("Error processing symbol", symbol=symbol, error=str(e))
            raise
    
    async def _execute_signal(self, signal: TradeSignal) -> None:
        """Execute a trading signal."""
        try:
            self.logger.info("Executing trading signal", 
                           symbol=signal.symbol,
                           action=signal.action,
                           strategy=signal.strategy.value,
                           side=signal.side.value,
                           price=str(signal.price),
                           quantity=str(signal.quantity),
                           reason=signal.reason)
            
            if self.enable_paper_trading:
                # Paper trading: just log the signal
                success = self.risk_manager.execute_signal(signal)
                status = "success" if success else "failed"
                self.logger.info("Paper trade executed", status=status, signal_id=id(signal))
            else:
                # Live trading would go here
                # success = await self._execute_live_trade(signal)
                success = False  # Placeholder
                self.logger.warning("Live trading not implemented", signal=asdict(signal))
            
            # Update metrics
            trade_signals_total.labels(
                symbol=signal.symbol,
                strategy=signal.strategy.value,
                action=signal.action
            ).inc()
            
            self.processed_signals += 1
            
        except Exception as e:
            self.logger.error("Error executing signal", signal=asdict(signal), error=str(e))
            self.error_count += 1
    
    async def _market_data_simulator(self) -> None:
        """Simulate market data for demo purposes."""
        self.logger.info("Starting market data simulator")
        
        # Base prices for simulation
        base_prices = {"BTCUSD": 50000, "ETHUSD": 3000}
        
        while not self.shutdown_event.is_set():
            try:
                timestamp = datetime.now()
                
                for symbol in self.symbols:
                    # Generate simulated price and volume
                    import random
                    base_price = base_prices.get(symbol, 50000)
                    
                    # Add some volatility
                    price_change = random.gauss(0, 0.002)  # 0.2% std dev
                    price = Decimal(str(base_price * (1 + price_change)))
                    volume = Decimal(str(random.uniform(0.1, 5.0)))
                    
                    # Update VWAP calculator
                    vwap_calc = self.vwap_calculators[symbol]
                    vwap_calc.add_trade(price, volume, timestamp)
                    
                    # Process through trigger engine
                    trigger_engine = self.trigger_engines[symbol]
                    signals = trigger_engine.process_trade(price, volume, timestamp)
                    
                    # Occasionally simulate liquidations
                    if random.random() < 0.01:  # 1% chance
                        liquidation_value = Decimal(str(random.uniform(10000, 100000)))
                        trigger_engine.process_liquidation(liquidation_value, timestamp)
                
                await asyncio.sleep(1)  # 1 second interval
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in market data simulator", error=str(e))
                await asyncio.sleep(5)
    
    async def _get_current_price(self, symbol: str) -> Optional[Decimal]:
        """Get current market price for symbol."""
        # In a real implementation, this would fetch from market data provider
        # For demo, we'll use the latest price from VWAP calculator
        vwap_calc = self.vwap_calculators.get(symbol)
        if not vwap_calc:
            return None
            
        # Get the most recent trade price (simplified)
        vwap = vwap_calc.get_vwap("3min")
        if vwap:
            # Add small random variation to simulate current price
            import random
            variation = random.gauss(0, 0.001)  # 0.1% std dev
            return vwap * Decimal(str(1 + variation))
        
        return None
    
    async def _health_monitor(self) -> None:
        """Monitor system health and update metrics."""
        self.logger.info("Starting health monitor")
        
        while not self.shutdown_event.is_set():
            try:
                self.last_heartbeat = datetime.now()
                
                # Check system health
                is_healthy = self._check_health()
                health_check_status.set(1 if is_healthy else 0)
                
                if not is_healthy:
                    self.logger.warning("System health check failed",
                                      error_count=self.error_count,
                                      active_tasks=len(self.tasks))
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in health monitor", error=str(e))
                await asyncio.sleep(60)
    
    async def _metrics_updater(self) -> None:
        """Update Prometheus metrics periodically."""
        while not self.shutdown_event.is_set():
            try:
                self._update_position_metrics()
                await asyncio.sleep(10)  # Update every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error updating metrics", error=str(e))
                await asyncio.sleep(30)
    
    def _update_position_metrics(self) -> None:
        """Update position-related metrics."""
        summary = self.risk_manager.get_portfolio_summary()
        positions_active.set(summary["active_positions"])
        circuit_breaker_active.set(1 if summary["circuit_breaker_active"] else 0)
    
    def _check_health(self) -> bool:
        """Check overall system health."""
        now = datetime.now()
        
        # Check if heartbeat is recent
        if now - self.last_heartbeat > timedelta(minutes=5):
            return False
        
        # Check error rate
        if self.error_count > 100:  # Too many errors
            return False
        
        # Check if tasks are running
        active_tasks = sum(1 for task in self.tasks if not task.done())
        if active_tasks < len(self.tasks) - 1:  # Allow for some completed tasks
            return False
        
        return True
    
    async def _shutdown(self) -> None:
        """Graceful shutdown of all components."""
        self.logger.info("Starting graceful shutdown")
        self.running = False
        
        try:
            # Cancel all tasks
            for task in self.tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete
            if self.tasks:
                await asyncio.gather(*self.tasks, return_exceptions=True)
            
            # Close any open positions (paper trading)
            if self.enable_paper_trading:
                await self._flatten_positions()
            
            self.logger.info("Graceful shutdown completed")
            
        except Exception as e:
            self.logger.error("Error during shutdown", error=str(e))
    
    async def _flatten_positions(self) -> None:
        """Close all open positions during shutdown."""
        try:
            active_positions = list(self.risk_manager.active_positions.items())
            
            for symbol, position in active_positions:
                current_price = await self._get_current_price(symbol)
                if current_price is None:
                    current_price = position.entry_price  # Fallback
                
                # Create exit signal
                exit_signal = TradeSignal(
                    symbol=symbol,
                    strategy=position.strategy,
                    side=position.side,
                    action="exit",
                    price=current_price,
                    quantity=position.quantity,
                    timestamp=datetime.now(),
                    reason="Shutdown position flattening",
                )
                
                self.risk_manager.execute_signal(exit_signal)
                self.logger.info("Position closed for shutdown", symbol=symbol)
                
        except Exception as e:
            self.logger.error("Error flattening positions", error=str(e))
    
    def get_status(self) -> Dict:
        """Get current system status."""
        portfolio = self.risk_manager.get_portfolio_summary()
        
        return {
            "running": self.running,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "error_count": self.error_count,
            "processed_signals": self.processed_signals,
            "active_tasks": len([t for t in self.tasks if not t.done()]),
            "portfolio": portfolio,
            "symbols": self.symbols,
            "paper_trading": self.enable_paper_trading,
        }


def setup_logging(config: Dict) -> None:
    """Configure structured logging."""
    log_level = config.get("log_level", "INFO").upper()
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.dev.ConsoleRenderer() if config.get("log_format") != "json" else structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level)),
        logger_factory=structlog.WriteLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def load_config(config_path: str) -> Dict:
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config or {}
    except Exception as e:
        print(f"Error loading config from {config_path}: {e}", file=sys.stderr)
        return {}


async def main_async(config_path: str, trading_mode: str) -> None:
    """Async main function."""
    # Load configuration
    config = load_config(config_path)
    config["paper_trading"] = trading_mode == "paper"
    
    # Setup logging
    setup_logging(config)
    logger = structlog.get_logger("nemo.main")
    
    logger.info("Starting Nemo Volatility Harvest Bot",
                config_path=config_path,
                trading_mode=trading_mode)
    
    # Start Prometheus metrics server
    metrics_port = config.get("metrics_port", 8000)
    start_http_server(metrics_port)
    logger.info("Metrics server started", port=metrics_port)
    
    # Create and start orchestrator
    orchestrator = TradingOrchestrator(config)
    
    # Setup signal handlers for graceful shutdown
    def signal_handler():
        logger.info("Shutdown signal received")
        orchestrator.shutdown_event.set()
    
    # Register signal handlers
    for sig in [signal.SIGTERM, signal.SIGINT]:
        signal.signal(sig, lambda s, f: signal_handler())
    
    try:
        await orchestrator.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error("Fatal error in main loop", error=str(e), traceback=traceback.format_exc())
        raise
    finally:
        logger.info("Nemo bot shutdown complete")


def main():
    """
    Main entry point for the Nemo trading bot.

    This function will:
    1. Parse command line arguments
    2. Load configuration from specified config file
    3. Initialize data and trade providers
    4. Set up strategy engines and risk management
    5. Start the main trading loop
    6. Handle shutdown gracefully
    """
    parser = argparse.ArgumentParser(
        description="Nemo Volatility Harvest Bot - Algorithmic Trading System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )

    trading_group = parser.add_mutually_exclusive_group(required=True)
    trading_group.add_argument(
        "--paper-trading",
        action="store_true",
        help="Start in paper trading mode (recommended for testing)",
    )
    trading_group.add_argument(
        "--live-trading",
        action="store_true",
        help="Start in live trading mode (use with caution)",
    )

    args = parser.parse_args()

    # Validate config file exists
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file '{args.config}' not found.", file=sys.stderr)
        sys.exit(1)

    # Determine trading mode
    trading_mode = "paper" if args.paper_trading else "live"

    print("Nemo Volatility Harvest Bot - Starting...")
    print(f"Configuration: {args.config}")
    print(f"Trading Mode: {trading_mode}")

    # Use uvloop for better performance on Unix systems
    if sys.platform != "win32":
        try:
            uvloop.install()
        except ImportError:
            pass  # uvloop not available

    # Run the async main function
    try:
        asyncio.run(main_async(str(config_path), trading_mode))
    except KeyboardInterrupt:
        print("\nShutdown complete.")
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
