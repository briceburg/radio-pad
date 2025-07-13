"""
Shared message protocol for radio-pad components.
Centralizes message format and validation.
"""
import json
from typing import Any, Dict, Optional, Tuple


class MessageProtocol:
    """Standard message protocol for radio-pad WebSocket communication."""
    
    @staticmethod
    def create_message(event: str, data: Any = None) -> str:
        """Create a standardized message."""
        return json.dumps({"event": event, "data": data})
    
    @staticmethod
    def parse_message(message: str) -> Tuple[Optional[str], Any]:
        """Parse a message and return (event, data) tuple."""
        try:
            msg_dict = json.loads(message)
            return msg_dict.get("event"), msg_dict.get("data")
        except json.JSONDecodeError:
            return None, None
    
    @staticmethod
    def validate_message(message: str) -> Tuple[bool, Optional[str]]:
        """Validate message format. Returns (is_valid, error_reason)."""
        try:
            msg_dict = json.loads(message)
            if "event" not in msg_dict:
                return False, 'Missing "event" field'
            return True, None
        except json.JSONDecodeError:
            return False, 'Invalid JSON format'


# Standard event types
class Events:
    STATION_PLAYING = "station_playing"
    STATION_REQUEST = "station_request" 
    VOLUME = "volume"
    CLIENT_COUNT = "client_count"