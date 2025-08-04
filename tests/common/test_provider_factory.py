"""
Tests for provider factory implementation.

This module tests the factory pattern for provider instantiation:
- ProviderFactory configuration-driven creation
- DataProviderFactory with fallback logic
- TradeProviderFactory with validation
- Configuration management and error handling
"""

import pytest
from typing import Dict, Any
from unittest.mock import Mock, patch

from src.common.provider_factory import (
    ProviderFactory,
    DataProviderFactory,
    TradeProviderFactory
)


class TestProviderFactory:
    """Test cases for base ProviderFactory."""
    
    def test_factory_initialization(self):
        """Test ProviderFactory initialization with configuration."""
        config = {
            "providers": {
                "data": {"primary": "alpaca"},
                "trade": {"primary": "gemini"}
            },
            "credentials": {
                "alpaca": {"api_key": "test_key"},
                "gemini": {"api_key": "test_key"}
            }
        }
        
        factory = ProviderFactory(config)
        
        assert factory.config == config
        assert isinstance(factory._data_providers, dict)
        assert isinstance(factory._trade_providers, dict)
    
    def test_get_provider_config(self):
        """Test provider-specific configuration extraction."""
        config = {
            "providers": {
                "trade": {"paper_trading": False}
            },
            "credentials": {
                "alpaca": {
                    "api_key": "test_key",
                    "secret": "test_secret"
                }
            },
            "trading": {
                "max_position_size": 1000
            }
        }
        
        factory = ProviderFactory(config)
        provider_config = factory._get_provider_config("alpaca")
        
        assert provider_config["credentials"]["api_key"] == "test_key"
        assert provider_config["credentials"]["secret"] == "test_secret"
        assert provider_config["trading"]["max_position_size"] == 1000
        assert provider_config["paper_trading"] is False
    
    def test_get_provider_config_with_defaults(self):
        """Test provider configuration with default values."""
        config = {
            "credentials": {
                "gemini": {"api_key": "test_key"}
            }
        }
        
        factory = ProviderFactory(config)
        provider_config = factory._get_provider_config("gemini")
        
        # Should have defaults
        assert provider_config["paper_trading"] is True  # Default
        assert provider_config["trading"] == {}  # Empty dict default
        assert provider_config["credentials"]["api_key"] == "test_key"
    
    def test_data_provider_creation_not_implemented(self):
        """Test that data provider creation raises NotImplementedError."""
        config = {
            "providers": {
                "data": {"primary": "alpaca"}
            }
        }
        
        factory = ProviderFactory(config)
        
        with pytest.raises(NotImplementedError) as exc_info:
            factory.create_data_provider()
        
        assert "Data provider 'alpaca' not yet implemented" in str(exc_info.value)
    
    def test_trade_provider_creation_not_implemented(self):
        """Test that trade provider creation raises NotImplementedError."""
        config = {
            "providers": {
                "trade": {"primary": "gemini"}
            }
        }
        
        factory = ProviderFactory(config)
        
        with pytest.raises(NotImplementedError) as exc_info:
            factory.create_trade_provider()
        
        assert "Trade provider 'gemini' not yet implemented" in str(exc_info.value)
    
    def test_data_provider_no_configuration(self):
        """Test data provider creation with no configuration."""
        config = {}
        factory = ProviderFactory(config)
        
        with pytest.raises(ValueError) as exc_info:
            factory.create_data_provider()
        
        assert "No data provider specified in configuration" in str(exc_info.value)
    
    def test_trade_provider_no_configuration(self):
        """Test trade provider creation with no configuration."""
        config = {}
        factory = ProviderFactory(config)
        
        with pytest.raises(ValueError) as exc_info:
            factory.create_trade_provider()
        
        assert "No trade provider specified in configuration" in str(exc_info.value)
    
    def test_provider_override(self):
        """Test provider creation with name override."""
        config = {
            "providers": {
                "data": {"primary": "alpaca"}
            }
        }
        
        factory = ProviderFactory(config)
        
        # Override with different provider
        with pytest.raises(NotImplementedError) as exc_info:
            factory.create_data_provider("gemini")
        
        assert "Data provider 'gemini' not yet implemented" in str(exc_info.value)
    
    def test_get_available_providers(self):
        """Test getting available providers information."""
        config = {
            "providers": {
                "data": {
                    "primary": "alpaca",
                    "secondary": "gemini"
                },
                "trade": {
                    "primary": "alpaca"
                }
            }
        }
        
        factory = ProviderFactory(config)
        available = factory.get_available_providers()
        
        assert available["data_providers"] == []  # Empty until implementations added
        assert available["trade_providers"] == []  # Empty until implementations added
        assert available["configured"]["data_primary"] == "alpaca"
        assert available["configured"]["data_secondary"] == "gemini"
        assert available["configured"]["trade_primary"] == "alpaca"


