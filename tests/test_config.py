"""
Comprehensive tests for the configuration system.

Tests cover:
- YAML configuration loading and validation
- Environment variable overrides and substitution
- Type conversion and validation
- Error handling for malformed configurations
- Provider configuration validation
- Financial precision with Decimal types
"""

import os
import tempfile
import pytest
from pathlib import Path
from decimal import Decimal
from typing import Dict, Any

from src.common.config import Config, ProviderConfig, load_config


class TestProviderConfig:
    """Test cases for ProviderConfig."""
    
    def test_provider_config_creation(self):
        """Test basic ProviderConfig creation."""
        config = ProviderConfig(
            api_key="test_key",
            api_secret="test_secret",
            ws_url="wss://test.com",
            rest_url="https://test.com"
        )
        
        assert config.api_key == "test_key"
        assert config.api_secret == "test_secret"
        assert config.ws_url == "wss://test.com"
        assert config.rest_url == "https://test.com"
    
    def test_provider_config_defaults(self):
        """Test ProviderConfig with default values."""
        config = ProviderConfig(
            api_key="test_key",
            api_secret="test_secret"
        )
        
        assert config.api_key == "test_key"
        assert config.api_secret == "test_secret"
        assert config.ws_url == ""
        assert config.rest_url == ""
    
    def test_provider_config_empty_credentials_allowed(self):
        """Test that empty credentials are allowed (for env var population)."""
        config = ProviderConfig(
            api_key="",
            api_secret=""
        )
        
        assert config.api_key == ""
        assert config.api_secret == ""
    
    def test_provider_config_validation_for_use(self):
        """Test runtime validation for provider usage."""
        config = ProviderConfig(api_key="", api_secret="")
        
        with pytest.raises(ValueError, match="API key is required"):
            config.validate_for_use()
        
        config.api_key = "test_key"
        with pytest.raises(ValueError, match="API secret is required"):
            config.validate_for_use()
        
        config.api_secret = "test_secret"
        config.validate_for_use()  # Should not raise


