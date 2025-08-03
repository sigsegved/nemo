"""
Configuration system for the Nemo trading bot.

This module provides a robust configuration loading and validation system
that supports YAML files, environment variable overrides, and type-safe
access to configuration values.
"""

import yaml
import os
from typing import Dict, Any, List
from decimal import Decimal
from dataclasses import dataclass


@dataclass
class ProviderConfig:
    """Configuration for a specific provider."""
    api_key: str
    api_secret: str
    ws_url: str = ""
    rest_url: str = ""


@dataclass  
class Config:
    """Main configuration class."""
    # Provider selection
    data_provider: str
    trade_provider: str
    symbols: List[str]
    
    # Strategy parameters
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
    providers: Dict[str, ProviderConfig]
    
    @classmethod
    def load_from_file(cls, config_path: str) -> 'Config':
        """Load configuration from YAML file."""
        with open(config_path, 'r') as f:
            raw_config = yaml.safe_load(f)
        
        # Apply environment variable overrides
        cls._apply_env_overrides(raw_config)
        
        # Validate and create config instance
        return cls._from_dict(raw_config)
    
    @staticmethod
    def _apply_env_overrides(config: Dict[str, Any]) -> None:
        """Apply environment variable overrides for sensitive data."""
        # Override API keys from environment
        for provider_name in config.get('PROVIDERS', {}):
            provider_config = config['PROVIDERS'][provider_name]
            api_key_env = f"{provider_name.upper()}_API_KEY"
            api_secret_env = f"{provider_name.upper()}_API_SECRET"
            
            if api_key_env in os.environ:
                provider_config['API_KEY'] = os.environ[api_key_env]
            if api_secret_env in os.environ:
                provider_config['API_SECRET'] = os.environ[api_secret_env]
    
    @classmethod
    def _from_dict(cls, config_dict: Dict[str, Any]) -> 'Config':
        """Create Config instance from dictionary with validation."""
        # Validate required fields
        required_fields = [
            'DATA_PROVIDER', 'TRADE_PROVIDER', 'SYMBOLS', 'PRICE_DEV',
            'VOL_MULT', 'LLM_CONF', 'MAX_GROSS_PCT_EQUITY', 'MAX_LEVERAGE',
            'STOP_LOSS_PCT', 'COOLDOWN_HR', 'OPENAI_MODEL'
        ]
        
        for field in required_fields:
            if field not in config_dict:
                raise ValueError(f"Missing required configuration field: {field}")
        
        # Convert provider configs
        providers = {}
        for name, provider_data in config_dict.get('PROVIDERS', {}).items():
            if not isinstance(provider_data, dict):
                raise ValueError(f"Provider configuration for '{name}' must be a dictionary")
            
            providers[name] = ProviderConfig(
                api_key=provider_data.get('API_KEY', ''),
                api_secret=provider_data.get('API_SECRET', ''),
                ws_url=provider_data.get('WS_URL', ''),
                rest_url=provider_data.get('REST_URL', '')
            )
        
        # Validate and convert types
        try:
            symbols = config_dict['SYMBOLS']
            if not isinstance(symbols, list):
                raise ValueError("SYMBOLS must be a list")
            
            price_dev = Decimal(str(config_dict['PRICE_DEV']))
            llm_conf = Decimal(str(config_dict['LLM_CONF']))
            max_gross_pct_equity = Decimal(str(config_dict['MAX_GROSS_PCT_EQUITY']))
            stop_loss_pct = Decimal(str(config_dict['STOP_LOSS_PCT']))
            
            vol_mult = int(config_dict['VOL_MULT'])
            max_leverage = int(config_dict['MAX_LEVERAGE'])
            cooldown_hr = int(config_dict['COOLDOWN_HR'])
            
        except (ValueError, TypeError) as e:
            raise ValueError(f"Configuration validation error: {e}")
        
        return cls(
            data_provider=config_dict['DATA_PROVIDER'],
            trade_provider=config_dict['TRADE_PROVIDER'],
            symbols=symbols,
            price_dev=price_dev,
            vol_mult=vol_mult,
            llm_conf=llm_conf,
            max_gross_pct_equity=max_gross_pct_equity,
            max_leverage=max_leverage,
            stop_loss_pct=stop_loss_pct,
            cooldown_hr=cooldown_hr,
            openai_model=config_dict['OPENAI_MODEL'],
            providers=providers
        )