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
async def test_real_player_processes_playback_commands(switchboard_url, registry_session):
    controller_url = f"{switchboard_url}/{PLAYER_ROOM}"
    token = registry_session.json()["access_token"] if registry_session else None

    async with websockets.connect(controller_url) as controller:
        await controller.send(json.dumps({"event": "authenticate", "data": {"token": token}}))
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


@pytest.mark.asyncio
async def test_real_player_broadcasts_live_radio_dial_refresh(
    http,
    registry_url,
    switchboard_url,
    registry_session,
):
    controller_url = f"{switchboard_url}/{PLAYER_ROOM}"
    token = registry_session.json()["access_token"] if registry_session else None
    auth_headers = {"Authorization": f"Bearer {token}"} if token else {}
    station_url = f"{registry_url}/accounts/community/stations/WWOZ"
    original_stream_url = http.get(station_url).json()["stream_url"]
    updated_stream_url = f"{original_stream_url}?radio-pad-live-refresh-test=1"

    def update_station(stream_url):
        response = http.put(station_url, headers=auth_headers, json={"stream_url": stream_url})
        assert response.status_code == 200

    async with websockets.connect(controller_url) as controller:
        await controller.send(json.dumps({"event": "authenticate", "data": {"token": token}}))
        await wait_for_event(controller, "authenticated")
        initial = await wait_for_event(controller, "radio_dial_state")

        try:
            update_station(updated_stream_url)
            refreshed = await wait_for_event(
                controller,
                "radio_dial_state",
                predicate=lambda data: data["revision"] != initial["data"]["revision"],
            )
            assert refreshed["data"]["url"].endswith("/accounts/community/radio-dials/briceburg")
        finally:
            update_station(original_stream_url)

        await wait_for_event(
            controller,
            "radio_dial_state",
            predicate=lambda data: data["revision"] != refreshed["data"]["revision"],
        )
