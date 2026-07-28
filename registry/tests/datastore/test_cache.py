from __future__ import annotations

from datastore.core import ExpiringCache


def test_expiring_cache_loads_once_until_expiry_or_invalidation() -> None:
    now = [10.0]
    loads: list[str] = []
    cache: ExpiringCache[str, str | None] = ExpiringCache(ttl_seconds=5, clock=lambda: now[0])

    def load() -> str:
        loads.append("load")
        return "value"

    assert cache.get_or_load("document", load) == "value"
    assert cache.get_or_load("document", load) == "value"
    assert loads == ["load"]

    now[0] = 15.0
    assert cache.get_or_load("document", load) == "value"
    assert loads == ["load", "load"]

    cache.invalidate("document")
    assert cache.get_or_load("document", load) == "value"
    assert loads == ["load", "load", "load"]
