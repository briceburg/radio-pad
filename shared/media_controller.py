"""
Media controller for radio-pad player.
Handles MPV process and IPC communication.
"""
import asyncio
import logging
import os
import subprocess
import sys
from typing import Optional

try:
    from python_mpv_jsonipc import MPV
except ImportError:
    logging.error("python_mpv_jsonipc not installed")
    sys.exit(1)

from shared.config import Config


class MediaController:
    """Manages MPV media player for radio stations."""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.sock: Optional[MPV] = None
        self.volume: Optional[int] = None
        self.current_station: Optional[dict] = None
        self.sock_lock = asyncio.Lock()
    
    async def play_station(self, station: dict) -> bool:
        """Play a radio station. Returns success status."""
        logging.info(f"Playing station: {station['name']} @ {station['url']}")
        
        try:
            # Stop any currently playing station
            self.stop_station()
            
            self.current_station = station
            
            # Start MPV process
            self.process = subprocess.Popen([
                "mpv", station["url"],
                "--no-osc", "--no-osd-bar", "--no-input-default-bindings",
                "--no-input-cursor", "--no-input-vo-keyboard", "--no-input-terminal",
                "--no-audio-display", f"--input-ipc-server={Config.MPV_SOCKET_FILE}",
                "--no-video", "--no-cache", "--stream-lavf-o=reconnect_streamed=1",
                "--profile=low-latency", f"--audio-channels={Config.AUDIO_CHANNELS}",
            ], stdin=subprocess.DEVNULL, stdout=sys.stdout, stderr=subprocess.STDOUT)
            
            # Reset socket for new process
            self.sock = None
            await self._establish_ipc_socket()
            return True
            
        except Exception as e:
            logging.error(f"Error starting station: {e}")
            return False
    
    def stop_station(self):
        """Stop the currently playing station."""
        self.current_station = None
        
        if self.sock:
            try:
                self.sock.stop()
            except Exception:
                pass
            finally:
                self.sock = None
        
        if self.process:
            try:
                self.process.terminate()
                if os.path.exists(Config.MPV_SOCKET_FILE):
                    os.remove(Config.MPV_SOCKET_FILE)
            except Exception:
                pass
            finally:
                self.process = None
    
    async def adjust_volume(self, delta: int) -> bool:
        """Adjust volume by delta amount. Returns success status."""
        if not self.sock:
            logging.warning("MPV IPC socket not established, cannot adjust volume")
            return False
        
        try:
            if self.volume is None:
                self.volume = self.sock.volume
            
            new_volume = max(50, min(100, self.volume + delta))
            self.volume = new_volume
            self.sock.volume = self.volume
            logging.info(f"Volume adjusted to: {self.volume}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to adjust volume: {e}")
            return False
    
    async def _establish_ipc_socket(self) -> Optional[MPV]:
        """Establish IPC socket connection to MPV."""
        async with self.sock_lock:
            if self.sock is not None:
                return self.sock
                
            loop = asyncio.get_running_loop()
            
            for i in range(Config.MPV_IPC_RETRIES):
                try:
                    sock = await loop.run_in_executor(
                        None, lambda: MPV(start_mpv=False, ipc_socket=Config.MPV_SOCKET_FILE)
                    )
                    self.sock = sock
                    logging.info("MPV IPC established")
                    
                    # Restore volume if available
                    if self.volume is not None:
                        try:
                            self.sock.volume = self.volume
                            logging.info(f"Volume restored to {self.volume}")
                        except Exception as e:
                            logging.warning(f"Failed to restore volume: {e}")
                    
                    return self.sock
                    
                except Exception as e:
                    if i == Config.MPV_IPC_RETRIES - 1:
                        logging.error(f"Failed to connect to MPV IPC: {e}")
                    await asyncio.sleep(Config.MPV_IPC_RETRY_DELAY)
            
            logging.warning("Failed to establish MPV IPC, volume controls disabled")
            return None
    
    def get_current_station_name(self) -> Optional[str]:
        """Get the name of the currently playing station."""
        return self.current_station["name"] if self.current_station else None
    
    def is_playing(self) -> bool:
        """Check if a station is currently playing."""
        return self.current_station is not None