#!/usr/bin/env python3
"""
Demo script showing how to use the backtesting engine.

This script demonstrates the complete backtesting workflow including:
- Loading historical data 
- Running strategy simulation
- Generating performance reports
- Walk-forward testing
"""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from src.strategy.backtest import BacktestEngine
from src.providers.gemini.historical import GeminiHistoricalDataProvider

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Run backtesting demo."""
    print("=" * 60)
    print("NEMO Backtesting Engine Demo")
    print("=" * 60)
    
    # Configuration
    config = {
        "SYMBOLS": ["BTC-USD-PERP", "ETH-USD-PERP"],
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
    
    provider_config = {
        "REST_URL": "https://api.gemini.com",
        "HISTORICAL_URL": "https://api.gemini.com/v1/candles"
    }
    
    # Create components
    historical_provider = GeminiHistoricalDataProvider(provider_config)
    backtest_engine = BacktestEngine(historical_provider, config)
    
    print(f"🚀 Initializing backtest engine...")
    print(f"   Initial Equity: ${config['INITIAL_EQUITY']:,}")
    print(f"   Symbols: {', '.join(config['SYMBOLS'])}")
    print(f"   Max Leverage: {config['MAX_LEVERAGE']}x")
    print()
    
    # Test dates (using mock data for demo)
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2023, 1, 2)  # 1 day for demo
    
    try:
        print("📊 Running strategy simulation...")
        print(f"   Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        print(f"   Strategy: Volatility Harvest (Mean Reversion + Momentum)")
        print()
        
        # Run simulation
        metrics = await backtest_engine.simulate_strategy(
            config, start_date, end_date
        )
        
        # Generate report
        report = backtest_engine.generate_report(metrics)
        
        # Display results
        print("📈 BACKTEST RESULTS")
        print("=" * 40)
        
        summary = report["summary"]
        print(f"Total Return:      {summary['total_return_pct']:+.2f}%")
        print(f"Total Trades:      {summary['total_trades']}")
        print(f"Win Rate:          {summary['win_rate']:.1f}%")
        print(f"Sharpe Ratio:      {summary['sharpe_ratio'] or 'N/A'}")
        print(f"Max Drawdown:      {summary['max_drawdown_pct']:.2f}%")
        print()
        
        performance = report["performance"]
        print("💰 PERFORMANCE METRICS")
        print("=" * 40)
        print(f"Total P&L:         ${performance['total_pnl']:,.2f}")
        print(f"Gross P&L:         ${performance['gross_pnl']:,.2f}")
        print(f"Profit Factor:     {performance['profit_factor']:.2f}")
        print(f"Expectancy:        ${performance['expectancy']:,.2f}")
        print()
        
        trades = report["trades"]
        print("📊 TRADE ANALYSIS")
        print("=" * 40)
        print(f"Winning Trades:    {trades['winning_trades']}")
        print(f"Losing Trades:     {trades['losing_trades']}")
        print(f"Avg Win:           {trades['avg_winning_trade_pct']:+.2f}%")
        print(f"Avg Loss:          {trades['avg_losing_trade_pct']:+.2f}%")
        print(f"Avg Duration:      {trades['avg_trade_duration_hours']:.1f} hours")
        print()
        
        costs = report["costs"]
        print("💸 COST BREAKDOWN")
        print("=" * 40)
        print(f"Trading Fees:      ${costs['total_fees']:,.2f}")
        print(f"Slippage:          ${costs['total_slippage']:,.2f}")
        print(f"Funding Costs:     ${costs['total_funding_cost']:,.2f}")
        print()
        
        targets = report["targets"]
        print("🎯 TARGET ANALYSIS")
        print("=" * 40)
        print(f"Sharpe Target:     {targets['sharpe_target']} ({'✅' if targets['sharpe_achieved'] else '❌'})")
        print(f"Drawdown Target:   <{targets['drawdown_target']}% ({'✅' if targets['drawdown_achieved'] else '❌'})")
        print()
        
        if targets['sharpe_achieved'] and targets['drawdown_achieved']:
            print("🎉 SUCCESS: Strategy meets performance targets!")
        else:
            print("⚠️  WARNING: Strategy does not meet performance targets")
            print("    Consider parameter optimization or strategy refinement")
        print()
        
        # Demonstrate walk-forward testing
        print("🔄 WALK-FORWARD ANALYSIS")
        print("=" * 40)
        print("Running walk-forward test with 70/30 split...")
        
        # Use shorter period for demo
        wf_start = datetime(2023, 1, 1)
        wf_end = datetime(2023, 1, 3)  # 2 days for demo
        
        wf_results = await backtest_engine.walk_forward_test(
            wf_start, wf_end, train_ratio=0.7, step_size_days=1
        )
        
        if wf_results:
            print(f"Walk-forward periods: {len(wf_results)}")
            
            avg_return = sum(r.total_return_pct for r in wf_results) / len(wf_results)
            avg_sharpe = sum(r.sharpe_ratio or Decimal('0') for r in wf_results) / len(wf_results)
            max_dd = max(r.max_drawdown_pct for r in wf_results)
            
            print(f"Average Return:    {avg_return:+.2f}%")
            print(f"Average Sharpe:    {avg_sharpe:.2f}")
            print(f"Worst Drawdown:    {max_dd:.2f}%")
            
            consistency = sum(1 for r in wf_results if r.total_return_pct > 0) / len(wf_results)
            print(f"Consistency:       {consistency:.1%} positive periods")
        else:
            print("No walk-forward results (insufficient data)")
        print()
        
        print("✅ Backtesting demo completed successfully!")
        print()
        print("💡 NEXT STEPS:")
        print("   1. Integrate with real historical data provider")
        print("   2. Optimize strategy parameters using walk-forward results")
        print("   3. Implement out-of-sample testing for 2025 data")
        print("   4. Add Monte Carlo simulation for robustness testing")
        print("   5. Deploy strategy with paper trading validation")
        
    except Exception as e:
        logger.error(f"Backtesting failed: {e}")
        print(f"❌ Error: {e}")
    
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())