# Nemo Volatility Harvest Bot Development Instructions

**ALWAYS follow these instructions first and only search or gather additional context if the information here is incomplete or incorrect.**

## Project Overview

Nemo is a Python-based algorithmic trading bot implementing volatility harvesting strategies using Volume Weighted Average Price (VWAP) calculations, market microstructure analysis, and multi-provider support (Alpaca Markets, Gemini Exchange). The project is in early development with core infrastructure complete and functional components under active development.

## Bootstrap and Environment Setup

**CRITICAL**: All commands below are validated and work correctly. **NEVER CANCEL** long-running operations.

### Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Install Dependencies (NEVER CANCEL: Takes 2-3 minutes)
```bash
pip install --upgrade pip wheel setuptools
```

**For stable CI-compatible dependencies (RECOMMENDED)**:
```bash
pip install -r requirements-ci.txt  # NEVER CANCEL: Takes 1 minute 47 seconds
```

**For full development dependencies (may have network issues)**:
```bash
pip install -r requirements.txt  # May timeout on some packages - use requirements-ci.txt if this fails
```

### Verify Core Dependencies
```bash
python -c "import pydantic; print('✓ pydantic', pydantic.__version__); import pytest; print('✓ pytest', pytest.__version__); import numpy; print('✓ numpy', numpy.__version__)"
```

## Development Configuration

### Setup Configuration
```bash
cp config.yaml config.local.yaml
# Edit config.local.yaml with your settings and API credentials
```

### Environment Variables (Required for Trading)
```bash
export ALPACA_API_KEY="your_alpaca_key"
export ALPACA_SECRET_KEY="your_alpaca_secret" 
export GEMINI_API_KEY="your_gemini_key"
export GEMINI_SECRET_KEY="your_gemini_secret"
```

**For paper trading tests**:
```bash
export PAPER_ALPACA_API_KEY="your_paper_alpaca_key"
export PAPER_ALPACA_API_SECRET="your_paper_alpaca_secret"
export PAPER_GEMINI_API_KEY="your_paper_gemini_key"  
export PAPER_GEMINI_API_SECRET="your_paper_gemini_secret"
```

## Build and Test Commands

### Code Quality (Fast - Under 1 second each)
```bash
ruff check src/ tests/                    # Linting
ruff format --check src/ tests/          # Format checking
ruff format src/ tests/                  # Auto-format code
ruff check --fix src/ tests/             # Auto-fix lint issues
```

### Testing (NEVER CANCEL)
```bash
pytest tests/ -v                         # NEVER CANCEL: Takes 11 seconds, runs 232 tests
pytest tests/ --cov=src --cov-report=term-missing  # NEVER CANCEL: Takes 12 seconds with coverage
pytest tests/ -m "unit"                  # Fast unit tests: Takes 1 second, 21 tests
pytest tests/ -m "integration"           # Integration tests: Takes 11 seconds, 20 tests
```

## Run the Application

### Demo Script (Validates Core Functionality)
```bash
python demo.py  # Takes 0.1 seconds - shows VWAP calculations and triggers
```

### Main Application
```bash
python src/main.py --help                                    # Show help
python src/main.py --config config.local.yaml --paper-trading   # Paper trading (safe)
python src/main.py --config config.local.yaml --live-trading    # Live trading (CAUTION)
```

## Manual Validation Requirements

**MANDATORY**: After any changes, ALWAYS run complete validation workflow:

### 1. Core Validation (Takes ~2 minutes total)
```bash
# Environment setup
source venv/bin/activate
pip install -r requirements-ci.txt  # NEVER CANCEL: 1m47s

# Code quality
ruff check src/ tests/               # < 1 second
ruff format --check src/ tests/     # < 1 second

# Full test suite  
pytest tests/ -v                    # NEVER CANCEL: 11 seconds
```

### 2. Functional Validation
```bash
# Test core functionality
python demo.py                      # Should show VWAP calculations and trigger detection

# Test main application  
python src/main.py --config config.local.yaml --paper-trading  # Should start without errors
```

