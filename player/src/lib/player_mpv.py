# This file is part of the radio-pad project.
# https://github.com/briceburg/radio-pad
#
# Copyright (c) 2025 Brice Burgess <https://github.com/briceburg>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


from lib.interfaces import RadioPadPlayer, RadioPadStation, RadioPadPlayerConfig
from python_mpv_jsonipc import MPV
import asyncio
import os
import subprocess
import logging

logger = logging.getLogger('PLAYER')


class MpvPlayer(RadioPadPlayer):
    def __init__(self, config: RadioPadPlayerConfig, audio_channels: str = "stereo",
                 socket_path: str = "/tmp/radio-pad-mpv.sock"):
        super().__init__(config)
        self.audio_channels = audio_channels
        self.socket_path = socket_path
        self.mpv_process = None
        self.mpv_sock = None
        self.mpv_volume = None
        self.mpv_sock_lock = asyncio.Lock()

    async def play(self, station: RadioPadStation):
        """Play a radio station."""

        logger.info("playing station %s (%s)", station.name, station.url)
        try:
            # Stop any existing playback
            await self.stop()
            # Start mpv process
            self.mpv_process = subprocess.Popen(
                [
                    "mpv",
                    station.url,
                    "--no-osc",
                    "--no-osd-bar",
                    "--no-input-default-bindings",
                    "--no-input-cursor",
                    "--no-input-vo-keyboard",
                    "--no-input-terminal",
                    "--no-audio-display",
                    f"--input-ipc-server={self.socket_path}",
                    "--no-video",
                    "--no-cache",
                    "--stream-lavf-o=reconnect_streamed=1",
                    "--profile=low-latency",
                    f"--audio-channels={self.audio_channels}",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if self.mpv_process and self.mpv_process.poll() is None:
                logger.info("mpv process started with PID %s", self.mpv_process.pid)
                self.station = station
            else:
                logger.error("failed to start mpv process.")
            self.mpv_sock = None
            await self._establish_ipc_socket()
        except Exception as e:
            logger.error("error starting station: %s", e, exc_info=True)

    async def stop(self):
        """Stop playback of the current station."""
        self.station = None
        if self.mpv_sock:
            try:
                self.mpv_sock.stop()
            except Exception:
                pass
            finally:
                self.mpv_sock = None

        if self.mpv_process:
            try:
                self.mpv_process.terminate()
                if os.path.exists(self.socket_path):
                    os.remove(self.socket_path)
            except Exception:
                pass
            finally:
                self.mpv_process = None

    async def volume_up(self):
        self._adjust_volume(5)

    async def volume_down(self):
        self._adjust_volume(-5)

    def _adjust_volume(self, amount):
        if self.mpv_sock is None:
            logger.warning("mpv IPC socket not established, cannot adjust volume.")
            return

        if self.mpv_volume is None:
            self.mpv_volume = self.mpv_sock.volume

        volume = self.mpv_volume + amount

        if volume > 100:
            volume = 100
        elif volume < 0:
            volume = 0

        self.mpv_volume = volume
        self.mpv_sock.volume = self.mpv_volume
        logger.debug("Adjusted Volume: %s", self.mpv_volume)

    async def _establish_ipc_socket(self):
        async with self.mpv_sock_lock:
            if self.mpv_sock is not None:
                return self.mpv_sock
            loop = asyncio.get_running_loop()
            for i in range(20):
                try:
                    sock = await loop.run_in_executor(
                        None, lambda: MPV(start_mpv=False, ipc_socket=self.socket_path)
                    )
                    self.mpv_sock = sock
                    self.mpv_volume = sock.volume
                    return sock
                except Exception as e:
                    await asyncio.sleep(0.2)
            logger.error("failed to establish mpv IPC socket.")
            return
