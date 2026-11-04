"""Switchboard WebSocket integration tests.

Tests connection gating, ping/pong, and cross-client message routing
in a real compose environment.
"""

import asyncio
import json

import pytest
import websockets
from websockets.exceptions import ConnectionClosedError

PLAYER_HEADERS = {
    "User-Agent": "RadioPad/1.0 (integration-test)",
    "RadioPad-Radio-Dial-Url": "http://example.com/radio-dial.json",
    "RadioPad-Radio-Dial-Revision": '"integration-v1"',
}
REGISTERED_PLAYER_ROOM = "briceburg/living-room"


@pytest.mark.asyncio
async def test_player_connect(switchboard_url):
    """Player can send a fragmented ping, receive pong, and close cleanly."""
    async with websockets.connect(f"{switchboard_url}/test-acct/player1", additional_headers=PLAYER_HEADERS) as ws:
        await ws.send(['{"event":', '"ping"}'])
        async with asyncio.timeout(5):
            while json.loads(await ws.recv())["event"] != "pong":
                pass
    assert ws.close_code == 1000


@pytest.mark.asyncio
@pytest.mark.parametrize("fragmented", [False, True])
async def test_oversized_messages_close_with_1009(switchboard_url, fragmented):
    async with websockets.connect(f"{switchboard_url}/test-acct/oversized", additional_headers=PLAYER_HEADERS) as ws:
        await ws.send(["x" * 32768, "x" * 32769] if fragmented else "x" * 65537)
        with pytest.raises(ConnectionClosedError) as error:
            async with asyncio.timeout(5):
                while True:
                    await ws.recv()
        assert error.value.rcvd is not None
        assert error.value.rcvd.code == 1009


@pytest.mark.asyncio
async def test_controller_authenticates_for_registry_mode(switchboard_url, registry_session):
    """Controllers use a registry token exactly when OIDC is enabled."""
    token = registry_session.json()["access_token"] if registry_session else None
    expires_at = registry_session.json()["expires_at"] if registry_session else None
    async with websockets.connect(f"{switchboard_url}/{REGISTERED_PLAYER_ROOM}") as ws:
        await ws.send(json.dumps({"event": "authenticate", "data": {"token": token}}))
        assert json.loads(await ws.recv()) == {"event": "authenticated", "data": {"expires_at": expires_at}}
        await ws.send(json.dumps({"event": "ping"}))
        async with asyncio.timeout(3):
            while True:
                response = json.loads(await ws.recv())
                if response == {"event": "pong"}:
                    break
