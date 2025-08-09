# Copilot Instructions for Nemo Volatility Harvest Bot

This document provides comprehensive guidance for AI coding assistants working on the Nemo algorithmic trading system. It covers project context, architecture, development practices, and domain-specific considerations.

## Project Overview

**Nemo** is a sophisticated algorithmic trading bot that implements volatility harvesting strategies using:
- Volume Weighted Average Price (VWAP) calculations
- Market microstructure analysis
- Multi-provider support (Alpaca Markets, Gemini Exchange)
- Advanced risk management and portfolio controls
- Optional LLM-enhanced decision making

### Current Development State
- **Phase**: Foundation setup complete, core functionality under development
- **Architecture**: Modular design with provider abstraction layer
- **Status**: Directory structure and configuration templates in place, implementation in progress

## Architecture Understanding

### Directory Structure
```
/src
├── common/                    # Shared components and abstractions
│   ├── models.py             # Pydantic data models
│   ├── provider_base.py      # Abstract provider interfaces  
│   └── provider_factory.py   # Provider instantiation logic
├── providers/                # Broker-specific implementations
│   ├── gemini/              # Gemini exchange integration
│   └── alpaca/              # Alpaca platform integration
├── strategy/                # Trading logic and algorithms
│   ├── vwap.py             # VWAP calculations and analysis
│   ├── trigger.py          # Signal generation and triggers
│   ├── llm_gate.py         # LLM integration (optional)
│   ├── risk.py             # Risk management
│   └── backtest.py         # Backtesting engine
└── main.py                 # Main orchestrator and entry point
```

### Key Architectural Patterns
1. **Provider Pattern**: Abstract base classes in `common/provider_base.py` with concrete implementations in `providers/`
2. **Factory Pattern**: `provider_factory.py` handles provider instantiation and configuration
3. **Strategy Components**: Modular strategy components that can be composed together
4. **Configuration-Driven**: YAML-based configuration with environment variable support
5. **Async-First**: Designed for asynchronous operation with real-time data streams

## Development Guidelines

### Code Quality Standards
- **Type Hints**: Use comprehensive type annotations (checked with mypy)
- **Formatting & Linting**: Use `ruff` for consistent code formatting and linting
- **Documentation**: Include docstrings for all public functions and classes
- **Testing**: **MANDATORY** - All PRs must include comprehensive tests using pytest

### Python Patterns Used
- **Pydantic Models**: Use for data validation and configuration management
- **Async/Await**: Prefer async patterns for I/O operations
- **Context Managers**: Use for resource management (connections, files)
- **Dataclasses/Pydantic**: Use for structured data representation
- **Abstract Base Classes**: Use ABC for defining interfaces

### Configuration Management
- Primary config: `config.yaml` with environment variable substitution
- Local overrides: `config.local.yaml` (gitignored)
- Environment variables: Use for sensitive data (API keys)
- Pattern: `${VARIABLE_NAME:-default_value}` for env var substitution

## Domain-Specific Considerations

### Trading System Requirements
1. **Real-time Performance**: Prioritize low-latency code paths
2. **Data Integrity**: Validate all market data and calculations
3. **Error Handling**: Graceful degradation and recovery mechanisms
4. **State Management**: Maintain consistent system state across failures
5. **Audit Trail**: Log all trading decisions and actions

### Risk Management Principles
- **Position Sizing**: Implement volatility-adjusted position sizing
- **Portfolio Limits**: Enforce maximum drawdown and leverage constraints
- **Stop Losses**: Implement multiple stop-loss mechanisms
- **Circuit Breakers**: Halt trading on excessive losses or system errors
- **Validation**: Validate all trades before execution

### Security Considerations
- **API Keys**: Never commit credentials to version control
- **Environment Variables**: Use for all sensitive configuration
- **Network Security**: Validate all external API responses
- **Data Sanitization**: Sanitize all inputs from external sources
- **Logging**: Avoid logging sensitive information (keys, balances)

## Common Development Tasks

