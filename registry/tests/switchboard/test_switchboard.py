"""Switchboard WebSocket endpoint tests.

Uses Starlette's TestClient which provides synchronous WebSocket testing.
Tests that involve broadcast receive (sender loop) are limited because
the async relay runs in background tasks that do not fit neatly inside the sync
TestClient context.
Those flows are covered by the compose-based integration tests instead.
"""

import asyncio
import time
from collections.abc import Generator
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient, WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from api.auth import AuthServices
from auth import AccessTokens, AuthenticatedIdentity
from authz import AccountOwners, AuthzStore
from datastore import LocalBackend
from registry import create_app
from switchboard.broadcast import Broadcast
from switchboard.switchboard import (
    ACTIVE_PLAYER_CONNECTIONS,
    _cleared_state_key,
    _run_loop,
    _state_key,
    websocket_endpoint,
)

PLAYER_UA = "RadioPad/1.0 (test)"
PLAYER_RADIO_DIAL_URL = "http://example.com/radio-dial.json"
PLAYER_RADIO_DIAL_REVISION = '"radio-dial-v1"'
PLAYER_HEADERS = {
    "User-Agent": PLAYER_UA,
    "RadioPad-Radio-Dial-Url": PLAYER_RADIO_DIAL_URL,
    "RadioPad-Radio-Dial-Revision": PLAYER_RADIO_DIAL_REVISION,
}


def _close_player(ws: WebSocketTestSession, player_key: str = "acct/player1") -> None:
    """Let the endpoint finish its disconnect cleanup before TestClient cancels its session task."""
    ws.close()
    deadline = time.monotonic() + 1
    while player_key in ACTIVE_PLAYER_CONNECTIONS and time.monotonic() < deadline:
        time.sleep(0.001)
    assert player_key not in ACTIVE_PLAYER_CONNECTIONS


@pytest.fixture()
def switchboard_client() -> Generator[TestClient]:
    """TestClient wired up with switchboard profile."""
    ACTIVE_PLAYER_CONNECTIONS.clear()
    app = create_app(profiles=["switchboard"])
    with TestClient(app) as client:
        app.state.radio_dial_watcher = None
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


def test_player_requires_radio_dial_revision_header(switchboard_client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect):
        with switchboard_client.websocket_connect(
            "switchboard/acct/player1",
            headers={"User-Agent": PLAYER_UA, "RadioPad-Radio-Dial-Url": PLAYER_RADIO_DIAL_URL},
        ):
            pass


