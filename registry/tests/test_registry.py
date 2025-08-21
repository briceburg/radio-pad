from starlette.testclient import TestClient


def test_root_and_healthz(client: TestClient) -> None:
    # Root should redirect to /docs
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers.get("location") == "/docs"

    # Health endpoint
    h = client.get("/healthz")
    assert h.status_code == 204
    assert h.content == b""
    assert h.headers.get("cache-control") == "no-store"