### Adding a New Provider
1. Create directory under `src/providers/new_provider/`
2. Implement `data.py` inheriting from `DataProviderBase`
3. Implement `trade.py` inheriting from `TradeProviderBase`
4. Add configuration section to `config.yaml`
5. Update `provider_factory.py` to support new provider
6. Add comprehensive tests for all provider methods

### Implementing Strategy Components
1. Follow existing patterns in `src/strategy/`
2. Use dependency injection for provider access
3. Implement async methods for real-time operation
4. Include comprehensive error handling
5. Add configuration parameters to `config.yaml`
6. Write unit tests and integration tests

### Adding Risk Management Features
1. Extend `src/strategy/risk.py` with new risk checks
2. Integrate with main trading loop in `main.py`
3. Add configuration parameters under `risk:` section
4. Implement circuit breakers and emergency stops
5. Add monitoring and alerting capabilities

### Data Model Changes
1. Update Pydantic models in `src/common/models.py`
2. Ensure backward compatibility or migration strategy
3. Update all dependent code for new fields
4. Add validation rules and constraints
5. Update tests to cover new data structures

## Testing Approach

### Testing Requirements (MANDATORY)
- **All PRs must include tests** - No exceptions for new functionality
- **Coverage Requirements**: Minimum 80% test coverage for new code
- **Test Categories**: Unit, integration, strategy, and end-to-end tests
- **Mock External Services**: Always mock API calls and network dependencies
- **Test Both Success and Failure**: Include edge cases and error scenarios

### Testing Best Practices
- Use `pytest` fixtures for setup and teardown
- Mock external APIs and network calls
- Test both success and failure scenarios
- Use property-based testing for complex algorithms
- Separate fast tests from slow integration tests

### Test Data Management
- Use deterministic test data for reproducible results
- Create realistic market data scenarios
- Test edge cases (market gaps, halts, API failures)
- Validate against historical data when possible

## Code Examples and Patterns

### Provider Implementation Template
```python
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any
from ..common.provider_base import DataProviderBase
from ..common.models import MarketData, Symbol

class NewProviderData(DataProviderBase):
    async def connect(self) -> None:
        """Establish connection to data source."""
        # Implementation here
        
    async def subscribe_market_data(
        self, 
        symbols: List[Symbol]
    ) -> AsyncGenerator[MarketData, None]:
        """Stream real-time market data."""
        # Implementation here
        
    async def get_historical_data(
        self, 
        symbol: Symbol, 
        start: datetime, 
        end: datetime
    ) -> List[MarketData]:
        """Retrieve historical market data."""
        # Implementation here
```

### Configuration Loading Pattern
```python
import yaml
import os
from pathlib import Path
from typing import Dict, Any

def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration with environment variable substitution."""
    with open(config_path, 'r') as f:
        config_str = f.read()
    
    # Substitute environment variables
    config_str = os.path.expandvars(config_str)
    
    return yaml.safe_load(config_str)
```

### Error Handling Pattern
```python
import logging
from typing import Optional
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

@asynccontextmanager
async def trading_session():
    """Context manager for trading session with proper cleanup."""
    try:
        # Initialize providers and connections
        yield
    except Exception as e:
        logger.error(f"Trading session error: {e}")
        # Emergency shutdown procedures
        raise
    finally:
        # Cleanup and resource deallocation
        pass
```

## File Modification Guidelines

### When Modifying Existing Files
1. **Minimal Changes**: Make the smallest possible modifications
2. **Preserve Functionality**: Don't break existing working code
3. **Maintain Style**: Follow existing code patterns and formatting
4. **Add Tests**: Include tests for any new functionality
5. **Update Documentation**: Update docstrings and comments as needed

### When Adding New Files
1. **Follow Conventions**: Use existing naming and structure patterns
2. **Include Headers**: Add appropriate module docstrings
3. **Import Organization**: Follow established import patterns
4. **Error Handling**: Include comprehensive error handling
5. **Type Annotations**: Use complete type hints throughout

