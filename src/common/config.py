"""
Configuration system for the Nemo trading bot.

This module provides a robust configuration loading and validation system
that supports YAML files, environment variable overrides, and type-safe
access to configuration values with comprehensive validation.
"""

import os
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass
class ProviderConfig:
    """
    Configuration for a specific provider with validation.

    Attributes:
        api_key: API key for provider authentication
        api_secret: API secret for provider authentication
        ws_url: WebSocket URL for real-time data (optional)
        rest_url: REST API base URL (optional)
    """

    api_key: str
    api_secret: str
    ws_url: str = ""
    rest_url: str = ""

    def __post_init__(self) -> None:
        """Validate provider configuration after initialization."""
        self._validate_credentials()

    def _validate_credentials(self) -> None:
        """Validate credentials, allowing empty values to be filled from environment."""
        # Credentials can be empty in YAML if they're set via environment variables
        # We'll validate they're not empty only if they're meant to be used directly

        # Strip whitespace but allow empty strings for env var population
        if self.api_key:
            self.api_key = self.api_key.strip()
        if self.api_secret:
            self.api_secret = self.api_secret.strip()

    def validate_for_use(self) -> None:
        """
        Validate that credentials are available for use.
        Call this method before using the provider config.
        """
        if not self.api_key or not self.api_key.strip():
            raise ValueError("API key is required for provider usage")
        if not self.api_secret or not self.api_secret.strip():
            raise ValueError("API secret is required for provider usage")