### 3. Expected Output Validation
- **Demo script**: Should show trade processing, VWAP calculations, trigger detection, and summary
- **Main application**: Should show startup messages and trading mode confirmation
- **Tests**: Should pass 215+ tests with 85%+ coverage, may have 17 skips and 1 warning (normal)

## Directory Structure and Key Files

### Source Code
```
src/
├── common/                    # Shared components
│   ├── models.py             # Pydantic data models (100% coverage)
│   ├── provider_base.py      # Abstract provider interfaces
│   ├── provider_factory.py   # Provider instantiation logic
│   └── config.py             # Configuration management (88% coverage)
├── providers/                # Broker integrations
│   ├── gemini/              # Gemini exchange (73-86% coverage)
│   └── alpaca/              # Alpaca platform (100% coverage)
├── strategy/                 # Trading algorithms  
│   ├── vwap.py              # VWAP calculations (82% coverage)
│   ├── trigger.py           # Signal generation (97% coverage)
│   ├── risk.py              # Risk management (placeholder)
│   └── backtest.py          # Backtesting (placeholder)
└── main.py                  # Main entry point (0% coverage - placeholder)
```

### Tests
```
tests/
├── common/                  # Core component tests
├── providers/              # Provider-specific tests  
├── strategy/               # Strategy component tests
└── test_config.py          # Configuration system tests
```

### Configuration
- `config.yaml` - Template configuration
- `config.local.yaml` - Local overrides (gitignored)
- `pyproject.toml` - Python project configuration
- `requirements.txt` - Full dependencies (may have network issues)
- `requirements-ci.txt` - Stable CI dependencies (RECOMMENDED)

## CI/CD Pipeline

### GitHub Actions Workflow
- **Trigger**: Push/PR to main/develop branches
- **Python Version**: 3.12 (simplified from multi-version)
- **Validation**: Ruff linting/formatting, pytest with coverage
- **Expected Duration**: 2-3 minutes total
- **Resilient**: Graceful degradation for development-stage issues

### Pre-commit Setup (Optional)
```bash
pip install pre-commit
pre-commit install           # Auto-runs on commit
```

## Common Tasks and Patterns  

### Adding New Provider
1. Create directory under `src/providers/new_provider/`
2. Implement `data.py` inheriting from `DataProviderBase`  
3. Implement `trade.py` inheriting from `TradeProviderBase`
4. Register in `provider_factory.py`
5. Add configuration section to `config.yaml`
6. **MANDATORY**: Add comprehensive tests achieving 80%+ coverage

### Implementing Strategy Components
1. Follow patterns in `src/strategy/`
2. Use async methods for real-time operation
3. Implement comprehensive error handling
4. Add configuration parameters to `config.yaml`
5. **MANDATORY**: Write unit and integration tests

### Configuration Changes
1. Update `config.yaml` template
2. Ensure backward compatibility  
3. Add validation in `src/common/config.py`
4. **MANDATORY**: Update tests in `tests/test_config.py`

## Debugging and Development Tips

### Testing Specific Components
```bash
pytest tests/common/ -v                 # Test core components
pytest tests/providers/gemini/ -v       # Test Gemini provider
pytest tests/strategy/ -v               # Test strategy components
pytest tests/ -k "test_vwap" -v        # Test VWAP functionality
```

### Development Mode Commands
```bash
pytest tests/ --tb=long                 # Detailed error output
pytest tests/ --lf                      # Run only last failed tests
pytest tests/ -x                        # Stop on first failure
```

### Configuration Testing
```bash
python -c "from src.common.config import load_config; c = load_config('config.local.yaml'); print(f'Data provider: {c.data_provider}')"
```

## Architecture Notes

### Key Patterns
- **Provider Pattern**: Abstract base classes with concrete implementations
- **Factory Pattern**: Centralized provider instantiation
- **Async-First**: Real-time data processing with async/await
- **Configuration-Driven**: YAML with environment variable substitution
- **Type Safety**: Comprehensive Pydantic models and type hints

