"""
Gemini trade provider implementation.

This module implements order execution and portfolio management
functionality for the Gemini cryptocurrency exchange.
"""

import hashlib
import hmac
import base64
import time
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional
import aiohttp

from ...common.provider_base import TradeProvider
from ...common.models import OrderAck, Position

logger = logging.getLogger(__name__)


class GeminiTradeProvider(TradeProvider):
    """Gemini trade provider implementation with REST API integration."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Gemini trade provider.
        
        Args:
            config: Provider-specific configuration containing API credentials
        """
        self.config = config
        self.api_key = config.get("API_KEY", "")
        self.api_secret = config.get("API_SECRET", "")
        # Use sandbox by default for testing, production URL can be overridden in config
        self.rest_url = config.get("REST_URL", "https://api.sandbox.gemini.com")
        self.session: Optional[aiohttp.ClientSession] = None
        self.connected = False
    
    async def connect(self) -> None:
        """Establish connection to trading API."""
        try:
            logger.info("Connecting to Gemini REST API")
            
            if not self.api_key or not self.api_secret:
                raise ValueError("API_KEY and API_SECRET must be configured")
            
            # Create aiohttp session with timeout
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            # Test connection with account info request
            await self._test_connection()
            
            self.connected = True
            logger.info("Successfully connected to Gemini REST API")
            
        except Exception as e:
            logger.error(f"Failed to connect to Gemini REST API: {e}")
            if self.session:
                await self.session.close()
                self.session = None
            raise
    
    async def submit_order(
        self, symbol: str, side: str, amount: Decimal, tif: str = "IOC"
    ) -> OrderAck:
        """Submit an order and return acknowledgment.
        
        Args:
            symbol: Trading symbol (e.g., 'BTC-GUSD-PERP')
            side: Order side ('buy' or 'sell')  
            amount: Dollar amount of the trade
            tif: Time In Force - 'IOC' (Immediate or Cancel)
        
        Returns:
            OrderAck: Order acknowledgment with status and details
        """
        if not self.connected or not self.session:
            raise RuntimeError("Not connected to REST API")
        
        try:
            # Convert symbol to Gemini format
            gemini_symbol = symbol.replace("-", "").lower()
            
            # Get current market price to calculate quantity
            price = await self._get_market_price(gemini_symbol)
            quantity = amount / price
            
            # Prepare order payload
            payload = {
                "request": "/v1/order/new",
                "nonce": str(int(time.time() * 1000)),
                "symbol": gemini_symbol,
                "amount": str(quantity),
                "price": str(price),
                "side": side,
                "type": "exchange limit",  # Use limit order for IOC
                "options": ["immediate-or-cancel"] if tif == "IOC" else []
            }
            
            # Make authenticated request
            response_data = await self._make_authenticated_request("/v1/order/new", payload)
            
            # Create order acknowledgment
            order_ack = OrderAck(
                order_id=str(response_data.get("order_id", "")),
                symbol=symbol,
                side=side,
                amount=amount,
                status=self._map_gemini_status(response_data.get("is_live", False)),
                timestamp=datetime.now(),
                tif=tif,
                message=f"Gemini order submitted: {response_data.get('order_id', '')}"
            )
            
            logger.info(f"Order submitted: {order_ack.order_id} for {symbol}")
            return order_ack
            
        except Exception as e:
            logger.error(f"Failed to submit order: {e}")
            # Return failed order acknowledgment
            return OrderAck(
                order_id="failed",
                symbol=symbol,
                side=side,
                amount=amount,
                status="rejected",
                timestamp=datetime.now(),
                tif=tif,
                message=f"Order failed: {str(e)}"
            )
    
    async def close_position(self, symbol: str) -> OrderAck:
        """Close existing position for symbol."""
        if not self.connected:
            raise RuntimeError("Not connected to REST API")
        
        try:
            # Get current position
            positions = await self.fetch_positions()
            target_position = None
            
            for position in positions:
                if position.symbol == symbol:
                    target_position = position
                    break
            
            if not target_position:
                return OrderAck(
                    order_id="no_position",
                    symbol=symbol,
                    side="close",
                    amount=Decimal("0"),
                    status="rejected",
                    timestamp=datetime.now(),
                    message=f"No position found for {symbol}"
                )
            
            # Calculate opposite side and amount
            close_side = "sell" if target_position.side == "long" else "buy"
            close_amount = abs(target_position.size * target_position.current_price)
            
            # Submit closing order
            return await self.submit_order(symbol, close_side, close_amount, "IOC")
            
        except Exception as e:
            logger.error(f"Failed to close position for {symbol}: {e}")
            return OrderAck(
                order_id="close_failed",
                symbol=symbol,
                side="close",
                amount=Decimal("0"),
                status="rejected",
                timestamp=datetime.now(),
                message=f"Close position failed: {str(e)}"
            )
    
    async def fetch_positions(self) -> List[Position]:
        """Fetch all current positions."""
        if not self.connected:
            raise RuntimeError("Not connected to REST API")
        
        try:
            # Get account balances
            payload = {
                "request": "/v1/balances",
                "nonce": str(int(time.time() * 1000))
            }
            
            balances = await self._make_authenticated_request("/v1/balances", payload)
            positions = []
            
            # Convert balances to positions for non-zero amounts
            for balance in balances:
                if isinstance(balance, dict):
                    currency = balance.get("currency", "").upper()
                    amount = Decimal(str(balance.get("amount", "0")))
                    
                    if amount > 0:
                        # Get current price for this currency
                        try:
                            symbol_pair = f"{currency}GUSD"
                            current_price = await self._get_market_price(symbol_pair.lower())
                            
                            position = Position(
                                symbol=f"{currency}-GUSD-PERP",
                                side="long",
                                size=amount,
                                entry_price=current_price,  # Approximate
                                current_price=current_price,
                                unrealized_pnl=Decimal("0"),  # Would need historical data
                                timestamp=datetime.now()
                            )
                            positions.append(position)
                            
                        except Exception as e:
                            logger.warning(f"Could not get price for {currency}: {e}")
            
            return positions
            
        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}")
            return []
    
    async def get_account_equity(self) -> Decimal:
        """Get current account equity."""
        if not self.connected:
            raise RuntimeError("Not connected to REST API")
        
        try:
            # Get account balances
            payload = {
                "request": "/v1/balances",
                "nonce": str(int(time.time() * 1000))
            }
            
            balances = await self._make_authenticated_request("/v1/balances", payload)
            total_equity = Decimal("0")
            
            # Sum up all balances converted to USD
            for balance in balances:
                if isinstance(balance, dict):
                    currency = balance.get("currency", "").upper()
                    amount = Decimal(str(balance.get("amount", "0")))
                    
                    if amount > 0:
                        if currency == "USD" or currency == "GUSD":
                            # Direct USD value
                            total_equity += amount
                        else:
                            # Convert to USD using current price
                            try:
                                symbol_pair = f"{currency}USD"
                                price = await self._get_market_price(symbol_pair.lower())
                                total_equity += amount * price
                            except Exception as e:
                                logger.warning(f"Could not convert {currency} to USD: {e}")
            
            return total_equity
            
        except Exception as e:
            logger.error(f"Failed to get account equity: {e}")
            return Decimal("0")
    
    async def disconnect(self) -> None:
        """Clean up and disconnect from trading API."""
        logger.info("Disconnecting from Gemini REST API")
        self.connected = False
        
        if self.session:
            await self.session.close()
            self.session = None
        
        logger.info("Disconnected from Gemini REST API")
    
    async def _test_connection(self) -> None:
        """Test API connection with a simple request."""
        payload = {
            "request": "/v1/account",
            "nonce": str(int(time.time() * 1000))
        }
        
        await self._make_authenticated_request("/v1/account", payload)
    
    async def _make_authenticated_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make authenticated request to Gemini API."""
        if not self.session:
            raise RuntimeError("No active session")
        
        # Encode payload
        json_payload = json.dumps(payload)
        encoded_payload = base64.b64encode(json_payload.encode())
        
        # Create signature
        signature = hmac.new(
            self.api_secret.encode(),
            encoded_payload,
            hashlib.sha384
        ).hexdigest()
        
        # Headers
        headers = {
            "Content-Type": "text/plain",
            "Content-Length": "0",
            "X-GEMINI-APIKEY": self.api_key,
            "X-GEMINI-PAYLOAD": encoded_payload.decode(),
            "X-GEMINI-SIGNATURE": signature
        }
        
        url = f"{self.rest_url}{endpoint}"
        
        async with self.session.post(url, headers=headers) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"API request failed: {response.status} - {error_text}")
            
            return await response.json()
    
    async def _get_market_price(self, symbol: str) -> Decimal:
        """Get current market price for a symbol."""
        if not self.session:
            raise RuntimeError("No active session")
        
        url = f"{self.rest_url}/v1/pubticker/{symbol}"
        
        async with self.session.get(url) as response:
            if response.status != 200:
                raise RuntimeError(f"Failed to get price for {symbol}")
            
            data = await response.json()
            return Decimal(str(data.get("last", "0")))
    
    def _map_gemini_status(self, is_live: bool) -> str:
        """Map Gemini order status to our standard status."""
        return "pending" if is_live else "filled"