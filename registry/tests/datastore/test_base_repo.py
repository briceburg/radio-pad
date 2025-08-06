import pytest

from datastore import ModelStore
from datastore.backends.json_file_store import JSONFileStore
from models.account import Account


def test_template_requires_id_at_end(tmp_path):
    store = JSONFileStore(str(tmp_path))
    with pytest.raises(ValueError):
        ModelStore(store, model=Account, path_template="accounts/{id}/oops")


def test_template_rejects_missing_id(tmp_path):
    store = JSONFileStore(str(tmp_path))
    with pytest.raises(ValueError):
        ModelStore(store, model=Account, path_template="accounts/{account_id}")


def test_template_rejects_id_in_dir_portion(tmp_path):
    store = JSONFileStore(str(tmp_path))
    with pytest.raises(ValueError):
        ModelStore(store, model=Account, path_template="accounts/{id}/{id}")


def test_placeholders_require_path_params(tmp_path):
    store = JSONFileStore(str(tmp_path))
    repo = ModelStore(store, model=Account, path_template="accounts/{account_id}/{id}")
    with pytest.raises(ValueError):
        repo.get("x")
    with pytest.raises(ValueError):
        repo.list()
    with pytest.raises(ValueError):
        repo.merge_upsert("x", {})


def test_placeholders_accepted_and_injected(tmp_path):
    store = JSONFileStore(str(tmp_path))
    repo = ModelStore(store, model=Account, path_template="accounts/{account_id}/{id}")
    repo.merge_upsert("acc1", {"name": "A"}, path_params={"account_id": "acct"})
    got = repo.get("acc1", path_params={"account_id": "acct"})
    assert got is not None
    assert got.id == "acc1"
