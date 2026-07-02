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


import asyncio
import logging
import os
import subprocess

from python_mpv_jsonipc import MPV

from lib.interfaces import RadioPadPlayer, RadioPadPlayerConfig, RadioPadStation

logger = logging.getLogger("PLAYER")
READINESS_POLL_SECONDS = 0.2
PROCESS_STOP_TIMEOUT_SECONDS = 2


class MpvPlayer(RadioPadPlayer):
    def __init__(
        self,
        config: RadioPadPlayerConfig | None = None,
        audio_channels: str = "stereo",
        audio_device: str | None = None,
        audio_output: str | None = None,
        socket_path: str = "/tmp/radio-pad-mpv.sock",
        playback_timeout_seconds: float = 15,
    ):
        super().__init__(config)
        self.audio_channels = audio_channels
        self.audio_device = audio_device
        self.audio_output = audio_output
        self.socket_path = socket_path
        self.playback_timeout_seconds = playback_timeout_seconds
        self.mpv_process: subprocess.Popen[bytes] | None = None
        self.mpv_sock = None
        self.mpv_volume = None

    async def play(self, station: RadioPadStation):
        """Play a station and return only after mpv reports usable audio."""

        logger.info("starting station %s (%s)", station.call_sign, station.stream_url)
        try:
            self._remove_stale_socket()
            process = subprocess.Popen(
                [
                    "mpv",
                    station.stream_url,
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
                    *([f"--audio-device={self.audio_device}"] if self.audio_device else []),
                    *([f"--ao={self.audio_output}"] if self.audio_output else []),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
            )
            self.mpv_process = process
            logger.info("mpv process started with PID %s; waiting for IPC playback readiness", process.pid)
            async with asyncio.timeout(self.playback_timeout_seconds):
                await self._connect_ipc()
                await self._wait_for_audio_ready()
            self.station = station
            logger.info("confirmed playback for station %s", station.call_sign)
            await self._report_status("ok", None)
            return True
        except asyncio.CancelledError:
            await self.stop()
            raise
        except TimeoutError as e:
            await self.stop()
            logger.error("playback timed out for %s: %s", station.call_sign, e)
            await self._report_status("error", "Playback timed out")
            return False
        except Exception as e:
            await self.stop()
            logger.error("error starting station: %s", e, exc_info=True)
            await self._report_status("error", "Playback failed")
            return False

    async def stop(self):
        """Stop playback of the current station."""
        self.station = None
        await self._report_status("ok", None)
        if self.mpv_sock:
            try:
                self.mpv_sock.stop()
            except Exception:
                pass
            finally:
                self.mpv_sock = None

        if self.mpv_process:
            process = self.mpv_process
            self.mpv_process = None
            try:
                process.terminate()
                try:
                    await asyncio.to_thread(process.wait, timeout=PROCESS_STOP_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    process.kill()
                    await asyncio.to_thread(process.wait)
            except Exception:
                logger.warning("error stopping mpv process", exc_info=True)

        self._remove_stale_socket()

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
        elif volume < 50:
            volume = 50

        self.mpv_volume = volume
        self.mpv_sock.volume = self.mpv_volume
        logger.debug("Adjusted Volume: %s", self.mpv_volume)

    async def _connect_ipc(self):
        while True:
            self._require_running_process()
            try:
                sock = await asyncio.to_thread(MPV, start_mpv=False, ipc_socket=self.socket_path)
                self.mpv_sock = sock
                self.mpv_volume = sock.volume
                logger.info("mpv IPC socket ready")
                return
            except Exception:
                await asyncio.sleep(READINESS_POLL_SECONDS)

    async def _wait_for_audio_ready(self):
        while True:
            self._require_running_process()
            sock = self.mpv_sock
            if sock is None:
                raise RuntimeError("mpv IPC disconnected before playback was ready")
            try:
                idle_active, audio_params = await asyncio.to_thread(
                    lambda: (sock.idle_active, sock.audio_params),
                )
                if idle_active is False and audio_params:
                    return
            except Exception:
                logger.debug("mpv playback properties are not ready", exc_info=True)
            await asyncio.sleep(READINESS_POLL_SECONDS)

    def _require_running_process(self):
        process = self.mpv_process
        if process is None or process.poll() is not None:
            return_code = process.poll() if process else None
            raise RuntimeError(f"mpv exited before playback was ready (code {return_code})")

    def _remove_stale_socket(self):
        try:
            os.remove(self.socket_path)
        except FileNotFoundError:
            pass
        except OSError:
            logger.warning("could not remove stale mpv IPC socket %s", self.socket_path, exc_info=True)