### Configuration Changes
1. **Backward Compatibility**: Ensure existing configs still work
2. **Default Values**: Provide sensible defaults for new parameters
3. **Documentation**: Update config comments and documentation
4. **Validation**: Add validation for new configuration options
5. **Environment Variables**: Use env vars for sensitive data

## Performance Considerations

### Real-time Requirements
- Minimize latency in data processing pipelines
- Use async/await for I/O bound operations  
- Implement connection pooling for API calls
- Cache frequently accessed data appropriately
- Monitor and profile critical code paths

### Memory Management
- Avoid large data structures in memory
- Use generators for data streaming
- Implement proper cleanup for resources
- Monitor memory usage in long-running processes
- Use efficient data structures (numpy arrays for numerical data)

## Debugging and Monitoring

### Logging Best Practices
- Use structured logging with context information
- Include timing information for performance monitoring
- Log all trading decisions and their rationale
- Separate security-sensitive information from general logs
- Use appropriate log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)

### Debugging Strategies
- Use paper trading mode for testing changes
- Implement comprehensive health checks
- Add metrics and monitoring endpoints
- Use correlation IDs for request tracking
- Implement circuit breakers for external dependencies

## Common Pitfalls to Avoid

### Trading System Specific
- **Never** commit API credentials or sensitive data
- Don't ignore error conditions in trading logic
- Avoid blocking operations in real-time data paths
- Don't bypass risk management checks
- Never trade with untested code changes

### Python/Architecture Specific
- Don't use synchronous I/O in async contexts
- Avoid tight coupling between providers and strategies
- Don't hardcode configuration values in source code
- Avoid circular imports between modules
- Don't ignore type checking warnings

### Performance Related
- Don't perform expensive calculations in hot paths
- Avoid creating objects unnecessarily in loops
- Don't block the event loop with CPU-intensive work
- Avoid memory leaks in long-running processes
- Don't ignore connection timeouts and retries

## Validated Build and Test Commands

**CRITICAL**: All commands below are validated and work correctly. **NEVER CANCEL** long-running operations.

