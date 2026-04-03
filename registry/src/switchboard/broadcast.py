"""Lightweight channel-based pub-sub for the switchboard.

Provides a channel-based publish/subscribe API used by the switchboard to relay
WebSocket messages between players and controllers connected to the same
``{account_id}/{player_id}`` channel.

The default (and currently only) backend keeps channels in memory, which is
sufficient for single-instance deployments and test suites.  Multi-instance
deployments should use path-based sticky sessions so all connections for a
given player channel land on the same process.  If truly stateless horizontal
scaling is needed later, add a backend (e.g. NATS) behind the same
:class:`Broadcast` interface.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Event:
    """A message published to a channel."""

    channel: str
    message: str


class Subscriber:
    """Async iterator that yields events from a subscription queue."""

    def __init__(self, queue: asyncio.Queue[Event | None]) -> None:
        self._queue = queue

    def __aiter__(self) -> Subscriber:
        return self

    async def __anext__(self) -> Event:
        item = await self._queue.get()
        if item is None:
            raise StopAsyncIteration
        return item


class Broadcast:
    """In-memory channel pub-sub.

    Usage::

        broadcast = Broadcast()
        await broadcast.connect()

        await broadcast.publish("acme/player1", '{"event": "hello"}')

        async with broadcast.subscribe("acme/player1") as sub:
            async for event in sub:
                print(event.message)

        await broadcast.disconnect()
    """

    def __init__(self) -> None:
        self._channels: dict[str, set[asyncio.Queue[Event | None]]] = {}

    async def connect(self) -> None:
        """Prepare the broadcast (no-op for in-memory backend)."""

    async def disconnect(self) -> None:
        """Shut down: signal all active subscribers to stop."""
        for queues in self._channels.values():
            for q in queues:
                q.put_nowait(None)
        self._channels.clear()

    async def publish(self, channel: str, message: str) -> None:
        """Send *message* to every subscriber on *channel*."""
        for q in list(self._channels.get(channel, ())):
            await q.put(Event(channel=channel, message=message))

    @asynccontextmanager
    async def subscribe(self, channel: str) -> AsyncIterator[Subscriber]:
        """Yield a :class:`Subscriber` that receives events on *channel*."""
        queue: asyncio.Queue[Event | None] = asyncio.Queue()
        self._channels.setdefault(channel, set()).add(queue)
        try:
            yield Subscriber(queue)
        finally:
            subs = self._channels.get(channel)
            if subs is not None:
                subs.discard(queue)
                if not subs:
                    del self._channels[channel]
            # Signal the subscriber to stop iterating
            queue.put_nowait(None)
