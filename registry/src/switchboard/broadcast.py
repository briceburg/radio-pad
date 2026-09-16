"""In-memory channel pub-sub for player/controller rooms."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

logger = logging.getLogger(__name__)
DEFAULT_SUBSCRIBER_QUEUE_SIZE = 64


@dataclass(frozen=True, slots=True)
class Event:
    """A message published to a channel."""

    channel: str
    message: str


class Subscriber:
    """Async iterator that yields events from a subscription queue."""

    def __init__(self, queue: asyncio.Queue[Event]) -> None:
        self._queue = queue

    def __aiter__(self) -> Subscriber:
        return self

    async def __anext__(self) -> Event:
        try:
            return await self._queue.get()
        except asyncio.QueueShutDown:
            raise StopAsyncIteration from None


class Broadcast:
    """In-memory channel pub-sub."""

    def __init__(self, *, subscriber_queue_size: int = DEFAULT_SUBSCRIBER_QUEUE_SIZE) -> None:
        if subscriber_queue_size < 1:
            raise ValueError("subscriber_queue_size must be positive")
        self._subscriber_queue_size = subscriber_queue_size
        self._channels: dict[str, set[asyncio.Queue[Event]]] = {}
        self._channel_state: dict[str, dict[str, str]] = {}

    def _remove_subscriber(self, channel: str, queue: asyncio.Queue[Event]) -> None:
        subscribers = self._channels.get(channel)
        if subscribers is None:
            return
        subscribers.discard(queue)
        if not subscribers:
            del self._channels[channel]

    async def connect(self) -> None:
        """Prepare the broadcast (no-op for in-memory backend)."""

    async def disconnect(self) -> None:
        """Shut down: signal all active subscribers to stop."""
        for queues in self._channels.values():
            for q in queues:
                q.shutdown(immediate=True)
        self._channels.clear()
        self._channel_state.clear()

    async def publish(self, channel: str, message: str) -> None:
        """Send *message* to every subscriber on *channel*."""
        event = Event(channel=channel, message=message)
        for q in list(self._channels.get(channel, ())):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Disconnecting slow subscriber on channel %s", channel)
                self._remove_subscriber(channel, q)
                q.shutdown(immediate=True)

    def set_state(self, channel: str, key: str, message: str) -> None:
        """Record *message* as retained state for *channel* under *key*."""
        self._channel_state.setdefault(channel, {})[key] = message

    def clear_state(self, channel: str) -> None:
        """Remove all retained state for *channel*."""
        self._channel_state.pop(channel, None)

    def clear_state_key(self, channel: str, key: str) -> None:
        """Remove one retained state item for *channel*."""
        channel_state = self._channel_state.get(channel)
        if not channel_state:
            return
        channel_state.pop(key, None)
        if not channel_state:
            self._channel_state.pop(channel, None)

    @asynccontextmanager
    async def subscribe(self, channel: str, *, replay: bool = False) -> AsyncIterator[Subscriber]:
        """Yield a :class:`Subscriber` that receives events on *channel*.

        If *replay* is ``True``, any retained state messages for the channel
        are enqueued before live messages start flowing.
        """
        retained = list(self._channel_state.get(channel, {}).values()) if replay else []
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=max(self._subscriber_queue_size, len(retained)))
        for message in retained:
            queue.put_nowait(Event(channel=channel, message=message))
        self._channels.setdefault(channel, set()).add(queue)
        try:
            yield Subscriber(queue)
        finally:
            self._remove_subscriber(channel, queue)
            queue.shutdown(immediate=True)
