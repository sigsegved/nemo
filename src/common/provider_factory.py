"""
Factory pattern implementation for provider instantiation.

This module provides a centralized factory for creating and configuring
data and trade providers based on configuration settings. Implements the
factory design pattern to abstract provider creation complexity.
"""

from typing import Any

from .provider_base import DataProvider, TradeProvider


class ProviderFactory:
    """Factory for creating provider instances based on configuration."""

    # Registry of available providers
    _data_providers: dict[str, type[DataProvider]] = {}
    _trade_providers: dict[str, type[TradeProvider]] = {}

    @classmethod
    def register_data_provider(
        cls, name: str, provider_class: type[DataProvider]
    ) -> None:
        """Register a data provider implementation."""
        cls._data_providers[name] = provider_class

    @classmethod
    def register_trade_provider(
        cls, name: str, provider_class: type[TradeProvider]
    ) -> None:
        """Register a trading provider implementation."""
        cls._trade_providers[name] = provider_class

    @classmethod
    def create_data_provider(
        cls, provider_name: str, config: dict[str, Any]
    ) -> DataProvider:
        """Create a data provider instance."""
        if provider_name not in cls._data_providers:
            raise ValueError(f"Unknown data provider: {provider_name}")

        provider_class = cls._data_providers[provider_name]
        return provider_class(config.get("providers", {}).get(provider_name, {}))

    @classmethod
    def create_trade_provider(
        cls, provider_name: str, config: dict[str, Any]
    ) -> TradeProvider:
        """Create a trading provider instance."""
        if provider_name not in cls._trade_providers:
            raise ValueError(f"Unknown trade provider: {provider_name}")

        provider_class = cls._trade_providers[provider_name]
        return provider_class(config.get("providers", {}).get(provider_name, {}))

    @classmethod
    def get_available_providers(cls) -> dict[str, Any]:
        """Get list of all registered providers."""
        return {
            "data_providers": list(cls._data_providers.keys()),
            "trade_providers": list(cls._trade_providers.keys()),
        }


def _register_builtin_providers():
    """Register built-in provider implementations."""
    try:
        from ..providers.gemini.data import GeminiDataProvider
        from ..providers.gemini.trade import GeminiTradeProvider

        ProviderFactory.register_data_provider("gemini", GeminiDataProvider)
        ProviderFactory.register_trade_provider("gemini", GeminiTradeProvider)
    except ImportError:
        pass  # Gemini providers not yet implemented

    try:
        from ..providers.alpaca.data import AlpacaDataProvider
        from ..providers.alpaca.trade import AlpacaTradeProvider

        ProviderFactory.register_data_provider("alpaca", AlpacaDataProvider)
        ProviderFactory.register_trade_provider("alpaca", AlpacaTradeProvider)
    except ImportError:
        pass  # Alpaca providers not yet implemented


# Auto-register on module import
_register_builtin_providers()
