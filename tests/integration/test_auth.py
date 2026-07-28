"""Authenticated session flow through the real registry and switchboard."""

import pytest


def _cookie(response) -> str:
    return response.headers["set-cookie"].split(";", 1)[0]


def test_rolling_session_lifecycle(http, registry_url, registry_session, oidc_token):
    if registry_session is None:
        pytest.skip("requires the auth integration topology")

    created = registry_session
    session_cookie = _cookie(created)
    set_cookie = created.headers["set-cookie"].lower()
    assert "httponly" in set_cookie
    assert "max-age=2592000" in set_cookie

    access_token = created.json()["access_token"]
    control = http.get(
        f"{registry_url}/auth/players/briceburg/living-room/control",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert control.status_code == 204
    assert control.headers["radiopad-token-expires-at"] == str(created.json()["expires_at"])

    refreshed = http.post(
        f"{registry_url}/auth/session/refresh",
        headers={"Cookie": session_cookie, "RadioPad-Session": "refresh"},
    )
    assert refreshed.status_code == 200
    session_cookie = _cookie(refreshed)

    deleted = http.delete(f"{registry_url}/auth/session", headers={"Cookie": session_cookie})
    assert deleted.status_code == 204
    assert "expires=Thu, 01 Jan 1970 00:00:00 GMT" in deleted.headers["set-cookie"]
    assert (
        http.post(
            f"{registry_url}/auth/session/refresh",
            headers={"Cookie": _cookie(deleted), "RadioPad-Session": "refresh"},
        ).status_code
        == 401
    )

    revoked = http.post(
        f"{registry_url}/auth/session",
        headers={"Authorization": f"Bearer {oidc_token('revoked-user')}"},
    )
    assert revoked.status_code == 401
    assert revoked.json()["detail"] == "Session revoked—sign in again"
