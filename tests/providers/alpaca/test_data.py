"""
Tests for Alpaca data provider.

These tests cover the Alpaca data provider implementation, including:
- Configuration handling with paper trading endpoints
- Proper NotImplementedError behavior for unimplemented methods
- Integration tests using paper trading credentials when available
"""

import os
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

from src.providers.alpaca.data import AlpacaDataProvider
from src.common.models import TradeTick, MarketEvent


class TestAlpacaDataProviderConfiguration:
    """Test Alpaca data provider configuration."""

    def test_init_with_default_config(self):
        """Test initialization with default configuration."""
        config = {}
        provider = AlpacaDataProvider(config)
        
        assert provider.config == config
        assert provider.api_key == ""
        assert provider.api_secret == ""
        assert provider.rest_url == "https://paper-api.alpaca.markets/v2"
        assert provider.ws_url == "wss://stream.data.alpaca.markets/v2/iex"

    def test_init_with_custom_config(self):
        """Test initialization with custom configuration."""
        config = {
            "API_KEY": "test_key",
            "API_SECRET": "test_secret", 
            "REST_URL": "https://custom.alpaca.com/v2",
            "WS_URL": "wss://custom.alpaca.com/stream"
        }
        provider = AlpacaDataProvider(config)
        
        assert provider.config == config
        assert provider.api_key == "test_key"
        assert provider.api_secret == "test_secret"
        assert provider.rest_url == "https://custom.alpaca.com/v2"
        assert provider.ws_url == "wss://custom.alpaca.com/stream"

    def test_init_with_partial_config(self):
        """Test initialization with partial configuration."""
        config = {
            "API_KEY": "partial_key",
            "REST_URL": "https://paper-api.alpaca.markets/v2"
        }
        provider = AlpacaDataProvider(config)
        
        assert provider.api_key == "partial_key"
        assert provider.api_secret == ""  # Default empty
        assert provider.rest_url == "https://paper-api.alpaca.markets/v2"
        assert provider.ws_url == "wss://stream.data.alpaca.markets/v2/iex"  # Default


class TestAlpacaDataProviderNotImplemented:
    """Test that all Alpaca data provider methods properly raise NotImplementedError."""

    @pytest.fixture
    def provider(self):
        """Create a provider instance for testing."""
        config = {
            "API_KEY": "test_key",
            "API_SECRET": "test_secret"
        }
        return AlpacaDataProvider(config)

    @pytest.mark.asyncio
    async def test_connect_not_implemented(self, provider):
        """Test that connect raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Alpaca data provider not yet implemented"):
            await provider.connect()

    @pytest.mark.asyncio
    async def test_subscribe_trades_not_implemented(self, provider):
        """Test that subscribe_trades raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Alpaca data provider not yet implemented"):
            await provider.subscribe_trades(["AAPL", "TSLA"])

    @pytest.mark.asyncio
    async def test_subscribe_events_not_implemented(self, provider):
        """Test that subscribe_events raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Alpaca data provider not yet implemented"):
            await provider.subscribe_events(["AAPL"])

    @pytest.mark.asyncio
    async def test_iter_ticks_not_implemented(self, provider):
        """Test that iter_ticks raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Alpaca data provider not yet implemented"):
            async for tick in provider.iter_ticks():
                break  # Should not reach here

    @pytest.mark.asyncio
    async def test_iter_events_not_implemented(self, provider):
        """Test that iter_events raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Alpaca data provider not yet implemented"):
            async for event in provider.iter_events():
                break  # Should not reach here

    @pytest.mark.asyncio
    async def test_disconnect_not_implemented(self, provider):
        """Test that disconnect raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Alpaca data provider not yet implemented"):
            await provider.disconnect()