@dataclass
class Config:
    """
    Main configuration class with comprehensive validation.

    This class provides type-safe access to all configuration parameters
    with automatic validation, environment variable support, and decimal
    precision for financial calculations.
    """

    # Provider selection
    data_provider: str
    trade_provider: str
    symbols: list[str]

    # Strategy parameters - using Decimal for financial precision
    price_dev: Decimal
    vol_mult: int
    llm_conf: Decimal
    max_gross_pct_equity: Decimal
    max_leverage: int
    stop_loss_pct: Decimal
    cooldown_hr: int

    # External services
    openai_model: str

    # Provider configurations
    providers: dict[str, ProviderConfig]

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate_symbols()
        self._validate_provider_names()
        self._validate_financial_params()
        self._validate_provider_availability()

    def _validate_symbols(self) -> None:
        """Validate trading symbols format."""
        if not self.symbols:
            raise ValueError("At least one symbol must be specified")

        for i, symbol in enumerate(self.symbols):
            if not symbol or not symbol.strip():
                raise ValueError(f"Symbol at index {i} cannot be empty")

            # Basic symbol format validation
            cleaned_symbol = symbol.strip()
            if not re.match(r"^[A-Z0-9\-]+$", cleaned_symbol):
                raise ValueError(f"Invalid symbol format: {symbol}")

            # Update with cleaned version
            self.symbols[i] = cleaned_symbol

    def _validate_provider_names(self) -> None:
        """Validate provider names."""
        if not self.data_provider or not self.data_provider.strip():
            raise ValueError("Data provider name cannot be empty")
        if not self.trade_provider or not self.trade_provider.strip():
            raise ValueError("Trade provider name cannot be empty")

        # Normalize provider names
        self.data_provider = self.data_provider.strip().lower()
        self.trade_provider = self.trade_provider.strip().lower()

    def _validate_financial_params(self) -> None:
        """Validate financial parameters."""
        if self.price_dev <= 0:
            raise ValueError("Price deviation must be positive")
        if self.vol_mult <= 0:
            raise ValueError("Volume multiplier must be positive")
        if not (0 <= self.llm_conf <= 1):
            raise ValueError("LLM confidence must be between 0 and 1")
        if not (0 < self.max_gross_pct_equity <= 1):
            raise ValueError("Max gross percentage equity must be between 0 and 1")
        if self.max_leverage <= 0:
            raise ValueError("Max leverage must be positive")
        if not (0 < self.stop_loss_pct <= 1):
            raise ValueError("Stop loss percentage must be between 0 and 1")
        if self.cooldown_hr < 0:
            raise ValueError("Cooldown hours cannot be negative")

    def _validate_provider_availability(self) -> None:
        """Ensure configured providers are available in providers dict."""
        # Convert provider names to lowercase for case-insensitive lookup
        available_providers = {name.lower(): name for name in self.providers.keys()}

        if self.data_provider.lower() not in available_providers:
            raise ValueError(
                f"Data provider '{self.data_provider}' not found in providers configuration"
            )

        if self.trade_provider.lower() not in available_providers:
            raise ValueError(
                f"Trade provider '{self.trade_provider}' not found in providers configuration"
            )

    def validate_for_trading(self) -> None:
        """
        Validate that configuration is ready for trading operations.
        This checks that all required credentials are present.
        """
        # Convert provider names to lowercase for case-insensitive lookup
        providers_by_lower = {
            name.lower(): config for name, config in self.providers.items()
        }

        # Validate data provider credentials
        data_provider_config = providers_by_lower.get(self.data_provider.lower())
        if data_provider_config:
            try:
                data_provider_config.validate_for_use()
            except ValueError as e:
                raise ValueError(
                    f"Data provider '{self.data_provider}' configuration invalid: {e}"
                )

        # Validate trade provider credentials
        trade_provider_config = providers_by_lower.get(self.trade_provider.lower())
        if trade_provider_config:
            try:
                trade_provider_config.validate_for_use()
            except ValueError as e:
                raise ValueError(
                    f"Trade provider '{self.trade_provider}' configuration invalid: {e}"
                )

        # Additional trading-specific validations could go here
        if not self.openai_model.strip():
            raise ValueError("OpenAI model must be specified for trading operations")

    def to_provider_factory_format(self) -> dict[str, Any]:
        """
        Convert configuration to format expected by ProviderFactory.

        Returns:
            Dictionary in format expected by provider factory
        """
        # Convert provider configurations to credentials format
        credentials = {}
        for name, provider_config in self.providers.items():
            credentials[name] = {
                "api_key": provider_config.api_key,
                "secret": provider_config.api_secret,
                "ws_url": provider_config.ws_url,
                "rest_url": provider_config.rest_url,
            }

        # Build provider factory expected structure
        return {
            "providers": {
                "data": {
                    "primary": self.data_provider.lower(),
                    "secondary": None,  # Could be configured if needed
                },
                "trade": {
                    "primary": self.trade_provider.lower(),
                    "paper_trading": True,  # Default to paper trading for safety
                },
            },
            "credentials": credentials,
            "trading": {
                "max_gross_pct_equity": float(self.max_gross_pct_equity),
                "max_leverage": self.max_leverage,
                "stop_loss_pct": float(self.stop_loss_pct),
                "price_dev": float(self.price_dev),
                "vol_mult": self.vol_mult,
                "symbols": self.symbols,
                "cooldown_hr": self.cooldown_hr,
            },
            "risk": {
                "limits": {
                    "max_drawdown": float(self.stop_loss_pct),
                    "daily_loss_limit": float(
                        self.max_gross_pct_equity * self.stop_loss_pct
                    ),
                }
            },
        }

    @classmethod
    def load_from_file(cls, config_path: str) -> "Config":
        """
        Load configuration from YAML file with comprehensive validation.

        Args:
            config_path: Path to the YAML configuration file

        Returns:
            Validated Config instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If configuration is invalid
            yaml.YAMLError: If YAML parsing fails
        """
        config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        try:
            with open(config_path, encoding="utf-8") as f:
                raw_config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration file: {e}")

        if not isinstance(raw_config, dict):
            raise ValueError("Configuration file must contain a YAML dictionary")

        # Apply environment variable substitution
        cls._substitute_env_variables(raw_config)

        # Apply environment variable overrides for sensitive data
        cls._apply_env_overrides(raw_config)

        # Validate and create config instance
        return cls._from_dict(raw_config)

    @staticmethod
    def _substitute_env_variables(config: dict[str, Any]) -> None:
        """
        Substitute environment variables using ${VAR:-default} pattern.

        Args:
            config: Configuration dictionary to process in-place
        """

        def substitute_recursive(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {k: substitute_recursive(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [substitute_recursive(item) for item in obj]
            elif isinstance(obj, str):
                # Pattern: ${VARIABLE_NAME:-default_value}
                pattern = r"\$\{([^}:]+)(?::-([^}]*))?\}"

                def replace_var(match):
                    var_name = match.group(1)
                    default_value = match.group(2) if match.group(2) is not None else ""
                    return os.environ.get(var_name, default_value)

                return re.sub(pattern, replace_var, obj)
            else:
                return obj

        # Apply substitution recursively
        for key, value in config.items():
            config[key] = substitute_recursive(value)

    @staticmethod
    def _apply_env_overrides(config: dict[str, Any]) -> None:
        """
        Apply environment variable overrides for sensitive data.

        This method provides direct environment variable overrides for
        API keys and secrets, prioritizing security.

        Args:
            config: Configuration dictionary to modify in-place
        """
        # Override API keys from environment
        providers_config = config.get("PROVIDERS", {})

        for provider_name in providers_config:
            provider_config = providers_config[provider_name]
            if not isinstance(provider_config, dict):
                continue

            api_key_env = f"{provider_name.upper()}_API_KEY"
            api_secret_env = f"{provider_name.upper()}_API_SECRET"

            if api_key_env in os.environ:
                provider_config["API_KEY"] = os.environ[api_key_env]
            if api_secret_env in os.environ:
                provider_config["API_SECRET"] = os.environ[api_secret_env]

    @classmethod
    def _from_dict(cls, config_dict: dict[str, Any]) -> "Config":
        """
        Create Config instance from dictionary with comprehensive validation.

        Args:
            config_dict: Configuration dictionary from YAML file

        Returns:
            Validated Config instance

        Raises:
            ValueError: If configuration validation fails
        """
        try:
            # Convert provider configs to ProviderConfig instances
            providers = {}
            providers_config = config_dict.get("PROVIDERS", {})

            for name, provider_data in providers_config.items():
                if not isinstance(provider_data, dict):
                    raise ValueError(
                        f"Provider configuration for '{name}' must be a dictionary"
                    )

                providers[name.lower()] = ProviderConfig(
                    api_key=provider_data.get("API_KEY", ""),
                    api_secret=provider_data.get("API_SECRET", ""),
                    ws_url=provider_data.get("WS_URL", ""),
                    rest_url=provider_data.get("REST_URL", ""),
                )

            # Normalize field names and convert types
            normalized_config = {
                "data_provider": config_dict.get("DATA_PROVIDER", ""),
                "trade_provider": config_dict.get("TRADE_PROVIDER", ""),
                "symbols": config_dict.get("SYMBOLS", []),
                "price_dev": Decimal(str(config_dict.get("PRICE_DEV", "0"))),
                "vol_mult": int(config_dict.get("VOL_MULT", 0)),
                "llm_conf": Decimal(str(config_dict.get("LLM_CONF", "0"))),
                "max_gross_pct_equity": Decimal(
                    str(config_dict.get("MAX_GROSS_PCT_EQUITY", "0"))
                ),
                "max_leverage": int(config_dict.get("MAX_LEVERAGE", 0)),
                "stop_loss_pct": Decimal(str(config_dict.get("STOP_LOSS_PCT", "0"))),
                "cooldown_hr": int(config_dict.get("COOLDOWN_HR", 0)),
                "openai_model": config_dict.get("OPENAI_MODEL", ""),
                "providers": providers,
            }

            # Use dataclass validation instead of Pydantic
            return cls(
                data_provider=normalized_config["data_provider"],
                trade_provider=normalized_config["trade_provider"],
                symbols=normalized_config["symbols"],
                price_dev=normalized_config["price_dev"],
                vol_mult=normalized_config["vol_mult"],
                llm_conf=normalized_config["llm_conf"],
                max_gross_pct_equity=normalized_config["max_gross_pct_equity"],
                max_leverage=normalized_config["max_leverage"],
                stop_loss_pct=normalized_config["stop_loss_pct"],
                cooldown_hr=normalized_config["cooldown_hr"],
                openai_model=normalized_config["openai_model"],
                providers=providers,
            )

        except Exception as e:
            raise ValueError(f"Configuration validation failed: {e}")


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Convenience function to load configuration.

    Args:
        config_path: Path to configuration file. Defaults to 'config.yaml'

    Returns:
        Validated Config instance
    """
    if config_path is None:
        config_path = "config.yaml"

        # Try local config first if it exists
        local_config = "config.local.yaml"
        if Path(local_config).exists():
            config_path = local_config

    return Config.load_from_file(config_path)
