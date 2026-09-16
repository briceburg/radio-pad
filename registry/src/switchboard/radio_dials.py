import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx2

from lib.constants import REGISTRY_URL, SLUG_PATTERN

logger = logging.getLogger(__name__)

type EventPublisher = Callable[[str, str, object], Awaitable[None]]


@dataclass
class _Watch:
    fetch_url: str
    channels: dict[str, str | None] = field(default_factory=dict)
    revision: str | None = None


class RadioDialWatcher:
    """Check each unique active RadioDial and publish revision changes to its player rooms."""

    def __init__(
        self,
        client: httpx2.AsyncClient,
        publish: EventPublisher,
        *,
        refresh_seconds: float = 30,
        concurrency: int = 16,
        registry_url: str = REGISTRY_URL,
    ) -> None:
        if refresh_seconds < 0:
            raise ValueError("refresh_seconds must be non-negative")
        if concurrency < 1:
            raise ValueError("concurrency must be positive")
        self._client = client
        self._publish = publish
        self._refresh_seconds = refresh_seconds
        self._concurrency = concurrency
        self._registry_url = registry_url.rstrip("/")
        self._watches: dict[str, _Watch] = {}
        self._wake = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="radio-dial-watcher")

    async def close(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)
        self._task = None

    def register(self, url: str, channel: str, revision: str | None) -> None:
        watch = self._watches.get(url)
        refresh = watch is None
        if watch is None:
            fetch_url = self._registry_resource_url(url)
            if fetch_url is None:
                logger.warning("Not watching non-Registry RadioDial URL: %s", url)
                return
            watch = self._watches[url] = _Watch(fetch_url=fetch_url, revision=revision)
        elif watch.revision != revision:
            refresh = True
        watch.channels[channel] = revision
        if refresh:
            self._wake.set()

    def unregister(self, url: str, channel: str) -> None:
        watch = self._watches.get(url)
        if watch is None:
            return
        watch.channels.pop(channel, None)
        if not watch.channels:
            self._watches.pop(url, None)

    async def refresh(self) -> None:
        urls = iter(tuple(self._watches))

        async def worker() -> None:
            for url in urls:
                await self._refresh_one(url)

        worker_count = min(self._concurrency, len(self._watches))
        await asyncio.gather(*(worker() for _ in range(worker_count)))

    async def _refresh_one(self, url: str) -> None:
        watch = self._watches.get(url)
        if watch is None:
            return
        headers = {"If-None-Match": watch.revision} if watch.revision else None
        try:
            response = await self._client.get(watch.fetch_url, headers=headers)
        except Exception as error:
            logger.warning("RadioDial watch failed for %s: %s", url, error)
            return
        if response.status_code == 304:
            await self._publish_stale_channels(url, watch)
            return
        if response.status_code != 200:
            logger.warning("RadioDial watch returned HTTP %s for %s", response.status_code, url)
            return
        revision = response.headers.get("etag")
        if not revision:
            logger.warning("RadioDial watch response has no ETag: %s", url)
            return

        current = self._watches.get(url)
        if current is not watch:
            return
        current.revision = revision
        await self._publish_stale_channels(url, current)

    async def _publish_stale_channels(self, url: str, watch: _Watch) -> None:
        if watch.revision is None:
            return
        state = {"url": url, "revision": watch.revision}
        for channel, revision in tuple(watch.channels.items()):
            if revision == watch.revision:
                continue
            await self._publish(channel, "radio_dial_state", state)
            if channel in watch.channels and watch.channels[channel] == revision:
                watch.channels[channel] = watch.revision

    async def _run(self) -> None:
        while True:
            self._wake.clear()
            await self.refresh()
            timeout = self._refresh_seconds if self._watches else None
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=timeout or None)
            except TimeoutError:
                pass

    def _registry_resource_url(self, source_url: str) -> str | None:
        parts = [part for part in urlsplit(source_url).path.split("/") if part]
        resource = parts[-4:]
        if (
            len(resource) != 4
            or resource[0] != "accounts"
            or resource[2] != "radio-dials"
            or not re.fullmatch(SLUG_PATTERN, resource[1])
            or not re.fullmatch(SLUG_PATTERN, resource[3])
        ):
            return None
        return f"{self._registry_url}/{'/'.join(resource)}"
