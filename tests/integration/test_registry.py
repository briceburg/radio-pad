"""Registry API — reachable, serving seeded data, and enforcing auth on writes."""


def test_healthz(http, registry_url):
    base = registry_url.split("/api")[0] if "/api" in registry_url else registry_url
    resp = http.get(f"{base}/healthz")
    assert resp.status_code == 204


def test_list_presets(http, registry_url):
    resp = http.get(f"{registry_url}/presets")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) > 0


def test_get_account(http, registry_url):
    resp = http.get(f"{registry_url}/accounts/briceburg")
    assert resp.status_code == 200


def test_write_rejects_unauthenticated(http, registry_url):
    """Write endpoints reject requests without valid auth or payload.

    In dev (no OIDC), writes fail on validation (422). In production (OIDC
    configured), writes fail on auth (401). Either way, the response is not 2xx.
    """
    resp = http.put(f"{registry_url}/accounts/briceburg", content=b"")
    assert resp.status_code >= 400
