from __future__ import annotations

import json
import re
from pathlib import Path

from lib.logging import logger

from ..exceptions import ConcurrencyError
from .interfaces import SeedableStore


def seed_from_path(seed_path: Path, stores: list[SeedableStore], *, label: str) -> None:
    if not seed_path.is_dir():
        logger.error("%s seed path does not exist: %s", label, seed_path)
        return

    for seed_file in seed_path.rglob("*.json"):
        relative_path = seed_file.relative_to(seed_path).as_posix()

        for store in stores:
            if not (params := store.match(relative_path)):
                continue

            object_id = params.pop("id")
            path_params = params or None
            if store.exists(object_id, path_params=path_params):
                logger.debug("Skipping existing %s object: %s", label, relative_path)
                break

            with seed_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            try:
                store.seed({"id": object_id, **params, **data}, path_params=path_params)
            except ConcurrencyError:
                logger.debug("Skipping existing %s object: %s", label, relative_path)
            else:
                logger.info("Seeded %s %s", label, relative_path)
            break


def match_path_template(path: str, template: str) -> dict[str, str] | None:
    """Matches a path against a template, extracting placeholder values using regex.

    Returns a dictionary of extracted values if the path matches the template,
    otherwise returns None.
    """
    regex_pattern = _template_placeholder_re.sub(r"(?P<\1>[^/]+)", template)
    match = re.fullmatch(regex_pattern, path)
    return match.groupdict() if match else None


_template_placeholder_re = re.compile(r"\{([^}]+)\}")
