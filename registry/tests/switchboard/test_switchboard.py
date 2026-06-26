"""Switchboard WebSocket endpoint tests.

Uses Starlette's TestClient which provides synchronous WebSocket testing.
Tests that involve broadcast receive (sender loop) are limited because
the async relay runs in background tasks that do not fit neatly inside the sync
TestClient context.
Those flows are covered by the compose-based integration tests instead.
"""

from collections.abc import Generator
from typing import cast

import pytest
from fastapi import WebSocket
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from registry import create_app
from switchboard.switchboard import (
    ACTIVE_PLAYER_CONNECTIONS,
    _cleared_state_key,
    _register_player_connection,
    _state_key,
    _unregister_player_connection,
)

PLAYER_UA = "RadioPad/1.0 (test)"
PLAYER_STATIONS_URL = "http://example.com/stations.json"
PLAYER_HEADERS = {"User-Agent": PLAYER_UA, "RadioPad-Stations-Url": PLAYER_STATIONS_URL}


@pytest.fixture()
def switchboard_client() -> Generator[TestClient]:
    """TestClient wired up with switchboard profile."""
    app = create_app()
    with TestClient(app) as client:
        yield client


# -- connection gating --


def test_player_requires_stations_url_header(switchboard_client: TestClient) -> None:
    """Player missing RadioPad-Stations-Url header is rejected."""
    with pytest.raises(WebSocketDisconnect):
        with switchboard_client.websocket_connect(
            "switchboard/acct/player1",
            headers={"User-Agent": PLAYER_UA},
        ):
            pass


def test_controller_rejected_without_token(switchboard_client: TestClient) -> None:
    """Controller without a token is closed with 4001."""
    with pytest.raises(WebSocketDisconnect):
        with switchboard_client.websocket_connect("switchboard/acct/player1") as ws:
            ws.receive_text()


def test_player_connects_with_valid_headers(switchboard_client: TestClient) -> None:
    """Player with correct headers is accepted and can ping/pong."""
    with switchboard_client.websocket_connect("switchboard/acct/player1", headers=PLAYER_HEADERS) as ws:
        ws.send_json({"event": "ping"})
        resp = ws.receive_json()
        assert resp["event"] == "pong"


# -- protocol behavior --


def test_invalid_json_ignored(switchboard_client: TestClient) -> None:
    """Malformed JSON messages are silently ignored, connection stays open."""
    with switchboard_client.websocket_connect("switchboard/acct/player1", headers=PLAYER_HEADERS) as ws:
        ws.send_text("not-json")
        # Connection should still be alive — ping/pong proves it
        ws.send_json({"event": "ping"})
        resp = ws.receive_json()
        assert resp["event"] == "pong"


def test_missing_event_field_ignored(switchboard_client: TestClient) -> None:
    """Messages without an 'event' field are ignored."""
    with switchboard_client.websocket_connect("switchboard/acct/player1", headers=PLAYER_HEADERS) as ws:
        ws.send_json({"data": "should be ignored"})
        ws.send_json({"event": "ping"})
        resp = ws.receive_json()
        assert resp["event"] == "pong"


def test_playback_start_is_not_retained_state() -> None:
    assert _state_key("playback_start", {"station_name": "KEXP"}) is None


def test_player_status_warning_is_retained_by_scope() -> None:
    assert (
        _state_key(
            "player_status",
            {"scope": "switchboard", "level": "warning", "summary": "down"},
        )
        == "player_status:switchboard"
    )


def test_player_status_ok_clears_scope() -> None:
    data = {"scope": "switchboard", "level": "ok", "summary": None}
    assert _state_key("player_status", data) is None
    assert _cleared_state_key("player_status", data) == "player_status:switchboard"


def test_player_connection_tracking_identifies_last_disconnect() -> None:
    ACTIVE_PLAYER_CONNECTIONS.clear()
    ws1 = cast(WebSocket, object())
    ws2 = cast(WebSocket, object())

    assert _register_player_connection("acct/player", ws1)
    assert not _register_player_connection("acct/player", ws2)
    assert not _unregister_player_connection("acct/player", ws1)
    assert _unregister_player_connection("acct/player", ws2)
