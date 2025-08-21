from pathlib import Path

import pytest

from datastore.backends import LocalBackend
from datastore.core import ModelStore
from models.account import Account, AccountCreate


def test_template_requires_id_at_end(tmp_path: Path) -> None:
    store = LocalBackend(str(tmp_path))
    with pytest.raises(ValueError):
        ModelStore(store, model=Account, create_model=AccountCreate, path_template="accounts/{id}/oops")


def test_template_rejects_missing_id(tmp_path: Path) -> None:
    store = LocalBackend(str(tmp_path))
    with pytest.raises(ValueError):
        ModelStore(store, model=Account, create_model=AccountCreate, path_template="accounts/{account_id}")


def test_template_rejects_id_in_dir_portion(tmp_path: Path) -> None:
    store = LocalBackend(str(tmp_path))
    with pytest.raises(ValueError):
        ModelStore(store, model=Account, create_model=AccountCreate, path_template="accounts/{id}/{id}")


def test_placeholders_require_path_params(tmp_path: Path) -> None:
    store = LocalBackend(str(tmp_path))
    repo: ModelStore[Account, AccountCreate] = ModelStore(
        store, model=Account, create_model=AccountCreate, path_template="accounts/{account_id}/{id}"
    )
    with pytest.raises(ValueError):
        repo.get("x")
    with pytest.raises(ValueError):
        repo.list()
    with pytest.raises(ValueError):
        repo.merge_upsert("x", AccountCreate(name="test"))


def test_placeholders_accepted_and_injected(tmp_path: Path) -> None:
    store = LocalBackend(str(tmp_path))
    repo: ModelStore[Account, AccountCreate] = ModelStore(
        store, model=Account, create_model=AccountCreate, path_template="accounts/{account_id}/{id}"
    )
    repo.merge_upsert("acc1", AccountCreate(name="A"), path_params={"account_id": "acct"})
    got = repo.get("acc1", path_params={"account_id": "acct"})
    assert got is not None
    assert got.id == "acc1"
