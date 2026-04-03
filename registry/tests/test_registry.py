from starlette.testclient import TestClient

from lib.constants import API_VERSION


def test_root_and_healthz(client: TestClient) -> None:
    # Root should redirect to /docs
    r = client.get("http://testserver/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers.get("location") in ("http://testserver/docs", "/docs")
    assert r.headers.get("X-RadioPad-Api-Version") == API_VERSION

    # Health endpoint
    h = client.get("http://testserver/healthz")
    assert h.status_code == 204
    assert h.content == b""
    assert h.headers.get("cache-control") == "no-store"
    assert h.headers.get("X-RadioPad-Api-Version") == API_VERSION
