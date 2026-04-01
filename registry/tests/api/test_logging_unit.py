import logging
from collections.abc import Generator

import pytest

from lib.logging import (
    SILENCED_ENDPOINTS,
    SilentEndpointFilter,
    access_logger,
    silence_access_logs,
)


def make_record(path: str) -> logging.LogRecord:
    # Create a synthetic LogRecord similar to uvicorn.access: args tuple where index 2 is path
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="access",
        args=(None, None, path),
        exc_info=None,
    )
    return record


@pytest.fixture(autouse=True)
def _reset_logging_state() -> Generator[None]:
    """Ensure tests are isolated from global logger/filter state."""
    prior_filters = list(access_logger.filters)
    prior_silenced = set(SILENCED_ENDPOINTS)
    # Remove our filter instances and clear set before each test
    for f in list(access_logger.filters):
        if isinstance(f, SilentEndpointFilter):
            access_logger.removeFilter(f)
    SILENCED_ENDPOINTS.clear()
    try:
        yield
    finally:
        # Clean up any filter instances added by a test
        for f in list(access_logger.filters):
            if isinstance(f, SilentEndpointFilter):
                access_logger.removeFilter(f)
        # Restore original state
        for f in prior_filters:
            if f not in access_logger.filters:
                access_logger.addFilter(f)
        SILENCED_ENDPOINTS.clear()
        SILENCED_ENDPOINTS.update(prior_silenced)


def test_silence_access_logs_registers_filter_once() -> None:
    # Initially no SilentEndpointFilter should be attached by tests
    assert sum(isinstance(f, SilentEndpointFilter) for f in access_logger.filters) == 0

    silence_access_logs("/healthz")
    assert sum(isinstance(f, SilentEndpointFilter) for f in access_logger.filters) == 1

    # Second call should not add another filter
    silence_access_logs("/metrics")
    assert sum(isinstance(f, SilentEndpointFilter) for f in access_logger.filters) == 1


def test_silence_access_logs_accepts_str_and_iterable() -> None:
    silence_access_logs("/one")
    assert "/one" in SILENCED_ENDPOINTS
    assert len(SILENCED_ENDPOINTS) == 1

    silence_access_logs(["/two", "/three"])
    assert SILENCED_ENDPOINTS == {"/one", "/two", "/three"}


def test_installed_filter_blocks_silenced_and_allows_others() -> None:
    silence_access_logs(["/healthz", "/quiet"])  # installs filter and registers endpoints
    # Get our installed filter instance
    f = next(f for f in access_logger.filters if isinstance(f, SilentEndpointFilter))

    assert f.filter(make_record("/healthz")) is False
    assert f.filter(make_record("/quiet")) is False
    assert f.filter(make_record("/normal")) is True
