from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, call

import httpx2

from switchboard.radio_dials import RadioDialWatcher


async def test_watcher_polls_shared_dial_once_and_notifies_each_player_room() -> None:
    url = "https://public.example/api/accounts/community/radio-dials/briceburg"
    fetch_url = "https://registry.example/api/accounts/community/radio-dials/briceburg"
    response = httpx2.Response(200, headers={"ETag": '"new"'}, request=httpx2.Request("GET", fetch_url))
    get = AsyncMock(return_value=response)
    client = cast(httpx2.AsyncClient, SimpleNamespace(get=get))
    publish = AsyncMock()
    watcher = RadioDialWatcher(client, publish, registry_url="https://registry.example/api")
    watcher.register(url, "briceburg/living-room", '"old"')
    watcher.register(url, "briceburg/canones", '"old"')

    await watcher.refresh()

    get.assert_awaited_once_with(fetch_url, headers={"If-None-Match": '"old"'})
    state = {"url": url, "revision": '"new"'}
    publish.assert_has_awaits(
        [
            call("briceburg/canones", "radio_dial_state", state),
            call("briceburg/living-room", "radio_dial_state", state),
        ],
        any_order=True,
    )
    watcher.register(url, "briceburg/kitchen", '"old"')
    await watcher.refresh()
    publish.assert_awaited_with(
        "briceburg/kitchen",
        "radio_dial_state",
        state,
    )


async def test_watcher_ignores_unchanged_dial_and_stops_after_last_player() -> None:
    url = "https://registry.example/api/accounts/community/radio-dials/briceburg"
    response = httpx2.Response(304, request=httpx2.Request("GET", url))
    get = AsyncMock(return_value=response)
    client = cast(httpx2.AsyncClient, SimpleNamespace(get=get))
    publish = AsyncMock()
    watcher = RadioDialWatcher(client, publish, registry_url="https://registry.example/api")
    watcher.register(url, "briceburg/living-room", '"same"')

    await watcher.refresh()
    watcher.unregister(url, "briceburg/living-room")
    await watcher.refresh()

    get.assert_awaited_once_with(url, headers={"If-None-Match": '"same"'})
    publish.assert_not_awaited()


async def test_watcher_does_not_fetch_non_registry_resource() -> None:
    get = AsyncMock()
    client = cast(httpx2.AsyncClient, SimpleNamespace(get=get))
    watcher = RadioDialWatcher(client, AsyncMock())

    watcher.register("http://169.254.169.254/latest/meta-data", "briceburg/living-room", '"v1"')
    await watcher.refresh()

    get.assert_not_awaited()
