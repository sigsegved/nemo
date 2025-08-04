"""
Gemini data provider implementation.

This module implements the market data streaming and historical data
retrieval functionality for the Gemini cryptocurrency exchange.
"""

import asyncio
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import AsyncIterator, List, Dict, Any, Optional
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from ...common.provider_base import DataProvider
from ...common.models import TradeTick, MarketEvent

logger = logging.getLogger(__name__)


class GeminiDataProvider(DataProvider):
    """Gemini data provider implementation with WebSocket streaming."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Gemini data provider.
        
        Args:
            config: Provider-specific configuration containing WS_URL
        """
        self.config = config
        self.ws_url = config.get("WS_URL", "wss://api.gemini.com/v2/marketdata")
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.connected = False
        self.subscribed_symbols: List[str] = []
        self.subscribed_events: List[str] = []
        self._tick_queue: asyncio.Queue = asyncio.Queue()
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 5  # seconds
    
    async def connect(self) -> None:
        """Establish WebSocket connection to Gemini market data."""
        try:
            logger.info(f"Connecting to Gemini WebSocket: {self.ws_url}")
            self.websocket = await websockets.connect(self.ws_url)
            self.connected = True
            self._reconnect_attempts = 0
            logger.info("Successfully connected to Gemini WebSocket")
            
            # Start message handling task
            asyncio.create_task(self._handle_messages())
            
        except Exception as e:
            logger.error(f"Failed to connect to Gemini WebSocket: {e}")
            self.connected = False
            raise
    
    async def subscribe_trades(self, symbols: List[str]) -> None:
        """Subscribe to trade data for given symbols."""
        if not self.connected or not self.websocket:
            raise RuntimeError("Not connected to WebSocket")
        
        for symbol in symbols:
            try:
                # Gemini uses a different symbol format for WebSocket
                gemini_symbol = symbol.replace("-", "").lower()
                subscription = {
                    "type": "subscribe",
                    "subscriptions": [
                        {
                            "name": "l2_updates",
                            "symbols": [gemini_symbol]
                        }
                    ]
                }
                
                await self.websocket.send(json.dumps(subscription))
                self.subscribed_symbols.append(symbol)
                logger.info(f"Subscribed to trades for {symbol} (Gemini: {gemini_symbol})")
                
            except Exception as e:
                logger.error(f"Failed to subscribe to trades for {symbol}: {e}")
                raise
    
    async def subscribe_events(self, symbols: List[str]) -> None:
        """Subscribe to market events (mark-price, funding, liquidations)."""
        if not self.connected:
            raise RuntimeError("Not connected to WebSocket")
        
        # Gemini doesn't have the same event types as other exchanges
        # Store symbols for potential future use
        self.subscribed_events.extend(symbols)
        logger.info(f"Noted symbols for events: {symbols} (Gemini has limited event types)")
    
    async def iter_ticks(self) -> AsyncIterator[TradeTick]:
        """Async iterator yielding trade ticks from WebSocket stream."""
        while self.connected:
            try:
                # Wait for tick data with timeout
                tick = await asyncio.wait_for(self._tick_queue.get(), timeout=1.0)
                yield tick
            except asyncio.TimeoutError:
                # Continue if no data available
                continue
            except Exception as e:
                logger.error(f"Error in tick iteration: {e}")
                break
    
    async def iter_events(self) -> AsyncIterator[MarketEvent]:
        """Async iterator yielding market events."""
        while self.connected:
            try:
                # Wait for event data with timeout
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                yield event
            except asyncio.TimeoutError:
                # Continue if no data available
                continue
            except Exception as e:
                logger.error(f"Error in event iteration: {e}")
                break
    
    async def disconnect(self) -> None:
        """Clean up and disconnect from WebSocket."""
        logger.info("Disconnecting from Gemini WebSocket")
        self.connected = False
        
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
            finally:
                self.websocket = None
        
        logger.info("Disconnected from Gemini WebSocket")
    
    async def _handle_messages(self) -> None:
        """Handle incoming WebSocket messages."""
        if not self.websocket:
            return
        
        try:
            async for message in self.websocket:
                await self._process_message(message)
        except ConnectionClosed:
            logger.warning("WebSocket connection closed")
            await self._handle_reconnection()
        except WebSocketException as e:
            logger.error(f"WebSocket error: {e}")
            await self._handle_reconnection()
        except Exception as e:
            logger.error(f"Unexpected error in message handling: {e}")
            await self._handle_reconnection()
    
    async def _process_message(self, message: str) -> None:
        """Process individual WebSocket messages."""
        try:
            data = json.loads(message)
            
            # Handle different message types
            if data.get("type") == "l2_updates":
                await self._process_l2_update(data)
            elif data.get("type") == "trade":
                await self._process_trade(data)
            elif data.get("type") == "heartbeat":
                # Keep-alive message
                pass
            else:
                logger.debug(f"Unhandled message type: {data.get('type')}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def _process_l2_update(self, data: Dict[str, Any]) -> None:
        """Process Level 2 order book updates and extract trade-like data."""
        try:
            symbol = data.get("symbol", "").upper()
            # Convert back to standard format
            if symbol:
                # Map Gemini symbols back to our format
                symbol_map = {
                    "BTCGUSDPERP": "BTC-GUSD-PERP",
                    "ETHGUSDPERP": "ETH-GUSD-PERP", 
                    "SOLGUSDPERP": "SOL-GUSD-PERP",
                    "DOGEGUSDPERP": "DOGE-GUSD-PERP"
                }
                standard_symbol = symbol_map.get(symbol, symbol)
                
                changes = data.get("changes", [])
                for change in changes:
                    if len(change) >= 3:
                        side = change[0]  # "buy" or "sell"
                        price = Decimal(str(change[1]))
                        size = Decimal(str(change[2]))
                        
                        # Create a synthetic trade tick from L2 data
                        tick = TradeTick(
                            symbol=standard_symbol,
                            price=price,
                            size=size,
                            timestamp=datetime.now(),
                            side=side
                        )
                        
                        await self._tick_queue.put(tick)
                        
        except Exception as e:
            logger.error(f"Error processing L2 update: {e}")
    
    async def _process_trade(self, data: Dict[str, Any]) -> None:
        """Process trade messages."""
        try:
            symbol = data.get("symbol", "").upper()
            price = Decimal(str(data.get("price", "0")))
            size = Decimal(str(data.get("quantity", "0")))
            side = data.get("side", "buy")
            
            # Convert symbol format
            symbol_map = {
                "BTCGUSDPERP": "BTC-GUSD-PERP",
                "ETHGUSDPERP": "ETH-GUSD-PERP",
                "SOLGUSDPERP": "SOL-GUSD-PERP", 
                "DOGEGUSDPERP": "DOGE-GUSD-PERP"
            }
            standard_symbol = symbol_map.get(symbol, symbol)
            
            tick = TradeTick(
                symbol=standard_symbol,
                price=price,
                size=size,
                timestamp=datetime.now(),
                side=side
            )
            
            await self._tick_queue.put(tick)
            
        except Exception as e:
            logger.error(f"Error processing trade: {e}")
    
    async def _handle_reconnection(self) -> None:
        """Handle WebSocket reconnection with exponential backoff."""
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            self.connected = False
            return
        
        self._reconnect_attempts += 1
        delay = self._reconnect_delay * (2 ** (self._reconnect_attempts - 1))
        
        logger.info(f"Attempting reconnection {self._reconnect_attempts} in {delay} seconds")
        await asyncio.sleep(delay)
        
        try:
            await self.connect()
            # Re-subscribe to symbols if we were subscribed before
            if self.subscribed_symbols:
                await self.subscribe_trades(self.subscribed_symbols.copy())
        except Exception as e:
            logger.error(f"Reconnection attempt {self._reconnect_attempts} failed: {e}")
            await self._handle_reconnection()