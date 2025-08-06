import shutil
import uuid
from pathlib import Path

import pytest

from datastore import DataStore


@pytest.fixture
def temp_data_path(unit_tests_root: Path) -> Path:
    """Provide a project-level temporary data directory for datastore unit tests.
    Uses <project>/tmp/tests/unit/datastore/data so artifacts are inspectable after runs.
    Cleaned before each use for isolation.
    """
    base = unit_tests_root / "datastore" / "data"
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)
    return base


@pytest.fixture
def datastore_factory(unit_tests_root: Path):
    """Factory to create isolated DataStore instances under <project>/tmp/tests/unit/datastore/stores/<uuid>."""
    root_base = unit_tests_root / "datastore" / "stores"
    root_base.mkdir(parents=True, exist_ok=True)

    def _make(**kwargs):
        store_root = root_base / uuid.uuid4().hex
        store_root.mkdir()
        return DataStore(data_path=str(store_root), **kwargs)

    return _make
