import os
import time

import httpx2
import jwt
import pytest

_OIDC_AUDIENCE = "radiopad-integration"
_OIDC_ISSUER = "http://oidc:8080"
_OIDC_SECRET = "radio-pad-integration-oidc-secret"


def _oidc_token(subject):
    now = int(time.time())
    return jwt.encode(
        {
            "aud": _OIDC_AUDIENCE,
            "email": "briceburg@gmail.com",
            "email_verified": True,
            "exp": now + 300,
            "iat": now,
            "iss": _OIDC_ISSUER,
            "name": "Integration User",
            "sub": subject,
        },
        _OIDC_SECRET,
        algorithm="HS256",
        headers={"kid": "integration"},
    )


@pytest.fixture(scope="session")
def registry_url():
    return os.environ["REGISTRY_URL"]


@pytest.fixture(scope="session")
def switchboard_url():
    return os.environ["SWITCHBOARD_URL"]


@pytest.fixture(scope="session")
def remote_control_url():
    return os.environ["REMOTE_CONTROL_URL"]


@pytest.fixture(scope="session")
def http():
    """Shared HTTP client that follows redirects (handles FastAPI slash redirects)."""
    with httpx2.Client(follow_redirects=True) as client:
        yield client


@pytest.fixture(scope="session")
def oidc_token():
    return _oidc_token


@pytest.fixture(scope="session")
def registry_session(http, registry_url):
    status = http.get(f"{registry_url}/auth/status")
    assert status.status_code == 200
    if not status.json()["enabled"]:
        return None
    response = http.post(
        f"{registry_url}/auth/session",
        headers={"Authorization": f"Bearer {_oidc_token('active-user')}"},
    )
    assert response.status_code == 200
    return response
