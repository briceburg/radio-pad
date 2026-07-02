"""Player integration tests using the real compose-managed player service."""

import asyncio
import json

import pytest
import websockets

IDLE = {"call_sign": None, "requested_call_sign": None, "failed_call_sign": None}
PENDING_WWOZ = {**IDLE, "requested_call_sign": "WWOZ"}
PLAYING_WWOZ = {**IDLE, "call_sign": "WWOZ"}

PLAYER_ROOM = "briceburg/living-room"


async def wait_for_event(ws, event_name, predicate=None, timeout=15):
    async with asyncio.timeout(timeout):
        while True:
            message = json.loads(await ws.recv())
            if message.get("event") != event_name:
                continue
            if predicate is not None and not predicate(message.get("data")):
                continue
            return message


@pytest.mark.asyncio
async def test_real_player_processes_playback_commands(switchboard_url):
    controller_url = f"{switchboard_url}/{PLAYER_ROOM}"

    async with websockets.connect(controller_url) as controller:
        await controller.send(json.dumps({"event": "authenticate", "data": {"token": None}}))
        await wait_for_event(controller, "authenticated")
        await controller.send(json.dumps({"event": "playback_start", "data": {"call_sign": "WWOZ"}}))

        pending = await wait_for_event(
            controller,
            "playback_state",
            predicate=lambda data: data == PENDING_WWOZ,
        )
        assert pending["data"] == PENDING_WWOZ

        playing = await wait_for_event(
            controller,
            "playback_state",
            predicate=lambda data: data == PLAYING_WWOZ,
        )
        assert playing["data"] == PLAYING_WWOZ

        await controller.send(json.dumps({"event": "playback_stop", "data": None}))

        stopped = await wait_for_event(
            controller,
            "playback_state",
            predicate=lambda data: data == IDLE,
        )
        assert stopped["data"] == IDLE