class TestDataProviderFactory:
    """Test cases for specialized DataProviderFactory."""
    
    def test_data_factory_initialization(self):
        """Test DataProviderFactory initialization."""
        config = {
            "providers": {
                "data": {
                    "primary": "alpaca",
                    "secondary": "gemini"
                }
            }
        }
        
        factory = DataProviderFactory(config)
        
        assert factory.config == config
        assert isinstance(factory.factory, ProviderFactory)
    
    def test_primary_provider_creation(self):
        """Test primary data provider creation."""
        config = {
            "providers": {
                "data": {"primary": "alpaca"}
            }
        }
        
        factory = DataProviderFactory(config)
        
        with pytest.raises(NotImplementedError):
            factory.create_primary_provider()
    
    def test_secondary_provider_creation(self):
        """Test secondary data provider creation."""
        config = {
            "providers": {
                "data": {
                    "primary": "alpaca",
                    "secondary": "gemini"
                }
            }
        }
        
        factory = DataProviderFactory(config)
        
        # Should return None since provider not implemented
        secondary = factory.create_secondary_provider()
        assert secondary is None
    
    def test_secondary_provider_not_configured(self):
        """Test secondary provider when not configured."""
        config = {
            "providers": {
                "data": {"primary": "alpaca"}
            }
        }
        
        factory = DataProviderFactory(config)
        secondary = factory.create_secondary_provider()
        
        assert secondary is None
    
    @patch('src.common.provider_factory.ProviderFactory.create_data_provider')
    def test_secondary_provider_fallback(self, mock_create):
        """Test secondary provider creation with mock."""
        config = {
            "providers": {
                "data": {
                    "primary": "alpaca",
                    "secondary": "gemini"
                }
            }
        }
        
        # Mock the provider creation
        mock_provider = Mock()
        mock_create.return_value = mock_provider
        
        factory = DataProviderFactory(config)
        secondary = factory.create_secondary_provider()
        
        assert secondary == mock_provider
        mock_create.assert_called_once_with("gemini")


class TestTradeProviderFactory:
    """Test cases for specialized TradeProviderFactory."""
    
    def test_trade_factory_initialization(self):
        """Test TradeProviderFactory initialization."""
        config = {
            "providers": {
                "trade": {"primary": "alpaca"}
            }
        }
        
        factory = TradeProviderFactory(config)
        
        assert factory.config == config
        assert isinstance(factory.factory, ProviderFactory)
    
    def test_paper_trading_validation_disabled(self):
        """Test validation when paper trading is disabled."""
        config = {
            "providers": {
                "trade": {
                    "primary": "alpaca",
                    "paper_trading": False
                }
            },
            "risk": {
                "limits": {
                    "max_drawdown": 0.02,
                    "daily_loss_limit": 1000
                }
            }
        }
        
        factory = TradeProviderFactory(config)
        
        # Should not raise exception since risk config is present
        with pytest.raises(NotImplementedError):  # Provider not implemented
            factory.create_primary_provider()
    
    def test_live_trading_validation_missing_risk_config(self):
        """Test validation error when risk config is missing for live trading."""
        config = {
            "providers": {
                "trade": {
                    "primary": "alpaca",
                    "paper_trading": False
                }
            }
            # Missing risk configuration
        }
        
        factory = TradeProviderFactory(config)
        
        with pytest.raises(ValueError) as exc_info:
            factory.create_primary_provider()
        
        assert "Risk management configuration required for live trading" in str(exc_info.value)
    
    def test_live_trading_validation_missing_limits(self):
        """Test validation error when position limits are missing."""
        config = {
            "providers": {
                "trade": {
                    "primary": "alpaca",
                    "paper_trading": False
                }
            },
            "risk": {
                "limits": {
                    "max_drawdown": 0.02
                    # Missing daily_loss_limit
                }
            }
        }
        
        factory = TradeProviderFactory(config)
        
        with pytest.raises(ValueError) as exc_info:
            factory.create_primary_provider()
        
        assert "Position limits required for live trading" in str(exc_info.value)
    
    def test_paper_trading_default(self):
        """Test that paper trading defaults to True."""
        config = {
            "providers": {
                "trade": {"primary": "alpaca"}
                # No paper_trading setting - should default to True
            }
        }
        
        factory = TradeProviderFactory(config)
        
        # Should not raise validation error since paper trading is default
        with pytest.raises(NotImplementedError):  # Provider not implemented
            factory.create_primary_provider()
    
    @patch('src.common.provider_factory.ProviderFactory.create_trade_provider')
    def test_successful_provider_creation(self, mock_create):
        """Test successful trade provider creation with validation."""
        config = {
            "providers": {
                "trade": {
                    "primary": "alpaca",
                    "paper_trading": False
                }
            },
            "risk": {
                "limits": {
                    "max_drawdown": 0.02,
                    "daily_loss_limit": 1000
                }
            }
        }
        
        # Mock the provider creation
        mock_provider = Mock()
        mock_create.return_value = mock_provider
        
        factory = TradeProviderFactory(config)
        provider = factory.create_primary_provider()
        
        assert provider == mock_provider
        mock_create.assert_called_once()


