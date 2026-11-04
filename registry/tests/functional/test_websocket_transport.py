"""Exercise the selected Uvicorn backend over real loopback sockets."""

import asyncio
import json
import socket
from collections.abc import AsyncIterator

import pytest
import uvicorn
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosedError

from datastore import DataStore
from registry import create_app

PLAYER_HEADERS = {
    "User-Agent": "RadioPad/transport-test",
    "RadioPad-Radio-Dial-Url": "https://example.com/dial.json",
    "RadioPad-Radio-Dial-Revision": '"test"',
}


@pytest.fixture
async def switchboard_transport(mock_store: DataStore) -> AsyncIterator[str]:
    app = create_app(profiles=["api", "switchboard"])
    app.state.store = mock_store
    server = uvicorn.Server(uvicorn.Config(app, ws_max_size=65536, log_level="warning"))
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        task = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            async with asyncio.timeout(5):
                while not server.started:
                    if task.done():
                        await task
                    await asyncio.sleep(0.01)
            yield f"ws://127.0.0.1:{listener.getsockname()[1]}/switchboard/testuser1/player1"
        finally:
            server.should_exit = True
            await asyncio.wait_for(task, timeout=5)


async def test_fragmented_state_routes_and_connections_close_cleanly(switchboard_transport: str) -> None:
    async with connect(switchboard_transport, additional_headers=PLAYER_HEADERS) as player:
        async with connect(switchboard_transport) as controller:
            await controller.send(json.dumps({"event": "authenticate", "data": {"token": None}}))
            assert json.loads(await controller.recv())["event"] == "authenticated"
            await player.send(['{"event":', '"playback_state",', '"data":{"call_sign":"KEXP"}}'])
            async with asyncio.timeout(5):
                while (message := json.loads(await controller.recv()))["event"] != "playback_state":
                    pass
            assert message["data"]["call_sign"] == "KEXP"
        assert controller.close_code == 1000
    assert player.close_code == 1000


@pytest.mark.parametrize("fragmented", [False, True])
async def test_oversized_messages_close_with_1009(switchboard_transport: str, fragmented: bool) -> None:
    async with connect(switchboard_transport, additional_headers=PLAYER_HEADERS) as player:
        await player.send(["x" * 32768, "x" * 32769] if fragmented else "x" * 65537)
        with pytest.raises(ConnectionClosedError) as error:
            async with asyncio.timeout(5):
                while True:
                    await player.recv()
        assert error.value.rcvd is not None
        assert error.value.rcvd.code == 1009
