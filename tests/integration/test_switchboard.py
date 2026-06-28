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


@pytest.mark.asyncio
async def test_player_connect(switchboard_url):
    """Player can connect, send ping, receive pong."""
    async with websockets.connect(f"{switchboard_url}/test-acct/player1", additional_headers=PLAYER_HEADERS) as ws:
        await ws.send(json.dumps({"event": "ping"}))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert resp["event"] == "pong"


@pytest.mark.asyncio
async def test_controller_rejected_without_token(switchboard_url):
    """Controllers without an auth token are rejected."""
    with pytest.raises(Exception):
        async with websockets.connect(f"{switchboard_url}/test-acct/player1") as ws:
            await asyncio.wait_for(ws.recv(), timeout=3)
