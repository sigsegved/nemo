"""
Factory pattern implementation for provider instantiation.

This module provides a centralized factory for creating and configuring
data and trade providers based on configuration settings. Implements the
factory design pattern to abstract provider creation complexity.
"""

from typing import Dict, Any, Optional
from .provider_base import DataProvider, TradeProvider


class ProviderFactory:
    """Factory for creating and configuring providers based on configuration."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize factory with configuration.
        
        Args:
            config: Complete configuration dictionary
        """
        self.config = config
        self._data_providers: Dict[str, type] = {}
        self._trade_providers: Dict[str, type] = {}
        self._register_providers()
    
    def _register_providers(self) -> None:
        """Register available provider implementations."""
        # This will be extended as concrete providers are implemented
        # For now, we define the registry structure
        
        # Register data providers when they're implemented
        # self._data_providers = {
        #     "alpaca": AlpacaDataProvider,
        #     "gemini": GeminiDataProvider,
        # }
        
        # Register trade providers when they're implemented  
        # self._trade_providers = {
        #     "alpaca": AlpacaTradeProvider,
        #     "gemini": GeminiTradeProvider,
        # }
    
    def create_data_provider(self, provider_name: Optional[str] = None) -> DataProvider:
        """Create and configure a data provider.
        
        Args:
            provider_name: Provider name override, uses config default if None
            
        Returns:
            Configured DataProvider instance
            
        Raises:
            ValueError: If provider is not registered or configured
            NotImplementedError: If provider implementation is not available
        """
        if self.config is None:
            raise ValueError("Configuration is None")
        
        if provider_name is None:
            provider_name = self.config.get("providers", {}).get("data", {}).get("primary")
        
        if not provider_name:
            raise ValueError("No data provider specified in configuration")
        
        if provider_name not in self._data_providers:
            raise NotImplementedError(f"Data provider '{provider_name}' not yet implemented")
        
        provider_class = self._data_providers[provider_name]
        provider_config = self._get_provider_config(provider_name)
        
        return provider_class(provider_config)
    
    def create_trade_provider(self, provider_name: Optional[str] = None) -> TradeProvider:
        """Create and configure a trade provider.
        
        Args:
            provider_name: Provider name override, uses config default if None
            
        Returns:
            Configured TradeProvider instance
            
        Raises:
            ValueError: If provider is not registered or configured
            NotImplementedError: If provider implementation is not available
        """
        if provider_name is None:
            provider_name = self.config.get("providers", {}).get("trade", {}).get("primary")
        
        if not provider_name:
            raise ValueError("No trade provider specified in configuration")
        
        if provider_name not in self._trade_providers:
            raise NotImplementedError(f"Trade provider '{provider_name}' not yet implemented")
        
        provider_class = self._trade_providers[provider_name]
        provider_config = self._get_provider_config(provider_name)
        
        return provider_class(provider_config)
    
    def _get_provider_config(self, provider_name: str) -> Dict[str, Any]:
        """Extract provider-specific configuration.
        
        Args:
            provider_name: Name of the provider
            
        Returns:
            Provider-specific configuration dictionary
        """
        provider_config = {
            "credentials": self.config.get("credentials", {}).get(provider_name, {}),
            "trading": self.config.get("trading", {}),
            "paper_trading": self.config.get("providers", {}).get("trade", {}).get("paper_trading", True),
        }
        
        return provider_config
    
    def get_available_providers(self) -> Dict[str, Any]:
        """Get information about available providers.
        
        Returns:
            Dictionary with available data and trade providers
        """
        return {
            "data_providers": list(self._data_providers.keys()),
            "trade_providers": list(self._trade_providers.keys()),
            "configured": {
                "data_primary": self.config.get("providers", {}).get("data", {}).get("primary"),
                "data_secondary": self.config.get("providers", {}).get("data", {}).get("secondary"),
                "trade_primary": self.config.get("providers", {}).get("trade", {}).get("primary"),
            }
        }


class DataProviderFactory:
    """Specialized factory for data providers with fallback logic."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize data provider factory.
        
        Args:
            config: Configuration dictionary
        """
        self.factory = ProviderFactory(config)
        self.config = config
    
    def create_primary_provider(self) -> DataProvider:
        """Create primary data provider."""
        return self.factory.create_data_provider()
    
    def create_secondary_provider(self) -> Optional[DataProvider]:
        """Create secondary (fallback) data provider if configured."""
        secondary = self.config.get("providers", {}).get("data", {}).get("secondary")
        if secondary:
            try:
                return self.factory.create_data_provider(secondary)
            except (ValueError, NotImplementedError):
                return None
        return None


class TradeProviderFactory:
    """Specialized factory for trade providers with configuration validation."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize trade provider factory.
        
        Args:
            config: Configuration dictionary
        """
        self.factory = ProviderFactory(config)
        self.config = config
    
    def create_primary_provider(self) -> TradeProvider:
        """Create primary trade provider with validation."""
        # Validate paper trading settings first
        paper_trading = self.config.get("providers", {}).get("trade", {}).get("paper_trading", True)
        if not paper_trading:
            # Additional validation for live trading
            self._validate_live_trading_config()
        
        provider = self.factory.create_trade_provider()
        
        return provider
    
    def _validate_live_trading_config(self) -> None:
        """Validate configuration for live trading mode."""
        # Ensure risk management is properly configured for live trading
        risk_config = self.config.get("risk", {})
        if not risk_config:
            raise ValueError("Risk management configuration required for live trading")
        
        # Ensure position limits are set
        limits = risk_config.get("limits", {})
        if not limits.get("max_drawdown") or not limits.get("daily_loss_limit"):
            raise ValueError("Position limits required for live trading")