### Performance Considerations
- VWAP calculations use ring buffers for efficiency
- Numba optimization hooks for numerical computations
- Async patterns for I/O-bound operations
- Decimal precision for financial calculations

### Security Requirements
- **NEVER** commit API credentials to version control
- Use environment variables for sensitive configuration
- Enable paper trading for development and testing
- Validate all external API responses

## Critical Build and Timing Information

### Command Timeouts (NEVER CANCEL - Add 50% buffer)
- **pip install requirements-ci.txt**: 2 minutes (measured: 1m47s)
- **pytest tests/**: 20 seconds (measured: 11s)  
- **pytest with coverage**: 20 seconds (measured: 12s)
- **Integration tests**: 20 seconds (measured: 11s)
- **ruff commands**: Under 1 second each
- **demo.py**: Under 1 second

### CI Pipeline Timing
- **Total CI duration**: 3-4 minutes
- **Dependency installation**: 1-2 minutes
- **Testing phase**: 1-2 minutes
- **Quality checks**: Under 30 seconds

## Current Development State

### Completed Components (Ready for Use)
- ✅ Configuration system with environment variable support
- ✅ Pydantic data models for trading entities
- ✅ Provider factory and abstract base classes
- ✅ VWAP calculation engine with ring buffers
- ✅ Multi-trigger detection system
- ✅ Comprehensive test suite (232 tests, 85% coverage)
- ✅ CI/CD pipeline with quality gates

### In Development (Placeholders/Stubs)
- 🔄 Main orchestrator (basic structure only)
- 🔄 Risk management system (empty placeholder)
- 🔄 Backtesting engine (empty placeholder)
- 🔄 LLM integration (empty placeholder)

### Provider Implementation Status
- **Gemini**: Core functionality implemented (73-86% coverage)
- **Alpaca**: Stub implementation with interfaces (100% coverage)

## Validation Scenarios

### Core Functionality Test
1. Run `python demo.py`
2. Verify output shows:
   - Trade processing with prices and volumes
   - VWAP calculations for different timeframes
   - Trigger detection (price_deviation, volume_spike, liquidation_cluster)
   - Summary with signal counts

### Configuration Test  
1. Modify `config.local.yaml` with test values
2. Run `python src/main.py --config config.local.yaml --paper-trading`
3. Verify startup messages show correct config path and trading mode

### Development Workflow Test
1. Make small code change
2. Run `ruff format src/ tests/` (should format without errors)
3. Run `ruff check src/ tests/` (should pass all checks)
4. Run `pytest tests/ -v` (should pass 215+ tests)
5. Run coverage check (should maintain 85%+ coverage)

## Emergency Procedures

### If Tests Fail
1. Check recent changes with `git diff`
2. Run specific failing test: `pytest tests/path/to/test.py::test_name -v`
3. Check test output for specific error details
4. Revert changes if unclear: `git checkout -- filename`

### If Dependencies Fail
1. Use `requirements-ci.txt` instead of `requirements.txt`
2. Check network connectivity
3. Clear pip cache: `pip cache purge`
4. Recreate virtual environment if needed

### If CI Fails
1. Check GitHub Actions logs for specific error
2. Reproduce issue locally with exact CI commands
3. Focus on new changes since last successful build
4. Check for environment-specific issues

## Important Reminders

1. **ALWAYS** run the complete validation workflow before committing changes
2. **NEVER CANCEL** build or test commands - they complete quickly
3. **ALWAYS** test functionality manually using demo.py and main application
4. **MANDATORY** test coverage must remain above 80% for new code
5. Use `requirements-ci.txt` for reliable dependency installation
6. All API credentials must use environment variables, never hardcode
7. Test both paper-trading and configuration validation scenarios
8. Monitor CI pipeline and fix failures immediately

This project implements sophisticated financial algorithms with real-time requirements. Prioritize correctness, test coverage, and security in all modifications.