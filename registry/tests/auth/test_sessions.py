from __future__ import annotations

import pytest

from auth import AccessTokens, AuthenticatedIdentity, RegistryIDToken, SessionError

_SECRET = "test-session-secret-value-32-bytes"


def _identity() -> AuthenticatedIdentity:
    return AuthenticatedIdentity(
        issuer="https://issuer.example",
        subject="user-123",
        authenticated_at=1_700_000_000,
        email="owner@example.com",
        email_verified=True,
        name="Owner",
    )


def test_access_token_round_trip_tampering_and_expiry() -> None:
    now = [1_700_000_100.0]
    tokens = AccessTokens(_SECRET, clock=lambda: now[0], ttl_seconds=60)
    issued = tokens.issue(_identity())

    assert issued.expires_at == 1_700_000_160
    assert tokens.authenticate(issued.token) == issued.identity

    with pytest.raises(SessionError, match="Invalid access token"):
        tokens.authenticate(f"{issued.token[:-2]}xx")

    now[0] += 60
    with pytest.raises(SessionError, match="Session expired"):
        tokens.authenticate(issued.token)


def test_oidc_identity_prefers_original_authentication_time() -> None:
    token = RegistryIDToken(
        iss="https://issuer.example",
        sub="user-123",
        aud="radio-pad-remote-control",
        exp=1_700_000_600,
        iat=1_700_000_100,
    )

    assert AccessTokens.identity_from_oidc(token).authenticated_at == token.iat
    refreshed = token.model_copy(update={"iat": 1_700_000_200, "auth_time": token.iat})
    assert AccessTokens.identity_from_oidc(refreshed).authenticated_at == token.iat
    with pytest.raises(SessionError, match="Invalid OIDC authentication time"):
        AccessTokens.identity_from_oidc(token.model_copy(update={"auth_time": token.iat + 1}))


def test_access_token_secret_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REGISTRY_AUTH_SESSION_SECRET", raising=False)
    with pytest.raises(ValueError, match="must be set"):
        AccessTokens.from_env()

    monkeypatch.setenv("REGISTRY_AUTH_SESSION_SECRET", _SECRET)
    assert isinstance(AccessTokens.from_env(), AccessTokens)
