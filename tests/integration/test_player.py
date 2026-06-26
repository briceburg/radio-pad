"""Player integration tests using the real compose-managed player service."""

import asyncio
import json

import pytest
import websockets

PLAYER_ROOM = "briceburg/living-room"
CONTROLLER_TOKEN = "integration-test-token"


async def wait_for_event(ws, event_name, predicate=None, timeout=15):
    while True:
        message = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if message.get("event") != event_name:
            continue
        if predicate is not None and not predicate(message.get("data")):
            continue
        return message


@pytest.mark.asyncio
async def test_real_player_processes_playback_commands(switchboard_url):
    controller_url = f"{switchboard_url}/{PLAYER_ROOM}?token={CONTROLLER_TOKEN}"

    async with websockets.connect(controller_url) as controller:
        await controller.send(
            json.dumps(
                {"event": "playback_start", "data": {"station_name": "wwoz"}}
            )
        )

        playing = await wait_for_event(
            controller,
            "playback_state",
            predicate=lambda data: data == {"station_name": "wwoz"},
        )
        assert playing["data"] == {"station_name": "wwoz"}

        await controller.send(json.dumps({"event": "playback_stop", "data": None}))

        stopped = await wait_for_event(
            controller,
            "playback_state",
            predicate=lambda data: data == {"station_name": None},
        )
        assert stopped["data"] == {"station_name": None}
