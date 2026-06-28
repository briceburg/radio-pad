"""Player integration tests using the real compose-managed player service."""

import asyncio
import json

import pytest
import websockets

PLAYER_ROOM = "briceburg/living-room"
CONTROLLER_TOKEN = "integration-test-token"


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
    controller_url = f"{switchboard_url}/{PLAYER_ROOM}?token={CONTROLLER_TOKEN}"

    async with websockets.connect(controller_url) as controller:
        await controller.send(json.dumps({"event": "playback_start", "data": {"call_sign": "WWOZ"}}))

        playing = await wait_for_event(
            controller,
            "playback_state",
            predicate=lambda data: data == {"call_sign": "WWOZ"},
        )
        assert playing["data"] == {"call_sign": "WWOZ"}

        await controller.send(json.dumps({"event": "playback_stop", "data": None}))

        stopped = await wait_for_event(
            controller,
            "playback_state",
            predicate=lambda data: data == {"call_sign": None},
        )
        assert stopped["data"] == {"call_sign": None}
