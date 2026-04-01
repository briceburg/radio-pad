import logging
from collections.abc import Iterable

logger = logging.getLogger("uvicorn")
access_logger = logging.getLogger("uvicorn.access")

SILENCED_ENDPOINTS: set[str] = set()


def silence_access_logs(endpoints: str | Iterable[str]) -> None:
    if isinstance(endpoints, str):
        SILENCED_ENDPOINTS.add(endpoints)
    else:
        SILENCED_ENDPOINTS.update(endpoints)

    # Lazily register filter so it's added only when caller intends to silence endpoints.
    if not any(isinstance(f, SilentEndpointFilter) for f in access_logger.filters):
        access_logger.addFilter(SilentEndpointFilter())


class SilentEndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not (isinstance(record.args, tuple) and len(record.args) > 2 and record.args[2] in SILENCED_ENDPOINTS)