class TestFactoryErrorHandling:
    """Test error handling in factory classes."""
    
    def test_invalid_configuration_structure(self):
        """Test handling of invalid configuration structure."""
        # Test with None config
        factory = ProviderFactory(None)
        
        with pytest.raises(ValueError):
            factory.create_data_provider()
    
    def test_missing_credentials(self):
        """Test handling of missing credentials configuration."""
        config = {
            "providers": {
                "data": {"primary": "alpaca"}
            }
            # Missing credentials section
        }
        
        factory = ProviderFactory(config)
        provider_config = factory._get_provider_config("alpaca")
        
        # Should handle missing credentials gracefully
        assert provider_config["credentials"] == {}
    
    def test_complex_configuration_extraction(self):
        """Test configuration extraction with complex nested structure."""
        config = {
            "providers": {
                "data": {
                    "primary": "alpaca",
                    "secondary": "gemini"
                },
                "trade": {
                    "primary": "alpaca",
                    "paper_trading": True
                }
            },
            "credentials": {
                "alpaca": {
                    "api_key": "${ALPACA_API_KEY}",
                    "secret": "${ALPACA_SECRET}",
                    "base_url": "https://paper-api.alpaca.markets"
                },
                "gemini": {
                    "api_key": "${GEMINI_API_KEY}",
                    "secret": "${GEMINI_SECRET}",
                    "sandbox": True
                }
            },
            "trading": {
                "max_position_size": 10000,
                "default_order_type": "market"
            },
            "risk": {
                "limits": {
                    "max_drawdown": 0.05,
                    "daily_loss_limit": 5000,
                    "max_positions": 10
                }
            }
        }
        
        factory = ProviderFactory(config)
        
        # Test alpaca configuration
        alpaca_config = factory._get_provider_config("alpaca")
        assert alpaca_config["credentials"]["api_key"] == "${ALPACA_API_KEY}"
        assert alpaca_config["trading"]["max_position_size"] == 10000
        assert alpaca_config["paper_trading"] is True
        
        # Test gemini configuration
        gemini_config = factory._get_provider_config("gemini")
        assert gemini_config["credentials"]["sandbox"] is True
        assert gemini_config["trading"]["default_order_type"] == "market"


class TestFactoryIntegration:
    """Integration tests for factory classes."""
    
    def test_data_factory_integration(self):
        """Test integration between DataProviderFactory and base factory."""
        config = {
            "providers": {
                "data": {
                    "primary": "alpaca",
                    "secondary": "gemini"
                }
            },
            "credentials": {
                "alpaca": {"api_key": "test"},
                "gemini": {"api_key": "test"}
            }
        }
        
        data_factory = DataProviderFactory(config)
        
        # Test that methods delegate to base factory correctly
        available = data_factory.factory.get_available_providers()
        assert available["configured"]["data_primary"] == "alpaca"
        assert available["configured"]["data_secondary"] == "gemini"
    
    def test_trade_factory_integration(self):
        """Test integration between TradeProviderFactory and base factory."""
        config = {
            "providers": {
                "trade": {
                    "primary": "alpaca",
                    "paper_trading": True
                }
            },
            "credentials": {
                "alpaca": {"api_key": "test"}
            },
            "risk": {
                "limits": {
                    "max_drawdown": 0.02,
                    "daily_loss_limit": 1000
                }
            }
        }
        
        trade_factory = TradeProviderFactory(config)
        
        # Test that validation works with base factory integration
        available = trade_factory.factory.get_available_providers()
        assert available["configured"]["trade_primary"] == "alpaca"