### Environment Setup (NEVER CANCEL - Takes 2-3 minutes)
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install --upgrade pip wheel setuptools
pip install -r requirements-ci.txt  # NEVER CANCEL: Takes about 1-2 minutes
```

**Alternative for full development dependencies (may have network issues)**:
```bash
pip install -r requirements.txt  # May timeout - use requirements-ci.txt if this fails
```

### Verify Dependencies
```bash
python -c "import pydantic; print('✓ pydantic', pydantic.__version__); import pytest; print('✓ pytest', pytest.__version__); import numpy; print('✓ numpy', numpy.__version__)"
```

### Code Quality (Fast - Under 1 second each)
```bash
ruff check src/ tests/                    # Linting
ruff format --check src/ tests/          # Format checking
ruff format src/ tests/                  # Auto-format code
ruff check --fix src/ tests/             # Auto-fix lint issues
```

### Testing (NEVER CANCEL)
```bash
pytest tests/ -v                         # NEVER CANCEL: Takes 11 seconds, runs over 200 tests
pytest tests/ --cov=src --cov-report=term-missing  # NEVER CANCEL: Takes 12 seconds with coverage
pytest tests/ -m "unit"                  # Fast unit tests: Takes 1 second, 21 tests
pytest tests/ -m "integration"           # Integration tests: Takes 11 seconds, 20 tests
```

### Application Validation
```bash
python demo.py  # Takes 0.1 seconds - shows VWAP calculations and triggers
python src/main.py --config config.local.yaml --paper-trading   # Paper trading (safe)
```

### Configuration Setup
```bash
cp config.yaml config.local.yaml
# Edit config.local.yaml with your settings and API credentials
```

## Command Timing Information (Add 50% timeout buffer)
- **pip install requirements-ci.txt**: 2 minutes (measured: 1m47s)
- **pytest tests/**: 20 seconds (measured: 11s)  
- **pytest with coverage**: 20 seconds (measured: 12s)
- **Integration tests**: 20 seconds (measured: 11s)
- **ruff commands**: Under 1 second each
- **demo.py**: Under 1 second

## Getting Started Checklist

When working on the Nemo codebase:

1. **Setup Environment**
   - [ ] Create virtual environment: `python -m venv venv`
   - [ ] Activate environment: `source venv/bin/activate`
   - [ ] Install dependencies: `pip install -r requirements-ci.txt` (**NEVER CANCEL: 1m47s**)
   - [ ] Copy config template: `cp config.yaml config.local.yaml`

2. **Before Making Changes**
   - [ ] Run existing tests: `pytest tests/ -v` (**NEVER CANCEL: 11s, 232 tests**)
   - [ ] Check code style and linting: `ruff check src/ tests/`
   - [ ] Check code formatting: `ruff format --check src/ tests/`
   - [ ] Run type checking: `mypy src/`
   - [ ] Review relevant documentation and code

3. **Development Process**
   - [ ] **Create comprehensive tests first** (TDD approach recommended)
   - [ ] Implement changes with minimal modifications
   - [ ] Run tests frequently: `pytest -x`
   - [ ] Check formatting and linting: `ruff check src/ tests/`
   - [ ] Auto-format code: `ruff format src/ tests/`
   - [ ] Validate type hints: `mypy src/`

4. **Before Committing** 
   - [ ] **All tests pass**: `pytest tests/ -v` (**MANDATORY - NEVER CANCEL: 11s**)
   - [ ] **Test coverage verified**: Check coverage reports (should be 85%+)
   - [ ] **Code is formatted and linted**: `ruff check src/ tests/` and `ruff format src/ tests/`
   - [ ] Type checking passes: `mypy src/`
   - [ ] Documentation is updated
   - [ ] Configuration changes are documented

## Mandatory Validation Requirements

**After any changes, ALWAYS run complete validation workflow:**

### Core Validation (Takes ~2 minutes total)
```bash
source venv/bin/activate
pip install -r requirements-ci.txt  # NEVER CANCEL: 1m47s
ruff check src/ tests/               # < 1 second
ruff format --check src/ tests/     # < 1 second
pip install -r requirements-ci.txt
ruff check src/ tests/
ruff format --check src/ tests/
pytest tests/ -v
```

### Functional Validation
```bash
python demo.py                      # Should show VWAP calculations and trigger detection
python src/main.py --config config.local.yaml --paper-trading  # Should start without errors
```

### Expected Output Validation
- **Demo script**: Should show trade processing, VWAP calculations, trigger detection, and summary
- **Main application**: Should show startup messages and trading mode confirmation
- **Tests**: Should pass 215+ tests with 85%+ coverage, may have 17 skips and 1 warning (normal)

## Emergency Procedures

### If Tests Fail
1. Check recent changes with `git --no-pager diff`
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

## Additional Resources

- **README.md**: Project overview and quick start guide
- **config.yaml**: Configuration template with comments
- **requirements.txt**: Complete dependency list (use requirements-ci.txt for reliability)
- **requirements-ci.txt**: Stable CI dependencies (RECOMMENDED)
- **LICENSE**: Project licensing information

## Notes for AI Assistants

- This is a financial trading system - prioritize correctness and safety
- The codebase is in early development - many files contain TODO comments and placeholder implementations  
- Focus on implementing robust, well-tested components that follow established patterns
- Always consider the real-time, high-stakes nature of trading applications
- When in doubt about trading logic or risk management, err on the side of caution

## Critical Operational Notes

1. **NEVER CANCEL** build or test commands - they complete quickly (validated timing above)
2. **ALWAYS** test functionality manually using demo.py and main application
3. **MANDATORY** test coverage must remain above 80% for new code
4. Use `requirements-ci.txt` for reliable dependency installation
5. All API credentials must use environment variables, never hardcode
6. Test both paper-trading and configuration validation scenarios
7. Monitor CI pipeline and fix failures immediately

This project implements sophisticated financial algorithms with real-time requirements. Prioritize correctness, test coverage, and security in all modifications.
