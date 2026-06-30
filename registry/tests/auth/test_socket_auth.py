"""Socket auth validation tests (validate_remote path)."""

from unittest.mock import AsyncMock

import httpx2
import pytest
from fastapi import WebSocketException

from auth.socket_auth import validate_remote


@pytest.fixture
def mock_request() -> AsyncMock:
    req = AsyncMock()
    req.app.state.http_client = AsyncMock()
    return req


@pytest.mark.parametrize(
    ("token", "headers"),
    [("valid-token", {"Authorization": "Bearer valid-token"}), (None, {})],
)
async def test_validate_remote_forwards_optional_token(
    mock_request: AsyncMock,
    token: str | None,
    headers: dict[str, str],
) -> None:
    mock_response = httpx2.Response(204, request=httpx2.Request("GET", "http://test"))
    mock_request.app.state.http_client.get.return_value = mock_response

    await validate_remote(mock_request, "acct", "player1", token)
    mock_request.app.state.http_client.get.assert_called_once_with(
        "http://localhost:8000/api/auth/players/acct/player1/control",
        headers=headers,
    )


@pytest.mark.parametrize("response_status", [401, 403, 404])
async def test_validate_remote_rejects_denied_access(mock_request: AsyncMock, response_status: int) -> None:
    mock_response = httpx2.Response(response_status, request=httpx2.Request("GET", "http://test"))
    mock_request.app.state.http_client.get.return_value = mock_response

    with pytest.raises(WebSocketException) as exc:
        await validate_remote(mock_request, "acct", "player1", "bad-token")

    assert exc.value.code == 1008
    assert "Unauthorized" in exc.value.reason


@pytest.mark.parametrize(
    "error",
    [httpx2.ConnectError("Connection refused"), httpx2.TimeoutException("Timeout")],
)
async def test_validate_remote_reports_transport_errors(mock_request: AsyncMock, error: httpx2.HTTPError) -> None:
    mock_request.app.state.http_client.get.side_effect = error

    with pytest.raises(WebSocketException) as exc:
        await validate_remote(mock_request, "acct", "player1", "token")

    assert exc.value.code == 1011
    assert "internal error" in exc.value.reason


async def test_validate_remote_reports_registry_errors(mock_request: AsyncMock) -> None:
    mock_request.app.state.http_client.get.return_value = httpx2.Response(
        500,
        request=httpx2.Request("GET", "http://test"),
    )

    with pytest.raises(WebSocketException) as exc:
        await validate_remote(mock_request, "acct", "player1", "token")

    assert exc.value.code == 1011
    assert "internal error" in exc.value.reason
