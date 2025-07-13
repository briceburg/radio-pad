"""
Shared WebSocket utilities for radio-pad components.
Provides common connection, reconnection, and message handling patterns.
"""
import asyncio
import logging
import websockets
from typing import Callable, Optional, Any
from .protocol import MessageProtocol, Events


class WebSocketManager:
    """Manages WebSocket connections with automatic reconnection."""
    
    def __init__(self, url: str, message_handler: Callable[[str, Any], None], 
                 user_agent: Optional[str] = None, reconnect_delay: int = 5):
        self.url = url
        self.message_handler = message_handler
        self.user_agent = user_agent
        self.reconnect_delay = reconnect_delay
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.is_connected = False
        
    async def connect_loop(self):
        """Main connection loop with automatic reconnection."""
        if not self.url:
            logging.info("WebSocket URL is empty, skipping connection.")
            return
            
        while True:
            try:
                headers = {}
                if self.user_agent:
                    headers["User-Agent"] = self.user_agent
                    
                async with websockets.connect(self.url, extra_headers=headers) as ws:
                    logging.info(f"WebSocket connected to: {self.url}")
                    self.websocket = ws
                    self.is_connected = True
                    
                    async for message in ws:
                        event, data = MessageProtocol.parse_message(message)
                        if event:
                            await self.message_handler(event, data)
                        else:
                            logging.warning(f"Invalid message received: {message}")
                            
            except (ConnectionRefusedError, OSError) as e:
                logging.warning(f"Failed to connect to {self.url}: {e}")
            except Exception as e:
                logging.error(f"Unexpected WebSocket error: {e}")
            finally:
                self.is_connected = False
                self.websocket = None
                
            logging.info(f"Reconnecting to WebSocket in {self.reconnect_delay}s...")
            await asyncio.sleep(self.reconnect_delay)
    
    async def send_event(self, event: str, data: Any = None) -> bool:
        """Send an event through the WebSocket. Returns success status."""
        if not self.is_connected or not self.websocket:
            logging.warning("WebSocket not connected, cannot send message")
            return False
            
        try:
            message = MessageProtocol.create_message(event, data)
            await self.websocket.send(message)
            return True
        except Exception as e:
            logging.error(f"Failed to send WebSocket message: {e}")
            return False
    
    async def close(self):
        """Close the WebSocket connection."""
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logging.error(f"Error closing WebSocket: {e}")
            finally:
                self.websocket = None
                self.is_connected = False


class BroadcastManager:
    """Manages broadcasting messages to multiple targets."""
    
    def __init__(self):
        self.targets = {}
        
    def add_target(self, name: str, send_func: Callable[[str, Any], None]):
        """Add a broadcast target."""
        self.targets[name] = send_func
        
    def remove_target(self, name: str):
        """Remove a broadcast target."""
        self.targets.pop(name, None)
        
    async def broadcast(self, event: str, data: Any = None, audience: str = "all"):
        """Broadcast an event to specified audience."""
        message = MessageProtocol.create_message(event, data)
        
        targets_to_use = []
        if audience == "all":
            targets_to_use = list(self.targets.values())
        else:
            target_func = self.targets.get(audience)
            if target_func:
                targets_to_use = [target_func]
        
        for send_func in targets_to_use:
            try:
                await send_func(message)
            except Exception as e:
                logging.error(f"Failed to broadcast to target: {e}")