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


async def wait_for_event(ws, event_name, timeout=5):
    """Read messages until the expected event arrives (or timeout)."""
    while True:
        message = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if message.get("event") == event_name:
            return message


@pytest.mark.asyncio
async def test_player_connect(switchboard_url):
    """Player can connect, send ping, receive pong."""
    async with websockets.connect(
        f"{switchboard_url}/test-acct/player1", additional_headers=PLAYER_HEADERS
    ) as ws:
        await ws.send(json.dumps({"event": "ping"}))
        resp = await wait_for_event(ws, "pong")
        assert resp["event"] == "pong"


@pytest.mark.asyncio
async def test_controller_connects_without_token_when_auth_disabled(switchboard_url):
    """Controllers can connect anonymously when registry auth is disabled."""
    async with websockets.connect(f"{switchboard_url}/test-acct/player1") as ws:
        await ws.send(json.dumps({"event": "ping"}))
        resp = await wait_for_event(ws, "pong")
        assert resp["event"] == "pong"


@pytest.mark.asyncio
async def test_player_station_playing_broadcast(switchboard_url):
    """Player publishes station_playing, a second player connection receives it.

    Uses two player connections to the same room to verify the broadcast
    path works end-to-end through the broadcaster, without needing an
    authenticated controller token.
    """
    room = f"{switchboard_url}/test-acct/broadcast-test"

    async with websockets.connect(room, additional_headers=PLAYER_HEADERS) as player1:
        # Drain the initial stations_url broadcast from player1 connecting
        try:
            await asyncio.wait_for(player1.recv(), timeout=1)
        except asyncio.TimeoutError:
            pass

        async with websockets.connect(room, additional_headers=PLAYER_HEADERS) as player2:
            # Drain any initial messages on player2 (stations_url from player2 join)
            try:
                while True:
                    await asyncio.wait_for(player2.recv(), timeout=1)
            except asyncio.TimeoutError:
                pass

            # player1 sends station_playing
            await player1.send(json.dumps({
                "event": "station_playing",
                "data": {"name": "Test FM", "url": "http://example.com/stream"},
            }))

            # player2 should receive the broadcast
            msg = json.loads(await asyncio.wait_for(player2.recv(), timeout=5))
            assert msg["event"] == "station_playing"
            assert msg["data"]["name"] == "Test FM"
