from contextlib import nullcontext
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from api.api import lifespan
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


@pytest.mark.parametrize("failure", [None, "startup", "body"])
async def test_lifespan_cleans_up_resources_on_success_and_failure(
    monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    closed: list[str] = []
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.side_effect = lambda *_: closed.append("http")
    broadcast = Mock(disconnect=AsyncMock(side_effect=lambda: closed.append("broadcast")))
    watcher = Mock(close=AsyncMock(side_effect=lambda: closed.append("watcher")))
    monkeypatch.setattr("httpx2.AsyncClient", Mock(return_value=client))
    monkeypatch.setattr("api.api.Broadcast", Mock(return_value=broadcast))
    watcher_factory = Mock(return_value=watcher)
    if failure == "startup":
        watcher_factory.side_effect = RuntimeError("startup failed")
    monkeypatch.setattr("switchboard.radio_dials.RadioDialWatcher", watcher_factory)
    app = FastAPI()
    app.state.profiles = ["switchboard"]

    with pytest.raises(RuntimeError) if failure else nullcontext():
        async with lifespan(app):
            if failure == "body":
                raise RuntimeError("lifespan failed")

    assert closed == (["broadcast", "http"] if failure == "startup" else ["watcher", "broadcast", "http"])
