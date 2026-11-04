import fcntl
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import RLock


class InterProcessLock:
    """Serialize operations across threads and processes using one lock file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._thread_lock = RLock()

    @contextmanager
    def __call__(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._thread_lock, self.path.open("a+b") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