async def test_controller_auth_validation_receives_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auth validation decides whether a tokenless controller is allowed."""
    websocket = AsyncMock()
    websocket.headers = {}
    websocket.app.state.broadcast = Broadcast()
    websocket.receive_text.return_value = '{"event":"authenticate","data":{"token":null}}'
    validate = AsyncMock()
    validate.return_value = None
    run_loop = AsyncMock()
    monkeypatch.setattr("switchboard.switchboard.validate_socket_client", validate)
    monkeypatch.setattr("switchboard.switchboard._run_loop", run_loop)

    await websocket_endpoint(websocket, "acct", "player1")

    validate.assert_awaited_once_with(websocket, "acct", "player1", None)
    websocket.accept.assert_awaited_once()
    websocket.send_json.assert_awaited_once_with({"event": "authenticated", "data": {"expires_at": None}})


async def test_controller_auth_internal_error_closes_1011(monkeypatch: pytest.MonkeyPatch) -> None:
    websocket = AsyncMock()
    websocket.headers = {}
    websocket.receive_text.return_value = '{"event":"authenticate","data":{"token":"token"}}'
    validate = AsyncMock(side_effect=RuntimeError("auth backend unavailable"))
    monkeypatch.setattr("switchboard.switchboard.validate_socket_client", validate)

    await websocket_endpoint(websocket, "acct", "player1")

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(code=1011, reason="Validation internal error")


@pytest.mark.parametrize(
    "message",
    [
        '{"event":"authenticate","data":"token"}',
        '{"event":"authenticate","data":{}}',
        '{"event":"authenticate","data":{"token":123}}',
    ],
)
async def test_controller_auth_rejects_malformed_messages(
    monkeypatch: pytest.MonkeyPatch,
    message: str,
) -> None:
    websocket = AsyncMock()
    websocket.headers = {}
    websocket.receive_text.return_value = message
    validate = AsyncMock()
    monkeypatch.setattr("switchboard.switchboard.validate_socket_client", validate)

    await websocket_endpoint(websocket, "acct", "player1")

    validate.assert_not_awaited()
    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(code=1008, reason="Authentication required")


def test_authenticated_controller_receives_retained_player_state(tmp_path: Path) -> None:
    from tests.api._app import build_store

    store = build_store(tmp_path / "data", seed=True)
    authz = AuthzStore(backend=LocalBackend(base_path=str(tmp_path / "authz"), prefix="authz"))
    authz.save_account_owners(AccountOwners(id="testuser1", emails=["owner@example.com"]))

    identity = AuthenticatedIdentity(
        issuer="https://issuer.example",
        subject="owner",
        authenticated_at=1_700_000_000,
        email="owner@example.com",
        email_verified=True,
    )
    access_tokens = AccessTokens("test-session-secret-value-32-bytes")
    access = access_tokens.issue(identity)

    app = create_app(profiles=["api", "switchboard"])
    app.state.store = store
    app.state.auth = AuthServices(
        authenticate_oidc=Mock(),
        authz_store=authz,
        access_tokens=access_tokens,
    )

    with TestClient(app) as client:
        app.state.radio_dial_watcher = None
        with client.websocket_connect("/switchboard/testuser1/player1", headers=PLAYER_HEADERS) as player:
            player.send_json({"event": "playback_state", "data": {"call_sign": "KEXP"}})
            player.send_json({"event": "ping"})
            while player.receive_json().get("event") != "pong":
                pass

            with client.websocket_connect("/switchboard/testuser1/player1") as controller:
                controller.send_json({"event": "authenticate", "data": {"token": access.token}})
                assert controller.receive_json() == {
                    "event": "authenticated",
                    "data": {"expires_at": access.expires_at},
                }
                retained: dict[str, object] = {}
                while not {"playback_state", "radio_dial_state"}.issubset(retained):
                    message = controller.receive_json()
                    retained[message["event"]] = message["data"]
                assert retained["playback_state"] == {"call_sign": "KEXP"}
                assert retained["radio_dial_state"] == {
                    "url": PLAYER_RADIO_DIAL_URL,
                    "revision": PLAYER_RADIO_DIAL_REVISION,
                }

            with client.websocket_connect("/switchboard/testuser1/player1") as signed_out:
                signed_out.send_json({"event": "authenticate", "data": {"token": None}})
                with pytest.raises(WebSocketDisconnect) as error:
                    signed_out.receive_json()
                assert error.value.code == 1008
                assert error.value.reason == "Authentication required"

            _close_player(player, "testuser1/player1")


async def test_controller_session_closes_at_token_expiry() -> None:
    websocket = AsyncMock()

    async def wait_for_message() -> str:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    websocket.receive_text.side_effect = wait_for_message

    await _run_loop(websocket, Broadcast(), "acct/player1", is_player=False, expires_at=0)

    websocket.close.assert_awaited_once_with(code=1008, reason="Authentication required")


async def test_offline_controller_receives_player_presence() -> None:
    websocket = AsyncMock()
    websocket.receive_text.side_effect = WebSocketDisconnect()

    await _run_loop(websocket, Broadcast(), "acct/player1", is_player=False)

    websocket.send_json.assert_awaited_once_with({"event": "player_presence", "data": {"connected": False}})


async def test_slow_websocket_send_ends_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    async def wait_forever(*_args: object) -> str:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    websocket = AsyncMock()
    websocket.send_text.side_effect = wait_forever
    websocket.receive_text.side_effect = wait_forever
    broadcast = Broadcast()
    broadcast.set_state("acct/player1", "playback_state", '{"event":"playback_state","data":{}}')
    monkeypatch.setattr("switchboard.switchboard.WEBSOCKET_SEND_TIMEOUT_SECONDS", 0.01)

    await asyncio.wait_for(_run_loop(websocket, broadcast, "acct/player1", is_player=True), timeout=1)


def test_duplicate_player_connection_is_rejected(switchboard_client: TestClient) -> None:
    with switchboard_client.websocket_connect("switchboard/acct/player1", headers=PLAYER_HEADERS) as player:
        with switchboard_client.websocket_connect("switchboard/acct/player1", headers=PLAYER_HEADERS) as duplicate:
            with pytest.raises(WebSocketDisconnect) as error:
                duplicate.receive_json()
        _close_player(player)
    assert error.value.code == 4002


def test_disconnected_player_state_is_not_retained(switchboard_client: TestClient) -> None:
    player_key = "acct/player1"
    broadcast = cast(FastAPI, switchboard_client.app).state.broadcast

    with switchboard_client.websocket_connect("switchboard/acct/player1", headers=PLAYER_HEADERS) as player:
        player.send_json({"event": "ping"})
        while player.receive_json().get("event") != "pong":
            pass
        assert player_key in broadcast._channel_state
        _close_player(player)

    assert player_key not in broadcast._channel_state


# -- protocol behavior --


@pytest.mark.parametrize(
    "message",
    [
        "not-json",
        '{"data":"should be ignored"}',
        "[]",
    ],
    ids=["invalid-json", "missing-event", "non-object"],
)
def test_ignored_messages_keep_connection_open(switchboard_client: TestClient, message: str) -> None:
    with switchboard_client.websocket_connect("switchboard/acct/player1", headers=PLAYER_HEADERS) as ws:
        ws.send_text(message)
        ws.send_json({"event": "ping"})
        while (resp := ws.receive_json())["event"] != "pong":
            pass
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
