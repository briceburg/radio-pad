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
    "RadioPad-Stations-Url": "http://example.com/stations.json",
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


@pytest.mark.asyncio
async def test_player_playback_state_broadcast(switchboard_url):
    """Player publishes playback_state, a second player connection receives it.

    Uses two player connections to the same room to verify the broadcast
    path works end-to-end through the broadcaster, without needing an
    authenticated controller token.
    """
    room = f"{switchboard_url}/test-acct/broadcast-test"

    async with websockets.connect(room, additional_headers=PLAYER_HEADERS) as player1:
        async with websockets.connect(room, additional_headers=PLAYER_HEADERS) as player2:
            # player1 sends playback_state
            await player1.send(
                json.dumps(
                    {
                        "event": "playback_state",
                        "data": {"station_name": "Test FM"},
                    }
                )
            )

            # player2 should receive the broadcast
            msg = json.loads(await asyncio.wait_for(player2.recv(), timeout=5))
            assert msg["event"] == "playback_state"
            assert msg["data"]["station_name"] == "Test FM"
