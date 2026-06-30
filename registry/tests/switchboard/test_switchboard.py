"""Switchboard WebSocket endpoint tests.

Uses Starlette's TestClient which provides synchronous WebSocket testing.
Tests that involve broadcast receive (sender loop) are limited because
the async relay runs in background tasks that do not fit neatly inside the sync
TestClient context.
Those flows are covered by the compose-based integration tests instead.
"""

import time
from collections.abc import Generator
from unittest.mock import AsyncMock

import pytest
from starlette.testclient import TestClient, WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from lib import constants
from registry import create_app
from switchboard.switchboard import (
    ACTIVE_PLAYER_CONNECTIONS,
    _cleared_state_key,
    _state_key,
)

PLAYER_UA = "RadioPad/1.0 (test)"
PLAYER_RADIO_DIAL_URL = "http://example.com/radio-dial.json"
PLAYER_HEADERS = {"User-Agent": PLAYER_UA, "RadioPad-Radio-Dial-Url": PLAYER_RADIO_DIAL_URL}


def _close_player(ws: WebSocketTestSession, player_key: str = "acct/player1") -> None:
    """Let the endpoint finish its disconnect cleanup before TestClient cancels its session task."""
    ws.close()
    deadline = time.monotonic() + 1
    while player_key in ACTIVE_PLAYER_CONNECTIONS and time.monotonic() < deadline:
        time.sleep(0.001)
    assert player_key not in ACTIVE_PLAYER_CONNECTIONS


@pytest.fixture()
def switchboard_client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient]:
    """TestClient wired up with switchboard profile."""
    monkeypatch.setattr(constants, "PROFILES", ["switchboard"])
    ACTIVE_PLAYER_CONNECTIONS.clear()
    app = create_app()
    with TestClient(app) as client:
        yield client
    ACTIVE_PLAYER_CONNECTIONS.clear()


# -- connection gating --


def test_player_requires_radio_dial_url_header(switchboard_client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect):
        with switchboard_client.websocket_connect(
            "switchboard/acct/player1",
            headers={"User-Agent": PLAYER_UA},
        ):
            pass


def test_controller_auth_validation_receives_missing_token(
    switchboard_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auth validation decides whether a tokenless controller is allowed."""
    validate = AsyncMock()
    monkeypatch.setattr("switchboard.switchboard.validate_socket_client", validate)

    with switchboard_client.websocket_connect("switchboard/acct/player1") as ws:
        ws.send_json({"event": "ping"})
        assert ws.receive_json() == {"event": "pong"}

    validate.assert_awaited_once()
    assert validate.await_args.args[3] is None


def test_duplicate_player_connection_is_rejected(switchboard_client: TestClient) -> None:
    with switchboard_client.websocket_connect("switchboard/acct/player1", headers=PLAYER_HEADERS) as player:
        with switchboard_client.websocket_connect("switchboard/acct/player1", headers=PLAYER_HEADERS) as duplicate:
            with pytest.raises(WebSocketDisconnect) as error:
                duplicate.receive_json()
        _close_player(player)
    assert error.value.code == 4002


# -- protocol behavior --


def test_invalid_json_ignored(switchboard_client: TestClient) -> None:
    """Malformed JSON messages are silently ignored, connection stays open."""
    with switchboard_client.websocket_connect("switchboard/acct/player1", headers=PLAYER_HEADERS) as ws:
        ws.send_text("not-json")
        # Connection should still be alive — ping/pong proves it
        ws.send_json({"event": "ping"})
        resp = ws.receive_json()
        assert resp["event"] == "pong"
        _close_player(ws)


def test_missing_event_field_ignored(switchboard_client: TestClient) -> None:
    """Messages without an 'event' field are ignored."""
    with switchboard_client.websocket_connect("switchboard/acct/player1", headers=PLAYER_HEADERS) as ws:
        ws.send_json({"data": "should be ignored"})
        ws.send_json({"event": "ping"})
        resp = ws.receive_json()
        assert resp["event"] == "pong"
        _close_player(ws)


def test_playback_start_is_not_retained_state() -> None:
    assert _state_key("playback_start", {"call_sign": "KEXP"}) is None


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
