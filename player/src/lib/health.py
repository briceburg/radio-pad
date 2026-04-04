import os
from pathlib import Path

DEFAULT_HEALTH_PATH = "/tmp/radio-pad-ready"


def health_path(path: str | None = None) -> Path:
    return Path(path or os.getenv("RADIOPAD_HEALTH_PATH", DEFAULT_HEALTH_PATH))


def mark_healthy(path: str | None = None) -> None:
    target = health_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("ready\n")


def clear_health(path: str | None = None) -> None:
    health_path(path).unlink(missing_ok=True)
