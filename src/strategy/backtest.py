"""
Backtesting engine and strategy validation.

This module provides comprehensive backtesting capabilities for strategy
development, optimization, and validation using historical market data.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from ..common.models import (
    OHLCV,
    BacktestMetrics,
    BacktestTrade,
    FundingRate,
    MarketRegime,
    TradeTick,
)
from ..common.provider_base import HistoricalDataProvider
from .llm_gate import HeuristicLLMProxy
from .risk import RiskManager, TradeSignal
from .trigger import TriggerEngine
from .vwap import MultiTimeframeVWAP

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Comprehensive backtesting engine with walk-forward testing support.

    Simulates the complete trading workflow using historical data to
    measure strategy performance and optimize parameters.
    """

    def __init__(
        self, historical_data_provider: HistoricalDataProvider, config: dict[str, Any]
    ):
        """
        Initialize backtest engine.

        Args:
            historical_data_provider: Provider for historical market data
            config: Backtest configuration parameters
        """
        self.historical_data_provider = historical_data_provider
        self.config = config

        # Extract backtest parameters
        self.symbols = config.get("SYMBOLS", ["BTC-GUSD-PERP"])
        self.initial_equity = Decimal(str(config.get("INITIAL_EQUITY", 100000)))
        self.slippage_bps = Decimal(
            str(config.get("SLIPPAGE_BPS", 5))
        )  # 5 basis points
        self.fee_bps = Decimal(str(config.get("FEE_BPS", 8)))  # 8 basis points

        # Strategy parameters
        self.price_dev_threshold = Decimal(str(config.get("PRICE_DEV", 0.01)))
        self.vol_mult = Decimal(str(config.get("VOL_MULT", 3)))
        self.llm_conf = Decimal(str(config.get("LLM_CONF", 0.65)))

        # Risk parameters
        self.max_leverage = Decimal(str(config.get("MAX_LEVERAGE", 3)))
        self.stop_loss_pct = Decimal(str(config.get("STOP_LOSS_PCT", 0.01)))
        self.cooldown_hours = config.get("COOLDOWN_HR", 6)

        # Initialize components
        self.risk_manager = RiskManager(
            base_equity=self.initial_equity, cooldown_hours=self.cooldown_hours
        )
        self.llm_proxy = HeuristicLLMProxy(confidence_threshold=self.llm_conf)

        # Backtesting state
        self.current_equity = self.initial_equity
        self.trades: list[BacktestTrade] = []
        self.equity_curve: list[tuple[datetime, Decimal]] = []
        self.open_positions: dict[str, BacktestTrade] = {}

        # Performance tracking
        self.total_fees = Decimal("0")
        self.total_slippage = Decimal("0")
        self.total_funding = Decimal("0")
        self.peak_equity = self.initial_equity
        self.max_drawdown = Decimal("0")

    async def load_historical_data(
        self, symbols: list[str], start_date: datetime, end_date: datetime
    ) -> dict[str, list[OHLCV]]:
        """
        Load historical OHLCV data for backtesting.

        Args:
            symbols: List of trading symbols
            start_date: Start date for historical data
            end_date: End date for historical data

        Returns:
            Dictionary mapping symbols to their OHLCV data
        """
        logger.info(f"Loading historical data from {start_date} to {end_date}")

        await self.historical_data_provider.connect()

        try:
            candles = await self.historical_data_provider.get_candles(
                symbols, start_date, end_date, interval="1m"
            )

            # Group candles by symbol
            data_by_symbol = defaultdict(list)
            for candle in candles:
                data_by_symbol[candle.symbol].append(candle)

            # Sort by timestamp
            for symbol in data_by_symbol:
                data_by_symbol[symbol].sort(key=lambda x: x.timestamp)

            logger.info(f"Loaded {len(candles)} candles for {len(symbols)} symbols")
            return dict(data_by_symbol)

        finally:
            await self.historical_data_provider.disconnect()

    async def simulate_strategy(
        self,
        config: dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        train_end_date: Optional[datetime] = None,
    ) -> BacktestMetrics:
        """
        Run strategy simulation on historical data.

        Args:
            config: Strategy configuration parameters
            start_date: Start date for simulation
            end_date: End date for simulation
            train_end_date: End of training period for walk-forward testing

        Returns:
            BacktestMetrics with comprehensive performance results
        """
        logger.info(f"Starting backtest simulation from {start_date} to {end_date}")

        # Load historical data
        historical_data = await self.load_historical_data(
            self.symbols, start_date, end_date
        )

        # Initialize per-symbol components
        vwap_calculators = {symbol: MultiTimeframeVWAP() for symbol in self.symbols}
        trigger_engines = {symbol: TriggerEngine(symbol) for symbol in self.symbols}

        # Load funding rate data for cost calculation
        funding_rates = await self._load_funding_rates(start_date, end_date)

        # Initialize equity curve with starting point
        self.equity_curve = [(start_date, self.initial_equity)]
        # Simulate trading for each symbol
        for symbol in self.symbols:
            if symbol not in historical_data:
                logger.warning(f"No historical data for {symbol}, skipping")
                continue

            await self._simulate_symbol(
                symbol,
                historical_data[symbol],
                vwap_calculators[symbol],
                trigger_engines[symbol],
                funding_rates.get(symbol, []),
                train_end_date,
            )

        # Add final equity curve point
        if not self.equity_curve or self.equity_curve[-1][0] < end_date:
            self.equity_curve.append((end_date, self.current_equity))

        # Calculate final metrics
        return self.calculate_metrics(self.trades, self.equity_curve)

    async def _simulate_symbol(
        self,
        symbol: str,
        candles: list[OHLCV],
        vwap_calc: MultiTimeframeVWAP,
        trigger_engine: TriggerEngine,
        funding_rates: list[FundingRate],
        train_end_date: Optional[datetime],
    ) -> None:
        """Simulate trading for a single symbol."""
        logger.info(f"Simulating trading for {symbol} with {len(candles)} candles")

        funding_iter = iter(funding_rates)
        current_funding = next(funding_iter, None)

        for i, candle in enumerate(candles):
            # Skip if this is training data and we're in test mode
            if train_end_date and candle.timestamp <= train_end_date:
                continue

            # Update VWAP with candle data
            typical_price = candle.typical_price
            vwap_calc.add_trade(typical_price, candle.volume, candle.timestamp)

            # Create trade tick from candle
            trade_tick = TradeTick(
                symbol=symbol,
                price=candle.close_price,
                size=candle.volume,
                timestamp=candle.timestamp,
                side="buy",  # Default side for candle data
                high=candle.high_price,
                low=candle.low_price,
                open_price=candle.open_price,
                volume=candle.volume,
            )

            # Add to LLM proxy for regime analysis
            self.llm_proxy.add_market_data(trade_tick)

            # Process trade through trigger engine
            trigger_signals = trigger_engine.process_trade(
                candle.close_price, candle.volume, candle.timestamp
            )

            # Get market regime classification
            market_regime = self.llm_proxy.classify_market_regime(
                candle.timestamp, symbol, candle.close_price
            )

            # Skip trading if LLM proxy says no
            if not self.llm_proxy.should_trade(market_regime, "mean_reversion"):
                continue

            # Get VWAP values for risk manager
            vwap_data = vwap_calc.get_all_vwaps(candle.timestamp)

            # Generate trading signals
            trade_signals = self.risk_manager.generate_signals(
                symbol, candle.close_price, vwap_data, trigger_signals, candle.timestamp
            )

            # Execute signals
            for signal in trade_signals:
                await self._execute_signal(signal, candle, market_regime)

            # Update funding costs
            if current_funding and candle.timestamp >= current_funding.timestamp:
                self._apply_funding_cost(symbol, current_funding)
                current_funding = next(funding_iter, None)

            # Update equity curve
            self._update_equity_curve(candle.timestamp)

            # Log progress periodically
            if i % 1000 == 0:
                logger.debug(f"Processed {i}/{len(candles)} candles for {symbol}")

    async def _execute_signal(
        self, signal: TradeSignal, candle: OHLCV, market_regime: MarketRegime
    ) -> None:
        """Execute a trading signal with realistic costs."""
        # Calculate slippage and fees
        slippage_cost = signal.price * signal.quantity * (self.slippage_bps / 10000)
        fee_cost = signal.price * signal.quantity * (self.fee_bps / 10000)

        if signal.action == "enter":
            # Create new trade
            trade = BacktestTrade(
                trade_id=f"{signal.symbol}_{signal.timestamp.timestamp()}",
                symbol=signal.symbol,
                strategy=signal.strategy.value,
                side=signal.side.value,
                entry_time=signal.timestamp,
                entry_price=signal.price,
                quantity=signal.quantity,
                entry_reason=signal.reason,
                fees=fee_cost,
                slippage=slippage_cost,
            )

            self.open_positions[signal.symbol] = trade
            self.total_fees += fee_cost
            self.total_slippage += slippage_cost

            logger.debug(
                f"Opened {signal.side.value} position in {signal.symbol} at {signal.price}"
            )

        elif signal.action in ["exit", "stop_loss", "take_profit"]:
            # Close existing position
            if signal.symbol in self.open_positions:
                trade = self.open_positions[signal.symbol]

                # Update exit details
                trade.exit_time = signal.timestamp
                trade.exit_price = signal.price
                trade.exit_reason = signal.reason

                # Calculate P&L
                if trade.side == "long":
                    trade.pnl = (signal.price - trade.entry_price) * trade.quantity
                else:
                    trade.pnl = (trade.entry_price - signal.price) * trade.quantity

                trade.pnl_pct = (
                    trade.pnl / trade.notional_value
                    if trade.notional_value > 0
                    else Decimal("0")
                )

                # Add exit costs
                trade.fees += fee_cost
                trade.slippage += slippage_cost

                # Calculate hold duration
                if trade.exit_time:
                    duration = trade.exit_time - trade.entry_time
                    trade.hold_duration_hours = Decimal(
                        str(duration.total_seconds() / 3600)
                    )

                # Update equity
                self.current_equity += trade.pnl - fee_cost - slippage_cost
                self.total_fees += fee_cost
                self.total_slippage += slippage_cost

                # Execute through risk manager
                self.risk_manager.execute_signal(signal)

                # Move to completed trades
                self.trades.append(trade)
                del self.open_positions[signal.symbol]

                logger.debug(
                    f"Closed {trade.side} position in {signal.symbol} with P&L: {trade.pnl}"
                )

    async def _load_funding_rates(
        self, start_date: datetime, end_date: datetime
    ) -> dict[str, list[FundingRate]]:
        """Load funding rate data for cost calculations."""
        try:
            funding_rates = await self.historical_data_provider.get_funding_rates(
                self.symbols, start_date, end_date
            )

            # Group by symbol
            rates_by_symbol = defaultdict(list)
            for rate in funding_rates:
                rates_by_symbol[rate.symbol].append(rate)

            return dict(rates_by_symbol)

        except Exception as e:
            logger.warning(f"Failed to load funding rates: {e}")
            return {}

    def _apply_funding_cost(self, symbol: str, funding_rate: FundingRate) -> None:
        """Apply funding cost to open positions."""
        if symbol in self.open_positions:
            trade = self.open_positions[symbol]

            # Calculate funding cost (8 hours interval typical)
            funding_cost = trade.notional_value * funding_rate.rate

            # Short positions pay/receive opposite funding
            if trade.side == "short":
                funding_cost = -funding_cost

            trade.funding_cost += funding_cost
            self.total_funding += abs(funding_cost)
            self.current_equity -= funding_cost

    def _update_equity_curve(self, timestamp: datetime) -> None:
        """Update equity curve and drawdown tracking."""
        # Add unrealized P&L from open positions
        unrealized_pnl = Decimal("0")
        for trade in self.open_positions.values():
            if hasattr(trade, "current_price"):
                if trade.side == "long":
                    unrealized_pnl += (
                        trade.current_price - trade.entry_price
                    ) * trade.quantity
                else:
                    unrealized_pnl += (
                        trade.entry_price - trade.current_price
                    ) * trade.quantity

        total_equity = self.current_equity + unrealized_pnl
        self.equity_curve.append((timestamp, total_equity))

        # Update peak and drawdown
        if total_equity > self.peak_equity:
            self.peak_equity = total_equity
        else:
            current_drawdown = (self.peak_equity - total_equity) / self.peak_equity
            if current_drawdown > self.max_drawdown:
                self.max_drawdown = current_drawdown

    def calculate_metrics(
        self, trades: list[BacktestTrade], equity_curve: list[tuple[datetime, Decimal]]
    ) -> BacktestMetrics:
        """
        Calculate comprehensive backtest performance metrics.

        Args:
            trades: List of completed trades
            equity_curve: Time series of equity values

        Returns:
            BacktestMetrics with all performance statistics
        """
        if not trades or not equity_curve:
            # Return empty metrics with provided dates
            return BacktestMetrics(
                start_date=datetime(2023, 1, 1)
                if not equity_curve
                else equity_curve[0][0],
                end_date=datetime(2023, 1, 1)
                if not equity_curve
                else equity_curve[-1][0],
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=Decimal("0"),
                total_pnl=Decimal("0"),
                total_return_pct=Decimal("0"),
                max_drawdown_pct=Decimal("0"),
                max_runup_pct=Decimal("0"),
                avg_trade_duration_hours=Decimal("0"),
                avg_winning_trade_pct=Decimal("0"),
                avg_losing_trade_pct=Decimal("0"),
                profit_factor=Decimal("0"),
                total_fees=Decimal("0"),
                total_funding_cost=Decimal("0"),
                total_slippage=Decimal("0"),
            )

        start_date = equity_curve[0][0]
        end_date = equity_curve[-1][0]

        # Basic trade statistics
        closed_trades = [t for t in trades if t.is_closed and t.pnl is not None]
        total_trades = len(closed_trades)
        winning_trades = len([t for t in closed_trades if t.pnl > 0])
        losing_trades = len([t for t in closed_trades if t.pnl <= 0])

        win_rate = (
            Decimal(winning_trades) / Decimal(total_trades)
            if total_trades > 0
            else Decimal("0")
        )

        # P&L calculations
        total_pnl = sum(t.pnl for t in closed_trades)
        total_return_pct = (total_pnl / self.initial_equity) * 100

        # Trade duration
        durations = [
            t.hold_duration_hours for t in closed_trades if t.hold_duration_hours
        ]
        avg_trade_duration_hours = (
            sum(durations) / len(durations) if durations else Decimal("0")
        )

        # Win/Loss averages
        winning_pnl = [t.pnl_pct for t in closed_trades if t.pnl > 0 and t.pnl_pct]
        losing_pnl = [t.pnl_pct for t in closed_trades if t.pnl <= 0 and t.pnl_pct]

        avg_winning_trade_pct = (
            sum(winning_pnl) / len(winning_pnl) if winning_pnl else Decimal("0")
        )
        avg_losing_trade_pct = (
            sum(losing_pnl) / len(losing_pnl) if losing_pnl else Decimal("0")
        )

        # Profit factor
        gross_profit = sum(t.pnl for t in closed_trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in closed_trades if t.pnl <= 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else Decimal("0")

        # Risk metrics
        returns = self._calculate_returns(equity_curve)
        sharpe_ratio = self._calculate_sharpe_ratio(returns)
        sortino_ratio = self._calculate_sortino_ratio(returns)

        # Drawdown analysis
        max_drawdown_pct = self.max_drawdown * 100
        max_runup_pct = self._calculate_max_runup(equity_curve)

        # Calmar ratio
        calmar_ratio = None
        if max_drawdown_pct > 0:
            annual_return = total_return_pct * (365.25 / (end_date - start_date).days)
            calmar_ratio = annual_return / max_drawdown_pct

        return BacktestMetrics(
            start_date=start_date,
            end_date=end_date,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            total_return_pct=total_return_pct,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown_pct=max_drawdown_pct,
            max_runup_pct=max_runup_pct,
            avg_trade_duration_hours=avg_trade_duration_hours,
            avg_winning_trade_pct=avg_winning_trade_pct,
            avg_losing_trade_pct=avg_losing_trade_pct,
            profit_factor=profit_factor,
            calmar_ratio=calmar_ratio,
            total_fees=self.total_fees,
            total_funding_cost=self.total_funding,
            total_slippage=self.total_slippage,
        )

    def _calculate_returns(
        self, equity_curve: list[tuple[datetime, Decimal]]
    ) -> list[Decimal]:
        """Calculate period returns from equity curve."""
        returns = []
        for i in range(1, len(equity_curve)):
            prev_equity = equity_curve[i - 1][1]
            curr_equity = equity_curve[i][1]
            if prev_equity > 0:
                ret = (curr_equity - prev_equity) / prev_equity
                returns.append(ret)
        return returns

    def _calculate_sharpe_ratio(self, returns: list[Decimal]) -> Optional[Decimal]:
        """Calculate Sharpe ratio from returns."""
        if len(returns) < 2:
            return None

        mean_return = sum(returns) / len(returns)

        # Calculate standard deviation
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = variance ** Decimal("0.5")

        if std_dev == 0:
            return None

        # Annualize (assuming minute data)
        annual_mean = mean_return * Decimal("525600")  # minutes in year
        annual_std = std_dev * (Decimal("525600") ** Decimal("0.5"))

        return annual_mean / annual_std

    def _calculate_sortino_ratio(self, returns: list[Decimal]) -> Optional[Decimal]:
        """Calculate Sortino ratio from returns."""
        if len(returns) < 2:
            return None

        mean_return = sum(returns) / len(returns)
        downside_returns = [r for r in returns if r < 0]

        if not downside_returns:
            return None

        downside_variance = sum(r**2 for r in downside_returns) / len(downside_returns)
        downside_std = downside_variance ** Decimal("0.5")

        if downside_std == 0:
            return None

        # Annualize
        annual_mean = mean_return * Decimal("525600")
        annual_downside_std = downside_std * (Decimal("525600") ** Decimal("0.5"))

        return annual_mean / annual_downside_std

    def _calculate_max_runup(
        self, equity_curve: list[tuple[datetime, Decimal]]
    ) -> Decimal:
        """Calculate maximum runup from equity curve."""
        max_runup = Decimal("0")
        trough_equity = equity_curve[0][1] if equity_curve else self.initial_equity

        for _, equity in equity_curve:
            if equity < trough_equity:
                trough_equity = equity
            else:
                runup = (equity - trough_equity) / trough_equity
                if runup > max_runup:
                    max_runup = runup

        return max_runup * 100  # Return as percentage

    def generate_report(self, results: BacktestMetrics) -> dict[str, Any]:
        """
        Generate comprehensive backtest report.

        Args:
            results: BacktestMetrics from simulation

        Returns:
            Dictionary containing formatted report data
        """
        return {
            "summary": {
                "start_date": results.start_date.isoformat(),
                "end_date": results.end_date.isoformat(),
                "total_return_pct": float(results.total_return_pct),
                "total_trades": results.total_trades,
                "win_rate": float(results.win_rate * 100),  # Convert to percentage
                "sharpe_ratio": float(results.sharpe_ratio)
                if results.sharpe_ratio
                else None,
                "max_drawdown_pct": float(results.max_drawdown_pct),
            },
            "performance": {
                "total_pnl": float(results.total_pnl),
                "gross_pnl": float(results.gross_pnl),
                "profit_factor": float(results.profit_factor),
                "expectancy": float(results.expectancy),
                "calmar_ratio": float(results.calmar_ratio)
                if results.calmar_ratio
                else None,
                "sortino_ratio": float(results.sortino_ratio)
                if results.sortino_ratio
                else None,
            },
            "trades": {
                "winning_trades": results.winning_trades,
                "losing_trades": results.losing_trades,
                "avg_winning_trade_pct": float(results.avg_winning_trade_pct),
                "avg_losing_trade_pct": float(results.avg_losing_trade_pct),
                "avg_trade_duration_hours": float(results.avg_trade_duration_hours),
            },
            "costs": {
                "total_fees": float(results.total_fees),
                "total_funding_cost": float(results.total_funding_cost),
                "total_slippage": float(results.total_slippage),
            },
            "targets": {
                "sharpe_target": 1.3,
                "drawdown_target": 8.0,
                "sharpe_achieved": (results.sharpe_ratio or Decimal("0"))
                > Decimal("1.3"),
                "drawdown_achieved": results.max_drawdown_pct < Decimal("8.0"),
            },
        }

    async def walk_forward_test(
        self,
        start_date: datetime,
        end_date: datetime,
        train_ratio: float = 0.7,
        step_size_days: int = 30,
    ) -> list[BacktestMetrics]:
        """
        Perform walk-forward analysis with rolling train/test periods.

        Args:
            start_date: Overall start date
            end_date: Overall end date
            train_ratio: Ratio of data used for training (0.7 for 70%)
            step_size_days: Days to advance for each test period

        Returns:
            List of BacktestMetrics for each test period
        """
        logger.info("Starting walk-forward analysis")

        results = []
        total_days = (end_date - start_date).days
        train_days = int(total_days * train_ratio)

        current_start = start_date

        while current_start + timedelta(days=train_days) < end_date:
            train_end = current_start + timedelta(days=train_days)
            test_end = min(train_end + timedelta(days=step_size_days), end_date)

            logger.info(
                f"Walk-forward period: train={current_start} to {train_end}, test={train_end} to {test_end}"
            )

            # Reset state for this period
            self._reset_state()

            # Run backtest for this period
            metrics = await self.simulate_strategy(
                self.config, current_start, test_end, train_end_date=train_end
            )

            results.append(metrics)

            # Advance to next period
            current_start += timedelta(days=step_size_days)

        logger.info(f"Completed walk-forward analysis with {len(results)} periods")
        return results

    def _reset_state(self) -> None:
        """Reset backtest state for new simulation."""
        self.current_equity = self.initial_equity
        self.trades = []
        self.equity_curve = []
        self.open_positions = {}
        self.total_fees = Decimal("0")
        self.total_slippage = Decimal("0")
        self.total_funding = Decimal("0")
        self.peak_equity = self.initial_equity
        self.max_drawdown = Decimal("0")

        # Reset risk manager
        self.risk_manager = RiskManager(
            base_equity=self.initial_equity, cooldown_hours=self.cooldown_hours
        )
