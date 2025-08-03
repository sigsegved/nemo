# Nemo Volatility Harvest Bot

A sophisticated algorithmic trading bot that implements volatility harvesting strategies using Volume Weighted Average Price (VWAP) calculations, market microstructure analysis, and optional LLM-enhanced decision making.

## Overview

Nemo is designed to capitalize on short-term volatility opportunities in both cryptocurrency and equity markets by:

- **VWAP-based Signal Generation**: Analyzing price deviations from volume-weighted average prices to identify entry and exit opportunities
- **Multi-Provider Support**: Supporting both Alpaca (stocks/crypto) and Gemini (crypto) trading platforms
- **Advanced Risk Management**: Implementing portfolio-level risk controls, position sizing, and drawdown protection
- **LLM Integration**: Optional integration with Large Language Models for enhanced market analysis and decision support
- **Comprehensive Backtesting**: Full historical simulation capabilities for strategy development and validation

## Features

### Core Trading Engine
- Real-time market data processing
- VWAP calculation and deviation analysis
- Multi-timeframe strategy execution
- Advanced trigger mechanisms

### Provider Integration
- **Alpaca Markets**: Stock and cryptocurrency trading
- **Gemini Exchange**: Cryptocurrency trading
- Unified API abstraction layer
- Automatic failover and redundancy

### Risk Management
- Volatility-adjusted position sizing
- Portfolio-level risk limits
- Real-time drawdown monitoring
- Stop-loss and take-profit automation

### Strategy Components
- VWAP-based volatility harvesting
- Market microstructure analysis
- Multi-factor signal combination
- Confidence-weighted decision making

## Architecture

```
/src
├── common/                    # Shared components and abstractions
│   ├── models.py             # Pydantic data models
│   ├── provider_base.py      # Abstract provider interfaces
│   └── provider_factory.py   # Provider instantiation logic
├── providers/                # Broker-specific implementations
│   ├── gemini/              # Gemini exchange integration
│   │   ├── data.py          # Market data streaming
│   │   └── trade.py         # Order execution
│   └── alpaca/              # Alpaca platform integration
│       ├── data.py          # Market data streaming
│       └── trade.py         # Order execution
├── strategy/                # Trading logic and algorithms
│   ├── vwap.py             # VWAP calculations and analysis
│   ├── trigger.py          # Signal generation and triggers
│   ├── llm_gate.py         # LLM integration (optional)
│   ├── risk.py             # Risk management
│   └── backtest.py         # Backtesting engine
└── main.py                 # Main orchestrator and entry point
```

## Quick Start

### Prerequisites

- Python 3.9 or higher
- API credentials for your chosen trading platform(s)
- Sufficient account funding for your trading strategy

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/sigsegved/nemo.git
   cd nemo
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure your environment**:
   ```bash
   cp config.yaml config.local.yaml
   # Edit config.local.yaml with your settings
   ```

5. **Set up API credentials** (using environment variables):
   ```bash
   export ALPACA_API_KEY="your_alpaca_key"
   export ALPACA_SECRET_KEY="your_alpaca_secret"
   export GEMINI_API_KEY="your_gemini_key"
   export GEMINI_SECRET_KEY="your_gemini_secret"
   ```

### Running the Bot

```bash
# Start in paper trading mode (recommended for testing)
python src/main.py --config config.local.yaml --paper-trading

# Start in live trading mode (use with caution)
python src/main.py --config config.local.yaml --live-trading
```

## Configuration

The bot is configured through `config.yaml`. Key configuration sections include:

### Trading Configuration
- **Symbols**: Define which assets to trade
- **Session Times**: Set trading hours and timezone
- **Base Currency**: Configure accounting currency

### Provider Settings
- **Data Sources**: Primary and fallback data providers
- **Execution Venues**: Trading platform selection
- **API Configuration**: Credentials and endpoints

### Strategy Parameters
- **VWAP Settings**: Lookback periods and deviation thresholds
- **Trigger Configuration**: Volatility and confidence thresholds
- **Position Limits**: Maximum concurrent positions

### Risk Management
- **Position Sizing**: Methods and parameters
- **Stop Loss**: Types and percentages
- **Portfolio Limits**: Drawdown and leverage constraints

## Development

### Project Status

🚧 **This project is currently in foundation setup phase**. The directory structure and configuration templates are in place, but core functionality is still under development.

### Development Roadmap

1. **Phase 1: Foundation** ✅
   - [x] Repository structure setup
   - [x] Configuration templates
   - [x] Module stubs and documentation

2. **Phase 2: Core Infrastructure** (In Progress)
   - [ ] Data model implementations
   - [ ] Provider base classes
   - [ ] Factory pattern implementation

3. **Phase 3: Provider Integration**
   - [ ] Alpaca data provider
   - [ ] Alpaca trade provider
   - [ ] Gemini data provider
   - [ ] Gemini trade provider

4. **Phase 4: Strategy Engine**
   - [ ] VWAP calculation engine
   - [ ] Trigger mechanism
   - [ ] Risk management system
   - [ ] Main orchestrator

5. **Phase 5: Advanced Features**
   - [ ] LLM integration
   - [ ] Backtesting engine
   - [ ] Monitoring and alerts

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Style

- Use `black` for code formatting
- Follow `flake8` linting rules
- Add type hints (checked with `mypy`)
- Include docstrings for all public functions
- Write tests for new functionality

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test categories
pytest -m "not slow"  # Skip slow tests
```

## Security Considerations

- **Never commit API credentials** to version control
- **Use environment variables** for sensitive configuration
- **Enable paper trading** for development and testing
- **Implement proper logging** without exposing secrets
- **Regular security audits** of dependencies

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

**Important**: This software is for educational and research purposes. Algorithmic trading involves substantial risk of loss. Past performance does not guarantee future results. Use at your own risk and never trade with money you cannot afford to lose.

## Support

- 📧 Email: [Create an issue](https://github.com/sigsegved/nemo/issues/new)
- 📖 Documentation: [Wiki](https://github.com/sigsegved/nemo/wiki)
- 💬 Discussions: [GitHub Discussions](https://github.com/sigsegved/nemo/discussions)

---

**Happy Trading! 🚀**