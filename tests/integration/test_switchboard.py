"""Switchboard WebSocket integration tests.

Tests connection gating, ping/pong, and cross-client message routing
in a real compose environment.
"""

import asyncio
import json

import pytest
import websockets

PLAYER_HEADERS = {
    "User-Agent": "RadioPad/1.0 (integration-test)",
    "RadioPad-Radio-Dial-Url": "http://example.com/radio-dial.json",
}
REGISTERED_PLAYER_ROOM = "briceburg/living-room"


@pytest.mark.asyncio
async def test_player_connect(switchboard_url):
    """Player can connect, send ping, receive pong."""
    async with websockets.connect(f"{switchboard_url}/test-acct/player1", additional_headers=PLAYER_HEADERS) as ws:
        await ws.send(json.dumps({"event": "ping"}))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert resp["event"] == "pong"


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
