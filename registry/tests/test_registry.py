import pytest
from starlette.testclient import TestClient

from lib.constants import API_VERSION
from registry import create_app


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


def test_switchboard_requires_one_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEB_CONCURRENCY", "2")

    create_app(profiles=["api"])
    with pytest.raises(ValueError, match="WEB_CONCURRENCY=1"):
        create_app(profiles=["switchboard"])
