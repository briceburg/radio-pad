"""Socket auth validation tests (validate_remote path)."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import WebSocketException

from auth.socket_auth import validate_remote


async def test_validate_remote_success() -> None:
    """200 response passes validation."""
    mock_response = httpx.Response(200)
    with patch("auth.socket_auth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await validate_remote("acct", "player1", "valid-token")
        mock_client.get.assert_called_once()


async def test_validate_remote_unauthorized() -> None:
    """Non-200 response raises WS_1008_POLICY_VIOLATION."""
    mock_response = httpx.Response(403)
    with patch("auth.socket_auth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(WebSocketException) as exc_info:
            await validate_remote("acct", "player1", "bad-token")
        assert exc_info.value.code == 1008


async def test_validate_remote_network_error() -> None:
    """Network error raises WS_1011_INTERNAL_ERROR."""
    with patch("auth.socket_auth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(WebSocketException) as exc_info:
            await validate_remote("acct", "player1", "token")
        assert exc_info.value.code == 1011


async def test_validate_remote_timeout() -> None:
    """Timeout raises WS_1011_INTERNAL_ERROR."""
    with patch("auth.socket_auth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ReadTimeout("timeout")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(WebSocketException) as exc_info:
            await validate_remote("acct", "player1", "token")
        assert exc_info.value.code == 1011


async def test_validate_remote_sends_bearer_header() -> None:
    """Token is sent as Bearer authorization header."""
    mock_response = httpx.Response(200)
    with patch("auth.socket_auth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await validate_remote("acct", "player1", "my-token")
        call_kwargs = mock_client.get.call_args
        assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer my-token"


async def test_validate_remote_no_token() -> None:
    """No token sends no Authorization header."""
    mock_response = httpx.Response(200)
    with patch("auth.socket_auth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await validate_remote("acct", "player1", None)
        call_kwargs = mock_client.get.call_args
        assert "Authorization" not in call_kwargs.kwargs["headers"]