class TestConfig:
    """Test cases for Config class."""
    
    @pytest.fixture
    def valid_config_dict(self) -> Dict[str, Any]:
        """Provide a valid configuration dictionary."""
        return {
            'DATA_PROVIDER': 'gemini',
            'TRADE_PROVIDER': 'gemini',
            'SYMBOLS': ['BTC-GUSD-PERP', 'ETH-GUSD-PERP'],
            'PRICE_DEV': 0.01,
            'VOL_MULT': 2,
            'LLM_CONF': 0.85,
            'MAX_GROSS_PCT_EQUITY': 0.95,
            'MAX_LEVERAGE': 3,
            'STOP_LOSS_PCT': 0.05,
            'COOLDOWN_HR': 24,
            'OPENAI_MODEL': 'gpt-4',
            'PROVIDERS': {
                'gemini': {
                    'API_KEY': 'test_gemini_key',
                    'API_SECRET': 'test_gemini_secret',
                    'WS_URL': 'wss://api.gemini.com',
                    'REST_URL': 'https://api.gemini.com'
                }
            }
        }
    
    @pytest.fixture
    def valid_yaml_content(self) -> str:
        """Provide valid YAML configuration content."""
        return """
DATA_PROVIDER: gemini
TRADE_PROVIDER: gemini
SYMBOLS: ["BTC-GUSD-PERP", "ETH-GUSD-PERP", "SOL-GUSD-PERP"]
PRICE_DEV: 0.01
VOL_MULT: 2
LLM_CONF: 0.85
MAX_GROSS_PCT_EQUITY: 0.95
MAX_LEVERAGE: 3
STOP_LOSS_PCT: 0.05
COOLDOWN_HR: 24
OPENAI_MODEL: gpt-4

PROVIDERS:
  gemini:
    API_KEY: test_key
    API_SECRET: test_secret
    WS_URL: wss://api.gemini.com/v1/marketdata
    REST_URL: https://api.gemini.com/v1
  alpaca:
    API_KEY: alpaca_key
    API_SECRET: alpaca_secret
    WS_URL: wss://stream.data.alpaca.markets/v2/iex
    REST_URL: https://paper-api.alpaca.markets
"""
    
    def test_config_from_dict_valid(self, valid_config_dict):
        """Test creating Config from valid dictionary."""
        config = Config._from_dict(valid_config_dict)
        
        assert config.data_provider == 'gemini'
        assert config.trade_provider == 'gemini'
        assert config.symbols == ['BTC-GUSD-PERP', 'ETH-GUSD-PERP']
        assert config.price_dev == Decimal('0.01')
        assert config.vol_mult == 2
        assert config.llm_conf == Decimal('0.85')
        assert config.max_gross_pct_equity == Decimal('0.95')
        assert config.max_leverage == 3
        assert config.stop_loss_pct == Decimal('0.05')
        assert config.cooldown_hr == 24
        assert config.openai_model == 'gpt-4'
        
        # Test provider configuration
        assert 'gemini' in config.providers
        gemini_config = config.providers['gemini']
        assert gemini_config.api_key == 'test_gemini_key'
        assert gemini_config.api_secret == 'test_gemini_secret'
    
    def test_config_empty_symbols_validation(self, valid_config_dict):
        """Test Config creation with empty symbols list."""
        valid_config_dict['SYMBOLS'] = []
        
        with pytest.raises(ValueError, match="At least one symbol must be specified"):
            Config._from_dict(valid_config_dict)
    
    def test_config_invalid_symbols_format(self, valid_config_dict):
        """Test Config creation with invalid symbol format."""
        valid_config_dict['SYMBOLS'] = ['BTC-USD', 'invalid symbol!']
        
        with pytest.raises(ValueError, match="Invalid symbol format"):
            Config._from_dict(valid_config_dict)
    
    def test_config_negative_financial_params(self, valid_config_dict):
        """Test Config creation with invalid financial parameters."""
        valid_config_dict['PRICE_DEV'] = -0.01
        
        with pytest.raises(ValueError, match="Price deviation must be positive"):
            Config._from_dict(valid_config_dict)
    
    def test_config_invalid_provider_reference(self, valid_config_dict):
        """Test Config creation with provider not in providers dict."""
        valid_config_dict['DATA_PROVIDER'] = 'nonexistent'
        
        with pytest.raises(ValueError, match="Data provider 'nonexistent' not found"):
            Config._from_dict(valid_config_dict)
    
    def test_config_load_from_yaml_file(self, valid_yaml_content):
        """Test loading configuration from YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(valid_yaml_content)
            temp_path = f.name
        
        try:
            config = Config.load_from_file(temp_path)
            
            assert config.data_provider == 'gemini'
            assert config.trade_provider == 'gemini'
            assert len(config.symbols) == 3
            assert 'BTC-GUSD-PERP' in config.symbols
            assert config.price_dev == Decimal('0.01')
            assert len(config.providers) == 2
            assert 'gemini' in config.providers
            assert 'alpaca' in config.providers
        finally:
            os.unlink(temp_path)
    
    def test_config_file_not_found(self):
        """Test loading configuration from non-existent file."""
        with pytest.raises(FileNotFoundError):
            Config.load_from_file('non_existent_file.yaml')
    
    def test_config_invalid_yaml(self):
        """Test loading configuration from invalid YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError, match="Invalid YAML"):
                Config.load_from_file(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_env_variable_overrides(self, valid_yaml_content):
        """Test environment variable overrides for API keys."""
        # Set environment variables
        os.environ['GEMINI_API_KEY'] = 'env_gemini_key'
        os.environ['GEMINI_API_SECRET'] = 'env_gemini_secret'
        os.environ['ALPACA_API_KEY'] = 'env_alpaca_key'
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                f.write(valid_yaml_content)
                temp_path = f.name
            
            try:
                config = Config.load_from_file(temp_path)
                
                # Verify environment variables override YAML values
                assert config.providers['gemini'].api_key == 'env_gemini_key'
                assert config.providers['gemini'].api_secret == 'env_gemini_secret'
                assert config.providers['alpaca'].api_key == 'env_alpaca_key'
                # alpaca secret should remain from YAML since no env var set
                assert config.providers['alpaca'].api_secret == 'alpaca_secret'
            finally:
                os.unlink(temp_path)
        finally:
            # Clean up environment variables
            for var in ['GEMINI_API_KEY', 'GEMINI_API_SECRET', 'ALPACA_API_KEY']:
                if var in os.environ:
                    del os.environ[var]
    
    def test_env_variable_substitution(self):
        """Test ${VAR:-default} pattern substitution."""
        os.environ['TEST_PROVIDER'] = 'test_provider'
        
        yaml_content = """
DATA_PROVIDER: ${TEST_PROVIDER:-default_provider}
TRADE_PROVIDER: ${MISSING_VAR:-fallback_provider}
SYMBOLS: ["BTC-GUSD-PERP"]
PRICE_DEV: 0.01
VOL_MULT: 2
LLM_CONF: 0.85
MAX_GROSS_PCT_EQUITY: 0.95
MAX_LEVERAGE: 3
STOP_LOSS_PCT: 0.05
COOLDOWN_HR: 24
OPENAI_MODEL: gpt-4

PROVIDERS:
  test_provider:
    API_KEY: test_key
    API_SECRET: test_secret
  fallback_provider:
    API_KEY: fallback_key
    API_SECRET: fallback_secret
"""
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                f.write(yaml_content)
                temp_path = f.name
            
            try:
                config = Config.load_from_file(temp_path)
                
                # Check substitutions
                assert config.data_provider == 'test_provider'  # From env var
                assert config.trade_provider == 'fallback_provider'  # From default
            finally:
                os.unlink(temp_path)
        finally:
            if 'TEST_PROVIDER' in os.environ:
                del os.environ['TEST_PROVIDER']
    
    def test_decimal_precision(self, valid_config_dict):
        """Test that financial values maintain decimal precision."""
        config = Config._from_dict(valid_config_dict)
        
        # Test that decimal values are preserved
        assert isinstance(config.price_dev, Decimal)
        assert isinstance(config.llm_conf, Decimal)
        assert isinstance(config.max_gross_pct_equity, Decimal)
        assert isinstance(config.stop_loss_pct, Decimal)
        
        # Test arithmetic precision
        result = config.max_gross_pct_equity * config.stop_loss_pct
        assert isinstance(result, Decimal)
        assert result == Decimal('0.0475')  # 0.95 * 0.05
    
    def test_trading_validation(self, valid_config_dict):
        """Test trading-specific validation."""
        config = Config._from_dict(valid_config_dict)
        
        # Should pass with valid credentials
        config.validate_for_trading()
        
        # Should fail with empty credentials
        config.providers['gemini'].api_key = ""
        with pytest.raises(ValueError, match="Data provider 'gemini' configuration invalid"):
            config.validate_for_trading()


class TestConfigIntegration:
    """Integration tests for configuration system."""
    
    def test_complete_config_workflow(self):
        """Test complete configuration loading workflow."""
        yaml_content = """
DATA_PROVIDER: gemini
TRADE_PROVIDER: alpaca
SYMBOLS: ["BTC-GUSD-PERP"]
PRICE_DEV: 0.005
VOL_MULT: 3
LLM_CONF: 0.9
MAX_GROSS_PCT_EQUITY: 0.8
MAX_LEVERAGE: 2
STOP_LOSS_PCT: 0.03
COOLDOWN_HR: 12
OPENAI_MODEL: gpt-3.5-turbo

PROVIDERS:
  gemini:
    API_KEY: yaml_gemini_key
    API_SECRET: yaml_gemini_secret
    WS_URL: wss://api.gemini.com/v1/marketdata
    REST_URL: https://api.gemini.com/v1
  alpaca:
    API_KEY: yaml_alpaca_key
    API_SECRET: yaml_alpaca_secret
    WS_URL: wss://stream.data.alpaca.markets/v2/iex
    REST_URL: https://paper-api.alpaca.markets
"""
        
        # Set some environment variables
        os.environ['ALPACA_API_KEY'] = 'env_alpaca_key'
        os.environ['ALPACA_API_SECRET'] = 'env_alpaca_secret'
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                f.write(yaml_content)
                temp_path = f.name
            
            try:
                config = Config.load_from_file(temp_path)
                
                # Verify basic configuration
                assert config.data_provider == 'gemini'
                assert config.trade_provider == 'alpaca'
                assert config.symbols == ['BTC-GUSD-PERP']
                
                # Verify environment override worked
                assert config.providers['alpaca'].api_key == 'env_alpaca_key'
                assert config.providers['alpaca'].api_secret == 'env_alpaca_secret'
                
                # Verify YAML values for gemini (no env override)
                assert config.providers['gemini'].api_key == 'yaml_gemini_key'
                assert config.providers['gemini'].api_secret == 'yaml_gemini_secret'
                
                # Verify decimal types
                assert isinstance(config.price_dev, Decimal)
                assert config.price_dev == Decimal('0.005')
                
                # Test trading validation
                config.validate_for_trading()
                
            finally:
                os.unlink(temp_path)
        finally:
            # Clean up environment variables
            for var in ['ALPACA_API_KEY', 'ALPACA_API_SECRET']:
                if var in os.environ:
                    del os.environ[var]


class TestLoadConfigFunction:
    """Test the convenience load_config function."""
    
    def test_load_config_default_path(self):
        """Test load_config with default path."""
        # This test would require an actual config.yaml file
        # For now, just test that the function exists and handles missing files
        with pytest.raises(FileNotFoundError):
            load_config('nonexistent_config.yaml')
    
    def test_load_config_custom_path(self):
        """Test load_config with custom path."""
        yaml_content = """
DATA_PROVIDER: gemini
TRADE_PROVIDER: gemini
SYMBOLS: ["BTC-GUSD-PERP"]
PRICE_DEV: 0.01
VOL_MULT: 2
LLM_CONF: 0.85
MAX_GROSS_PCT_EQUITY: 0.95
MAX_LEVERAGE: 3
STOP_LOSS_PCT: 0.05
COOLDOWN_HR: 24
OPENAI_MODEL: gpt-4

PROVIDERS:
  gemini:
    API_KEY: test_key
    API_SECRET: test_secret
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            config = load_config(temp_path)
            assert config.data_provider == 'gemini'
            assert len(config.symbols) == 1
        finally:
            os.unlink(temp_path)