@pytest.mark.integration
@pytest.mark.network
class TestAlpacaDataProviderIntegration:
    """Integration tests for Alpaca data provider using paper trading."""

    @pytest.fixture
    def paper_trading_config(self):
        """Get paper trading configuration from environment."""
        api_key = os.getenv("PAPER_ALPACA_API_KEY")
        api_secret = os.getenv("PAPER_ALPACA_API_SECRET")
        
        if not api_key or not api_secret:
            pytest.skip("Paper trading credentials not available in environment")
        
        return {
            "API_KEY": api_key,
            "API_SECRET": api_secret,
            "REST_URL": "https://paper-api.alpaca.markets/v2",
            "WS_URL": "wss://stream.data.alpaca.markets/v2/iex"
        }

    def test_paper_trading_config_available(self, paper_trading_config):
        """Test that paper trading configuration is properly loaded."""
        provider = AlpacaDataProvider(paper_trading_config)
        
        assert provider.api_key != ""
        assert provider.api_secret != ""
        assert provider.rest_url == "https://paper-api.alpaca.markets/v2"
        assert provider.ws_url == "wss://stream.data.alpaca.markets/v2/iex"

    @pytest.mark.skip(reason="Implementation pending - currently raises NotImplementedError")
    @pytest.mark.asyncio
    async def test_paper_trading_connection(self, paper_trading_config):
        """Test connection to paper trading environment (skipped until implemented)."""
        provider = AlpacaDataProvider(paper_trading_config)
        
        # This will be enabled once the Alpaca provider is implemented
        # await provider.connect()
        # await provider.disconnect()
        pass

    @pytest.mark.skip(reason="Implementation pending - currently raises NotImplementedError") 
    @pytest.mark.asyncio
    async def test_paper_trading_subscription(self, paper_trading_config):
        """Test symbol subscription in paper trading (skipped until implemented)."""
        provider = AlpacaDataProvider(paper_trading_config)
        
        # This will be enabled once the Alpaca provider is implemented
        # await provider.connect()
        # await provider.subscribe_trades(["AAPL", "TSLA"])
        # await provider.disconnect()
        pass


class TestAlpacaDataProviderMocking:
    """Test Alpaca data provider with mocked dependencies."""

    @pytest.fixture
    def provider(self):
        """Create provider with test configuration."""
        config = {
            "API_KEY": "test_key",
            "API_SECRET": "test_secret",
            "REST_URL": "https://paper-api.alpaca.markets/v2"
        }
        return AlpacaDataProvider(config)

    def test_provider_follows_interface(self, provider):
        """Test that provider follows the DataProvider interface."""
        from src.common.provider_base import DataProvider
        
        assert isinstance(provider, DataProvider)
        
        # Check that all abstract methods are present
        abstract_methods = DataProvider.__abstractmethods__
        for method_name in abstract_methods:
            assert hasattr(provider, method_name)
            assert callable(getattr(provider, method_name))

    def test_provider_configuration_access(self, provider):
        """Test that provider properly stores and accesses configuration."""
        assert provider.config["API_KEY"] == "test_key"
        assert provider.config["API_SECRET"] == "test_secret"
        assert provider.api_key == "test_key"
        assert provider.api_secret == "test_secret"


@pytest.mark.unit
class TestAlpacaDataProviderUnit:
    """Unit tests for Alpaca data provider components."""

    def test_paper_trading_endpoint_default(self):
        """Test that paper trading endpoint is used by default."""
        provider = AlpacaDataProvider({})
        assert "paper-api.alpaca.markets" in provider.rest_url
        assert "/v2" in provider.rest_url

    def test_websocket_endpoint_default(self):
        """Test that correct WebSocket endpoint is used by default.""" 
        provider = AlpacaDataProvider({})
        assert "stream.data.alpaca.markets" in provider.ws_url
        assert "/v2/iex" in provider.ws_url

    def test_config_precedence(self):
        """Test that explicit config takes precedence over defaults."""
        custom_rest_url = "https://custom.example.com/api"
        custom_ws_url = "wss://custom.example.com/stream"
        
        config = {
            "REST_URL": custom_rest_url,
            "WS_URL": custom_ws_url
        }
        provider = AlpacaDataProvider(config)
        
        assert provider.rest_url == custom_rest_url
        assert provider.ws_url == custom_ws_url

    def test_empty_credentials_handling(self):
        """Test handling of empty credentials."""
        provider = AlpacaDataProvider({})
        
        assert provider.api_key == ""
        assert provider.api_secret == ""
        # Should not raise during initialization
        assert provider.config == {}


if __name__ == "__main__":
    pytest.main([__file__])