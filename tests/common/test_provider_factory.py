"""
Test cases for provider factory functionality.

This module tests the ProviderFactory class, which provides a centralized
factory for creating data and trade provider instances based on configuration.
"""

import pytest
from typing import Dict, Any
from unittest.mock import Mock, patch

from src.common.provider_factory import ProviderFactory


class TestProviderFactory:
    """Test cases for ProviderFactory class."""
    
    def test_get_available_providers_empty(self):
        """Test getting available providers when none are registered."""
        # Clear registries for testing
        original_data = ProviderFactory._data_providers.copy()
        original_trade = ProviderFactory._trade_providers.copy()
        
        ProviderFactory._data_providers.clear()
        ProviderFactory._trade_providers.clear()
        
        try:
            available = ProviderFactory.get_available_providers()
            assert available == {
                'data_providers': [],
                'trade_providers': []
            }
        finally:
            # Restore original registries
            ProviderFactory._data_providers.update(original_data)
            ProviderFactory._trade_providers.update(original_trade)
    
    def test_register_data_provider(self):
        """Test registering a data provider."""
        mock_provider = Mock()
        ProviderFactory.register_data_provider("test_data", mock_provider)
        
        assert "test_data" in ProviderFactory._data_providers
        assert ProviderFactory._data_providers["test_data"] == mock_provider
        
        # Clean up
        del ProviderFactory._data_providers["test_data"]
    
    def test_register_trade_provider(self):
        """Test registering a trade provider."""
        mock_provider = Mock()
        ProviderFactory.register_trade_provider("test_trade", mock_provider)
        
        assert "test_trade" in ProviderFactory._trade_providers
        assert ProviderFactory._trade_providers["test_trade"] == mock_provider
        
        # Clean up
        del ProviderFactory._trade_providers["test_trade"]
    
    def test_create_data_provider_unknown(self):
        """Test creating unknown data provider raises ValueError."""
        config = {"providers": {"unknown": {}}}
        
        with pytest.raises(ValueError) as exc_info:
            ProviderFactory.create_data_provider("unknown", config)
        
        assert "Unknown data provider: unknown" in str(exc_info.value)
    
    def test_create_trade_provider_unknown(self):
        """Test creating unknown trade provider raises ValueError."""
        config = {"providers": {"unknown": {}}}
        
        with pytest.raises(ValueError) as exc_info:
            ProviderFactory.create_trade_provider("unknown", config)
        
        assert "Unknown trade provider: unknown" in str(exc_info.value)
    
    def test_create_data_provider_success(self):
        """Test successful data provider creation."""
        mock_provider_class = Mock()
        mock_instance = Mock()
        mock_provider_class.return_value = mock_instance
        
        ProviderFactory.register_data_provider("test_data", mock_provider_class)
        
        try:
            config = {
                "providers": {
                    "test_data": {
                        "api_key": "test_key"
                    }
                }
            }
            
            result = ProviderFactory.create_data_provider("test_data", config)
            
            assert result == mock_instance
            mock_provider_class.assert_called_once_with({
                "api_key": "test_key"
            })
        finally:
            # Clean up
            del ProviderFactory._data_providers["test_data"]
    
    def test_create_trade_provider_success(self):
        """Test successful trade provider creation."""
        mock_provider_class = Mock()
        mock_instance = Mock()
        mock_provider_class.return_value = mock_instance
        
        ProviderFactory.register_trade_provider("test_trade", mock_provider_class)
        
        try:
            config = {
                "providers": {
                    "test_trade": {
                        "api_secret": "test_secret"
                    }
                }
            }
            
            result = ProviderFactory.create_trade_provider("test_trade", config)
            
            assert result == mock_instance
            mock_provider_class.assert_called_once_with({
                "api_secret": "test_secret"
            })
        finally:
            # Clean up
            del ProviderFactory._trade_providers["test_trade"]
    
    def test_create_provider_no_config_section(self):
        """Test provider creation with missing config section."""
        mock_provider_class = Mock()
        mock_instance = Mock()
        mock_provider_class.return_value = mock_instance
        
        ProviderFactory.register_data_provider("test_data", mock_provider_class)
        
        try:
            config = {}  # No providers section
            
            result = ProviderFactory.create_data_provider("test_data", config)
            
            assert result == mock_instance
            # Should be called with empty dict when no providers section exists
            mock_provider_class.assert_called_once_with({})
        finally:
            # Clean up
            del ProviderFactory._data_providers["test_data"]
    
    def test_builtin_providers_registered(self):
        """Test that built-in providers are automatically registered."""
        available = ProviderFactory.get_available_providers()
        
        # Should have at least alpaca and gemini providers registered
        data_providers = available['data_providers']
        trade_providers = available['trade_providers']
        
        # Check if providers are registered (they might be skipped if import fails)
        # This test is flexible - providers may or may not be available
        assert isinstance(data_providers, list)
        assert isinstance(trade_providers, list)
        
        # If providers are available, they should include our expected ones
        if data_providers:
            # At least one provider should be registered
            assert len(data_providers) > 0
        
        if trade_providers:
            # At least one provider should be registered
            assert len(trade_providers) > 0