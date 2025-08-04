# Configuration System Examples

This document shows examples of how to use the enhanced configuration system.

## Basic Usage

```python
from common.config import Config, load_config

# Load configuration from file
config = Config.load_from_file('config.yaml')

# Or use the convenience function
config = load_config()  # Looks for config.yaml, then config.local.yaml

# Access configuration values with type safety
symbols = config.symbols              # List[str]
price_dev = config.price_dev          # Decimal
providers = config.providers          # Dict[str, ProviderConfig]
```

## Environment Variable Substitution

The configuration system supports `${VAR:-default}` pattern substitution:

```yaml
# config.yaml
DATA_PROVIDER: ${DATA_PROVIDER:-gemini}
TRADE_PROVIDER: ${TRADE_PROVIDER:-gemini}
OPENAI_MODEL: ${OPENAI_MODEL:-gpt-4o-mini}

PROVIDERS:
  gemini:
    API_KEY: ${GEMINI_API_KEY:-}
    API_SECRET: ${GEMINI_API_SECRET:-}
```

```bash
# Set environment variables
export DATA_PROVIDER=alpaca
export GEMINI_API_KEY=your_actual_key
export GEMINI_API_SECRET=your_actual_secret
```

## Environment Variable Overrides

API keys and secrets are automatically overridden from environment variables:

```python
# These environment variables automatically override YAML values:
# GEMINI_API_KEY, GEMINI_API_SECRET
# ALPACA_API_KEY, ALPACA_API_SECRET

config = load_config()
# API keys from env vars are automatically loaded
```

## Financial Precision

All financial values use Decimal for precision:

```python
config = load_config()

# All financial calculations maintain precision
risk_amount = config.max_gross_pct_equity * config.stop_loss_pct
position_size = config.price_dev * Decimal('1000')

print(f"Risk calculation: {risk_amount}")  # Precise decimal result
```

## Validation

The system provides comprehensive validation:

```python
try:
    config = load_config()
    
    # Validate configuration is ready for trading
    config.validate_for_trading()
    
    print("Configuration is valid and ready for trading")
except ValueError as e:
    print(f"Configuration error: {e}")
```

## Provider Configuration

Access provider-specific settings:

```python
config = load_config()

# Get provider configuration
gemini_config = config.providers['gemini']
print(f"Gemini REST URL: {gemini_config.rest_url}")
print(f"Gemini WS URL: {gemini_config.ws_url}")

# Validate provider credentials at runtime
try:
    gemini_config.validate_for_use()
    print("Gemini credentials are valid")
except ValueError as e:
    print(f"Gemini credentials invalid: {e}")
```

## Error Handling

The configuration system provides detailed error messages:

```python
try:
    config = Config.load_from_file('invalid_config.yaml')
except FileNotFoundError:
    print("Configuration file not found")
except ValueError as e:
    print(f"Configuration validation failed: {e}")
except yaml.YAMLError as e:
    print(f"YAML parsing failed: {e}")
```

## Configuration Structure

Expected YAML structure:

```yaml
# Provider selection
DATA_PROVIDER: gemini              # Data source provider
TRADE_PROVIDER: gemini             # Trading execution provider

# Trading symbols
SYMBOLS: 
  - "BTC-GUSD-PERP"
  - "ETH-GUSD-PERP"

# Strategy parameters (use Decimal precision)
PRICE_DEV: 0.01                    # Price deviation threshold
VOL_MULT: 3                        # Volume multiplier
LLM_CONF: 0.65                     # LLM confidence threshold (0-1)
MAX_GROSS_PCT_EQUITY: 0.25         # Max gross equity percentage (0-1)
MAX_LEVERAGE: 3                    # Maximum leverage
STOP_LOSS_PCT: 0.01                # Stop loss percentage (0-1)
COOLDOWN_HR: 6                     # Cooldown period in hours

# External services
OPENAI_MODEL: gpt-4o-mini          # OpenAI model name

# Provider configurations
PROVIDERS:
  gemini:
    API_KEY: ""                    # Will be overridden by GEMINI_API_KEY env var
    API_SECRET: ""                 # Will be overridden by GEMINI_API_SECRET env var
    WS_URL: wss://api.gemini.com/v2/marketdata
    REST_URL: https://api.gemini.com
  
  alpaca:
    API_KEY: ""                    # Will be overridden by ALPACA_API_KEY env var
    API_SECRET: ""                 # Will be overridden by ALPACA_API_SECRET env var
    WS_URL: wss://stream.data.alpaca.markets/v2/iex
    REST_URL: https://paper-api.alpaca.markets
```

## Security Best Practices

1. **Never commit API keys to version control**
2. **Use environment variables for sensitive data**
3. **Use config.local.yaml for local overrides** (add to .gitignore)
4. **Validate credentials at runtime before trading**

```python
# Good practice: Validate before use
config = load_config()

# Check if we're ready for live trading
try:
    config.validate_for_trading()
    print("✓ Ready for trading")
except ValueError as e:
    print(f"✗ Configuration issue: {e}")
    exit(1)
```