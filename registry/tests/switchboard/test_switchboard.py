"""Switchboard WebSocket endpoint tests.

Uses Starlette's TestClient which provides synchronous WebSocket testing.
Tests that involve broadcast receive (sender loop) are limited because
the async relay runs in background tasks that do not fit neatly inside the sync
TestClient context.
Those flows are covered by the compose-based integration tests instead.
"""

from collections.abc import Generator

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from registry import create_app

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


def test_controller_connects_without_token_when_auth_disabled(switchboard_client: TestClient) -> None:
    """Controller can connect anonymously when auth is disabled."""
    with switchboard_client.websocket_connect("switchboard/acct/player1") as ws:
        ws.send_json({"event": "ping"})
        resp = ws.receive_json()
        assert resp["event"] == "pong"


def test_controller_rejected_without_token_when_auth_enabled() -> None:
    """Controller without a token is closed with 4001 when auth is enabled."""
    app = create_app()

    # Simulate auth being enabled by setting a mock AuthServices with enabled=True
    class _FakeAuth:
        enabled = True

    app.state.auth = _FakeAuth()

    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("switchboard/acct/player1") as ws:
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
