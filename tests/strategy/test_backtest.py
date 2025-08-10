"""
Tests for the backtesting engine and related components.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.common.models import (
    OHLCV,
    BacktestMetrics,
    BacktestTrade,
    FundingRate,
    MarketRegime,
    TradeTick,
)
from src.providers.gemini.historical import GeminiHistoricalDataProvider
from src.strategy.backtest import BacktestEngine
from src.strategy.llm_gate import HeuristicLLMProxy


@pytest.fixture
def mock_historical_provider():
    """Create a mock historical data provider."""
    provider = AsyncMock(spec=GeminiHistoricalDataProvider)

    # Mock OHLCV data
    start_date = datetime(2023, 1, 1)
    candles = []

    for i in range(100):  # 100 minutes of data
        timestamp = start_date + timedelta(minutes=i)
        price = Decimal("50000") + Decimal(str(i * 10))  # Trending up

        candle = OHLCV(
            symbol="BTC-USD-PERP",
            timestamp=timestamp,
            open_price=price,
            high_price=price + Decimal("50"),
            low_price=price - Decimal("50"),
            close_price=price + Decimal("25"),
            volume=Decimal("1000"),
            trade_count=100,
        )
        candles.append(candle)

    provider.get_candles.return_value = candles
    provider.get_funding_rates.return_value = []
    provider.get_trade_data.return_value = []
    provider.connect.return_value = None
    provider.disconnect.return_value = None

    return provider


@pytest.fixture
def backtest_config():
    """Create backtest configuration."""
    return {
        "SYMBOLS": ["BTC-USD-PERP"],
        "INITIAL_EQUITY": 100000,
        "SLIPPAGE_BPS": 5,
        "FEE_BPS": 8,
        "PRICE_DEV": 0.01,
        "VOL_MULT": 3,
        "LLM_CONF": 0.65,
        "MAX_LEVERAGE": 3,
        "STOP_LOSS_PCT": 0.01,
        "COOLDOWN_HR": 6,
    }


@pytest.fixture
def backtest_engine(mock_historical_provider, backtest_config):
    """Create backtest engine with mocked dependencies."""
    return BacktestEngine(mock_historical_provider, backtest_config)


class TestOHLCVModel:
    """Test OHLCV data model."""

    def test_ohlcv_creation(self):
        """Test basic OHLCV creation."""
        candle = OHLCV(
            symbol="BTC-USD",
            timestamp=datetime.now(),
            open_price=Decimal("50000"),
            high_price=Decimal("50100"),
            low_price=Decimal("49900"),
            close_price=Decimal("50050"),
            volume=Decimal("1000"),
        )

        assert candle.symbol == "BTC-USD"
        assert candle.open_price == Decimal("50000")
        assert candle.volume == Decimal("1000")

    def test_typical_price_calculation(self):
        """Test typical price computation."""
        candle = OHLCV(
            symbol="BTC-USD",
            timestamp=datetime.now(),
            open_price=Decimal("50000"),
            high_price=Decimal("50100"),
            low_price=Decimal("49900"),
            close_price=Decimal("50000"),
            volume=Decimal("1000"),
        )

        expected_typical = (Decimal("50100") + Decimal("49900") + Decimal("50000")) / 3
        assert candle.typical_price == expected_typical

    def test_price_range_calculation(self):
        """Test price range calculation."""
        candle = OHLCV(
            symbol="BTC-USD",
            timestamp=datetime.now(),
            open_price=Decimal("50000"),
            high_price=Decimal("50100"),
            low_price=Decimal("49900"),
            close_price=Decimal("50000"),
            volume=Decimal("1000"),
        )

        assert candle.price_range == Decimal("200")  # 50100 - 49900

    def test_body_size_calculation(self):
        """Test candle body size calculation."""
        candle = OHLCV(
            symbol="BTC-USD",
            timestamp=datetime.now(),
            open_price=Decimal("50000"),
            high_price=Decimal("50100"),
            low_price=Decimal("49900"),
            close_price=Decimal("50050"),
            volume=Decimal("1000"),
        )

        assert candle.body_size == Decimal("50")  # |50050 - 50000|


class TestFundingRateModel:
    """Test FundingRate data model."""

    def test_funding_rate_creation(self):
        """Test basic funding rate creation."""
        rate = FundingRate(
            symbol="BTC-USD-PERP", timestamp=datetime.now(), rate=Decimal("0.0001")
        )

        assert rate.symbol == "BTC-USD-PERP"
        assert rate.rate == Decimal("0.0001")

    def test_rate_bps_calculation(self):
        """Test basis points conversion."""
        rate = FundingRate(
            symbol="BTC-USD-PERP", timestamp=datetime.now(), rate=Decimal("0.0001")
        )

        assert rate.rate_bps == Decimal("1")  # 0.0001 * 10000 = 1 bps


class TestBacktestTradeModel:
    """Test BacktestTrade data model."""

    def test_backtest_trade_creation(self):
        """Test basic backtest trade creation."""
        trade = BacktestTrade(
            trade_id="test_1",
            symbol="BTC-USD",
            strategy="mean_reversion",
            side="long",
            entry_time=datetime.now(),
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_reason="VWAP deviation",
        )

        assert trade.trade_id == "test_1"
        assert trade.side == "long"
        assert not trade.is_closed

    def test_trade_closure(self):
        """Test trade closure detection."""
        trade = BacktestTrade(
            trade_id="test_1",
            symbol="BTC-USD",
            strategy="mean_reversion",
            side="long",
            entry_time=datetime.now(),
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_reason="VWAP deviation",
            exit_time=datetime.now(),
            exit_price=Decimal("50500"),
        )

        assert trade.is_closed

    def test_notional_value_calculation(self):
        """Test notional value calculation."""
        trade = BacktestTrade(
            trade_id="test_1",
            symbol="BTC-USD",
            strategy="mean_reversion",
            side="long",
            entry_time=datetime.now(),
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_reason="VWAP deviation",
        )

        assert trade.notional_value == Decimal("5000")  # 50000 * 0.1


class TestBacktestMetricsModel:
    """Test BacktestMetrics data model."""

    def test_metrics_creation(self):
        """Test metrics creation with basic data."""
        metrics = BacktestMetrics(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            win_rate=Decimal("0.6"),
            total_pnl=Decimal("5000"),
            total_return_pct=Decimal("5"),
            max_drawdown_pct=Decimal("3"),
            max_runup_pct=Decimal("8"),
            avg_trade_duration_hours=Decimal("24"),
            avg_winning_trade_pct=Decimal("2"),
            avg_losing_trade_pct=Decimal("-1.5"),
            profit_factor=Decimal("1.5"),
            total_fees=Decimal("500"),
            total_funding_cost=Decimal("200"),
            total_slippage=Decimal("100"),
        )

        assert metrics.total_trades == 100
        assert metrics.win_rate == Decimal("0.6")

    def test_gross_pnl_calculation(self):
        """Test gross P&L calculation."""
        metrics = BacktestMetrics(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            win_rate=Decimal("0.6"),
            total_pnl=Decimal("5000"),
            total_return_pct=Decimal("5"),
            max_drawdown_pct=Decimal("3"),
            max_runup_pct=Decimal("8"),
            avg_trade_duration_hours=Decimal("24"),
            avg_winning_trade_pct=Decimal("2"),
            avg_losing_trade_pct=Decimal("-1.5"),
            profit_factor=Decimal("1.5"),
            total_fees=Decimal("500"),
            total_funding_cost=Decimal("200"),
            total_slippage=Decimal("100"),
        )

        expected_gross = (
            Decimal("5000") + Decimal("500") + Decimal("200") + Decimal("100")
        )
        assert metrics.gross_pnl == expected_gross

    def test_expectancy_calculation(self):
        """Test expectancy per trade calculation."""
        metrics = BacktestMetrics(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            win_rate=Decimal("0.6"),
            total_pnl=Decimal("5000"),
            total_return_pct=Decimal("5"),
            max_drawdown_pct=Decimal("3"),
            max_runup_pct=Decimal("8"),
            avg_trade_duration_hours=Decimal("24"),
            avg_winning_trade_pct=Decimal("2"),
            avg_losing_trade_pct=Decimal("-1.5"),
            profit_factor=Decimal("1.5"),
            total_fees=Decimal("500"),
            total_funding_cost=Decimal("200"),
            total_slippage=Decimal("100"),
        )

        assert metrics.expectancy == Decimal("50")  # 5000 / 100


class TestMarketRegimeModel:
    """Test MarketRegime data model."""

    def test_market_regime_creation(self):
        """Test market regime creation."""
        regime = MarketRegime(
            timestamp=datetime.now(),
            symbol="BTC-USD",
            regime="liquidation_noise",
            confidence=Decimal("0.8"),
            indicators={"volume_spike": True},
            headline_present=True,
            volume_anomaly=True,
            price_volatility=Decimal("0.05"),
        )

        assert regime.regime == "liquidation_noise"
        assert regime.confidence == Decimal("0.8")
        assert regime.headline_present


class TestHeuristicLLMProxy:
    """Test heuristic LLM proxy implementation."""

    @pytest.fixture
    def llm_proxy(self):
        """Create LLM proxy instance."""
        return HeuristicLLMProxy(
            liquidation_volume_threshold=Decimal("500000"),
            volatility_spike_threshold=Decimal("0.05"),
            confidence_threshold=Decimal("0.65"),
        )

    def test_market_data_addition(self, llm_proxy):
        """Test adding market data to proxy."""
        trade = TradeTick(
            symbol="BTC-USD",
            price=Decimal("50000"),
            size=Decimal("1"),
            timestamp=datetime.now(),
            side="buy",
        )

        llm_proxy.add_market_data(trade)
        assert len(llm_proxy._recent_trades) == 1

    def test_market_regime_classification_neutral(self, llm_proxy):
        """Test neutral market regime classification."""
        # Add some baseline trades
        for i in range(10):
            trade = TradeTick(
                symbol="BTC-USD",
                price=Decimal("50000"),
                size=Decimal("100"),
                timestamp=datetime.now() - timedelta(minutes=i),
                side="buy",
            )
            llm_proxy.add_market_data(trade)

        regime = llm_proxy.classify_market_regime(
            datetime.now(), "BTC-USD", Decimal("50000")
        )

        assert regime.regime == "neutral"
        assert regime.symbol == "BTC-USD"

    def test_market_regime_liquidation_noise(self, llm_proxy):
        """Test liquidation noise regime detection."""
        regime = llm_proxy.classify_market_regime(
            datetime.now(),
            "BTC-USD",
            Decimal("50000"),
            liquidation_sum=Decimal("1000000"),  # Above threshold
        )

        assert regime.regime == "liquidation_noise"
        assert regime.confidence > Decimal("0.65")

    def test_should_trade_decision(self, llm_proxy):
        """Test trading decision logic."""
        # Neutral regime should allow trading
        neutral_regime = MarketRegime(
            timestamp=datetime.now(),
            symbol="BTC-USD",
            regime="neutral",
            confidence=Decimal("0.7"),
            indicators={},
        )

        assert llm_proxy.should_trade(neutral_regime, "mean_reversion")

        # High-confidence liquidation noise should prevent trading
        liquidation_regime = MarketRegime(
            timestamp=datetime.now(),
            symbol="BTC-USD",
            regime="liquidation_noise",
            confidence=Decimal("0.8"),
            indicators={},
        )

        assert not llm_proxy.should_trade(liquidation_regime, "mean_reversion")


class TestGeminiHistoricalDataProvider:
    """Test Gemini historical data provider."""

    @pytest.fixture
    def provider(self):
        """Create provider instance."""
        config = {
            "REST_URL": "https://api.gemini.com",
            "HISTORICAL_URL": "https://api.gemini.com/v1/candles",
        }
        return GeminiHistoricalDataProvider(config)

    @pytest.mark.asyncio
    async def test_provider_connection(self, provider):
        """Test provider connection."""
        await provider.connect()
        assert provider.session is not None

        await provider.disconnect()
        assert provider.session is None

    @pytest.mark.asyncio
    async def test_get_candles_mock_data(self, provider):
        """Test getting historical candles (mock data)."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 1, 1, 0)  # 1 hour of data

        candles = await provider.get_candles(["BTC-GUSD-PERP"], start_date, end_date)

        assert len(candles) > 0
        assert all(isinstance(c, OHLCV) for c in candles)
        assert all(
            c.timestamp >= start_date and c.timestamp <= end_date for c in candles
        )

    @pytest.mark.asyncio
    async def test_get_funding_rates_mock_data(self, provider):
        """Test getting funding rates (mock data)."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 2)  # 1 day

        rates = await provider.get_funding_rates(
            ["BTC-GUSD-PERP"], start_date, end_date
        )

        assert len(rates) > 0
        assert all(isinstance(r, FundingRate) for r in rates)

    def test_symbol_format_conversion(self, provider):
        """Test symbol format conversion."""
        assert provider._convert_symbol_format("BTC-GUSD-PERP") == "btcgusd"
        assert provider._convert_symbol_format("ETH-USD-PERP") == "ethusd"


class TestBacktestEngine:
    """Test backtesting engine."""

    @pytest.mark.asyncio
    async def test_load_historical_data(self, backtest_engine):
        """Test loading historical data."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 1, 2, 0)  # 2 hours

        data = await backtest_engine.load_historical_data(
            ["BTC-USD-PERP"], start_date, end_date
        )

        assert "BTC-USD-PERP" in data
        assert len(data["BTC-USD-PERP"]) > 0

    @pytest.mark.asyncio
    async def test_simulate_strategy(self, backtest_engine):
        """Test strategy simulation."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 1, 2, 0)  # 2 hours

        metrics = await backtest_engine.simulate_strategy(
            backtest_engine.config, start_date, end_date
        )

        assert isinstance(metrics, BacktestMetrics)
        assert metrics.start_date == start_date

    def test_calculate_metrics_empty_data(self, backtest_engine):
        """Test metrics calculation with empty data."""
        metrics = backtest_engine.calculate_metrics([], [])

        assert metrics.total_trades == 0
        assert metrics.win_rate == Decimal("0")
        assert metrics.total_pnl == Decimal("0")

    def test_calculate_metrics_with_trades(self, backtest_engine):
        """Test metrics calculation with trade data."""
        trades = [
            BacktestTrade(
                trade_id="1",
                symbol="BTC-USD",
                strategy="mean_reversion",
                side="long",
                entry_time=datetime(2023, 1, 1),
                entry_price=Decimal("50000"),
                quantity=Decimal("0.1"),
                entry_reason="test",
                exit_time=datetime(2023, 1, 1, 1, 0),
                exit_price=Decimal("50500"),
                pnl=Decimal("50"),
                pnl_pct=Decimal("0.001"),
                hold_duration_hours=Decimal("1"),
            ),
            BacktestTrade(
                trade_id="2",
                symbol="BTC-USD",
                strategy="mean_reversion",
                side="short",
                entry_time=datetime(2023, 1, 1, 2, 0),
                entry_price=Decimal("50500"),
                quantity=Decimal("0.1"),
                entry_reason="test",
                exit_time=datetime(2023, 1, 1, 3, 0),
                exit_price=Decimal("50000"),
                pnl=Decimal("50"),
                pnl_pct=Decimal("0.001"),
                hold_duration_hours=Decimal("1"),
            ),
        ]

        equity_curve = [
            (datetime(2023, 1, 1), Decimal("100000")),
            (datetime(2023, 1, 1, 4, 0), Decimal("100100")),
        ]

        metrics = backtest_engine.calculate_metrics(trades, equity_curve)

        assert metrics.total_trades == 2
        assert metrics.winning_trades == 2
        assert metrics.win_rate == Decimal("1")
        assert metrics.total_pnl == Decimal("100")
        assert metrics.avg_trade_duration_hours == Decimal("1")

    def test_generate_report(self, backtest_engine):
        """Test report generation."""
        metrics = BacktestMetrics(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            win_rate=Decimal("0.6"),
            total_pnl=Decimal("5000"),
            total_return_pct=Decimal("5"),
            max_drawdown_pct=Decimal("3"),
            max_runup_pct=Decimal("8"),
            avg_trade_duration_hours=Decimal("24"),
            avg_winning_trade_pct=Decimal("2"),
            avg_losing_trade_pct=Decimal("-1.5"),
            profit_factor=Decimal("1.5"),
            total_fees=Decimal("500"),
            total_funding_cost=Decimal("200"),
            total_slippage=Decimal("100"),
        )

        report = backtest_engine.generate_report(metrics)

        assert "summary" in report
        assert "performance" in report
        assert "trades" in report
        assert "costs" in report
        assert "targets" in report

        assert report["summary"]["total_trades"] == 100
        assert report["targets"]["sharpe_target"] == 1.3
        assert report["targets"]["drawdown_target"] == 8.0

    def test_reset_state(self, backtest_engine):
        """Test state reset functionality."""
        # Modify state
        backtest_engine.current_equity = Decimal("50000")
        backtest_engine.trades = [Mock()]
        backtest_engine.equity_curve = [(datetime.now(), Decimal("50000"))]

        # Reset
        backtest_engine._reset_state()

        assert backtest_engine.current_equity == backtest_engine.initial_equity
        assert len(backtest_engine.trades) == 0
        assert len(backtest_engine.equity_curve) == 0
        assert len(backtest_engine.open_positions) == 0


@pytest.mark.asyncio
async def test_integration_backtest_workflow(backtest_engine):
    """Test complete backtesting workflow integration."""
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2023, 1, 1, 1, 0)  # 1 hour

    # Run simulation
    metrics = await backtest_engine.simulate_strategy(
        backtest_engine.config, start_date, end_date
    )

    # Generate report
    report = backtest_engine.generate_report(metrics)

    # Verify workflow completed
    assert isinstance(metrics, BacktestMetrics)
    assert isinstance(report, dict)
    assert "summary" in report

    # Check if targets are evaluated
    assert "targets" in report
    assert "sharpe_achieved" in report["targets"]
    assert "drawdown_achieved" in report["targets"]
