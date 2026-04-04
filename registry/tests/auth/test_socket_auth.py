"""Socket auth validation tests (validate_remote path)."""

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import WebSocketException

from auth.socket_auth import validate_remote


@pytest.fixture
def mock_request() -> AsyncMock:
    req = AsyncMock()
    req.app.state.http_client = AsyncMock()
    return req


async def test_validate_remote_success(mock_request: AsyncMock) -> None:
    """200 response passes validation."""
    mock_response = httpx.Response(200, request=httpx.Request("GET", "http://test"))
    mock_request.app.state.http_client.get.return_value = mock_response

    await validate_remote(mock_request, "acct", "player1", "valid-token")
    mock_request.app.state.http_client.get.assert_called_once()


async def test_validate_remote_unauthorized(mock_request: AsyncMock) -> None:
    """Non-200 response raises WS_1008_POLICY_VIOLATION."""
    mock_response = httpx.Response(403, request=httpx.Request("GET", "http://test"))
    mock_request.app.state.http_client.get.return_value = mock_response

    with pytest.raises(WebSocketException) as exc:
        await validate_remote(mock_request, "acct", "player1", "bad-token")

    assert exc.value.code == 1008
    assert "Unauthorized" in exc.value.reason


async def test_validate_remote_http_error(mock_request: AsyncMock) -> None:
    """Network connection errors raise WS_1011_INTERNAL_ERROR."""
    mock_request.app.state.http_client.get.side_effect = httpx.ConnectError("Connection refused")

    with pytest.raises(WebSocketException) as exc:
        await validate_remote(mock_request, "acct", "player1", "token")

    assert exc.value.code == 1011
    assert "internal error" in exc.value.reason


async def test_validate_remote_timeout(mock_request: AsyncMock) -> None:
    """Network timeouts raise WS_1011_INTERNAL_ERROR."""
    mock_request.app.state.http_client.get.side_effect = httpx.TimeoutException("Timeout")

    with pytest.raises(WebSocketException) as exc:
        await validate_remote(mock_request, "acct", "player1", "token")

    assert exc.value.code == 1011
    assert "internal error" in exc.value.reason


async def test_validate_remote_headers_token(mock_request: AsyncMock) -> None:
    """Bearer token is included in Authorization header."""
    mock_response = httpx.Response(200, request=httpx.Request("GET", "http://test"))
    mock_request.app.state.http_client.get.return_value = mock_response

    await validate_remote(mock_request, "acct", "player1", "my-token")

    mock_request.app.state.http_client.get.assert_called_once()
    _, kwargs = mock_request.app.state.http_client.get.call_args
    assert kwargs.get("headers") == {"Authorization": "Bearer my-token"}


async def test_validate_remote_headers_no_token(mock_request: AsyncMock) -> None:
    """No token results in empty headers."""
    mock_response = httpx.Response(200, request=httpx.Request("GET", "http://test"))
    mock_request.app.state.http_client.get.return_value = mock_response

    await validate_remote(mock_request, "acct", "player1", None)

    mock_request.app.state.http_client.get.assert_called_once()
    _, kwargs = mock_request.app.state.http_client.get.call_args
    assert kwargs.get("headers") == {}
