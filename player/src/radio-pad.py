#!/usr/bin/env python3

import asyncio
import logging
import os
import signal
import sys
import serial_asyncio
import serial.tools.list_ports

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shared'))

from protocol import MessageProtocol, Events
from config import Config
from media_controller import MediaController
from station_manager import StationManager
from websocket_utils import WebSocketManager, BroadcastManager

# Global state
MACROPAD = None
media_controller = MediaController()
station_manager = StationManager()
broadcast_manager = BroadcastManager()


async def setup_broadcast_targets():
    """Set up broadcast targets for macropad and switchboard."""
    async def macropad_send(message):
        if MACROPAD:
            try:
                MACROPAD.write((message + "\n").encode())
                await MACROPAD.drain()
            except Exception as e:
                logging.error(f"Failed to send to macropad: {e}")
    
    broadcast_manager.add_target("macropad", macropad_send)


async def handle_msg(event: str, data):
    """Handle incoming events from macropad and switchboard."""
    try:
        if event == Events.VOLUME:
            delta = 5 if data == "up" else -5
            await media_controller.adjust_volume(delta)
        elif event == Events.STATION_REQUEST:
            if data:
                station = station_manager.find_station_by_name(data)
                if station:
                    await media_controller.play_station(station)
            else:
                media_controller.stop_station()
            
            # Broadcast current station status
            station_name = media_controller.get_current_station_name()
            await broadcast_manager.broadcast(Events.STATION_PLAYING, station_name)
        elif event in [Events.STATION_PLAYING, Events.CLIENT_COUNT]:
            pass  # Ignore these events
        else:
            logging.warning(f"Unknown event: {event}")
    except Exception as e:
        logging.error(f"Error handling event '{event}': {e}")


async def cleanup():
    """Clean up resources before exit."""
    global MACROPAD
    logging.info("Cleaning up before exit...")
    
    if media_controller.is_playing():
        media_controller.stop_station()
        await broadcast_manager.broadcast(Events.STATION_PLAYING, None)
    
    if MACROPAD:
        try:
            await MACROPAD.wait_closed()
        except Exception as e:
            logging.error(f"Error closing macropad: {e}")
        MACROPAD = None

async def macropad_loop():
    """Connect to macropad and listen for events with auto-reconnect."""
    global MACROPAD
    
    while True:
        try:
            # Find all macropad ports
            ports = serial.tools.list_ports.comports()
            macropad_ports = [port for port, desc, _ in sorted(ports) if "Macropad" in desc]
            
            if not macropad_ports:
                logging.info("No macropad ports found, is it plugged in?")
            else:
                logging.info(f"Found {len(macropad_ports)} macropad port(s): {macropad_ports}")
                
                # Try each port to find the one that works for USB CDC data
                connected = False
                for macropad_port in macropad_ports:
                    logging.info(f"Attempting to connect to {macropad_port}")
                    
                    try:
                        reader, writer = await serial_asyncio.open_serial_connection(
                            url=macropad_port, baudrate=115200
                        )
                        
                        MACROPAD = writer
                        logging.info(f"Macropad connected to: {macropad_port}")
                        
                        # Send initial station playing event
                        current_station = media_controller.get_current_station_name()
                        await broadcast_manager.broadcast(Events.STATION_PLAYING, current_station, "macropad")
                        
                        # Listen for messages
                        connected = True
                        while True:
                            try:
                                line = await reader.readline()
                                if not line:
                                    break
                                
                                message = line.decode('utf-8').strip()
                                if message:
                                    event, data = MessageProtocol.parse_message(message)
                                    if event:
                                        await handle_msg(event, data)
                                    else:
                                        logging.warning(f"Invalid macropad message: {message}")
                                        
                            except Exception as e:
                                logging.error(f"Error reading macropad message: {e}")
                                break
                                
                    except Exception as e:
                        logging.warning(f"Failed to connect to {macropad_port}: {e}")
                        continue  # Try next port
                    finally:
                        if MACROPAD:
                            MACROPAD.close()
                            await MACROPAD.wait_closed()
                            MACROPAD = None
                            logging.info("Macropad connection closed")
                    
                    # If we successfully connected and then disconnected, break out of port loop
                    if connected:
                        break
                
                if not connected:
                    logging.warning("Failed to connect to any macropad port")
                        
        except Exception as e:
            logging.error(f"Unexpected macropad error: {e}")
        
        logging.info(f"Reconnecting to macropad in {Config.MACROPAD_RECONNECT_DELAY}s...")
        await asyncio.sleep(Config.MACROPAD_RECONNECT_DELAY)


async def main():
    """Main application entry point."""
    # Initialize components
    if not await station_manager.load_stations():
        logging.error("Failed to load stations, exiting")
        sys.exit(1)
    
    await setup_broadcast_targets()
    
    # Create WebSocket manager for switchboard connection
    async def switchboard_message_handler(event: str, data):
        await handle_msg(event, data)
    
    ws_manager = WebSocketManager(
        url=Config.SWITCHBOARD_URL,
        message_handler=switchboard_message_handler,
        user_agent="RadioPad/1.0",
        reconnect_delay=Config.RECONNECT_DELAY
    )
    
    # Add switchboard to broadcast targets
    async def switchboard_send(message):
        if ws_manager.is_connected:
            await ws_manager.websocket.send(message)
    
    broadcast_manager.add_target("switchboard", switchboard_send)
    
    try:
        await asyncio.gather(
            macropad_loop(),
            ws_manager.connect_loop(),
        )
    except asyncio.CancelledError:
        logging.info("Player exiting...")
        await cleanup()
        await ws_manager.close()
        raise
    except Exception as e:
        logging.error(f"Unexpected error in main: {e}")
        await cleanup()
        await ws_manager.close()
        raise


if __name__ == "__main__":
    def handle_exit(signum=None, frame=None, code=0):
        logging.info("Player received exit signal...")
        sys.exit(code)
    
    try:
        logging.basicConfig(level=logging.INFO)
        signal.signal(signal.SIGTERM, handle_exit)
        signal.signal(signal.SIGINT, handle_exit)
        asyncio.run(main())
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)
