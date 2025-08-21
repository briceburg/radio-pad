from pathlib import Path

from datastore import DataStore
from datastore.backends import LocalBackend
from models.account import Account
from tests.datastore.conftest import SeedCreator


def test_datastore_initialization() -> None:
    """DataStore initializes component stores."""
    real_store = DataStore(backend=LocalBackend(base_path="/tmp/fake"))
    assert real_store.accounts is not None
    assert real_store.players is not None
    assert real_store.global_presets is not None
    assert real_store.account_presets is not None


def test_datastore_isolation(tmp_path: Path) -> None:
    """Separate DataStore instances have independent backends and roots."""
    store1 = DataStore(backend=LocalBackend(base_path=str(tmp_path / "s1")))
    store2 = DataStore(backend=LocalBackend(base_path=str(tmp_path / "s2")))
    assert store1 is not store2
    assert store1.backend is not store2.backend


def test_seed_no_error(tmp_path: Path) -> None:
    """Calling seed on an empty seed path logs error but does not raise."""
    backend = LocalBackend(base_path=str(tmp_path / "data"))
    ds = DataStore(backend=backend, seed_path=str(tmp_path / "missing-seed"))
    ds.seed()  # Should not raise even if seed path missing


def test_seed_copies_json_and_is_idempotent(tmp_path: Path) -> None:
    seed_dir = tmp_path / "seed"
    data_dir = tmp_path / "data"

    # Create seed files using the helper
    seeder = SeedCreator(seed_dir)
    seeder.create_account("acct1", "Account One")
    seeder.create_global_preset("rock", "Rock")

    backend = LocalBackend(base_path=str(data_dir))
    ds = DataStore(backend=backend, seed_path=str(seed_dir))
    ds.seed()

    # Assert data was loaded by querying the datastore
    seeded_acct = ds.accounts.get("acct1")
    assert seeded_acct is not None
    assert seeded_acct.name == "Account One"
    assert ds.global_presets.get("rock") is not None

    # Mutate the account to ensure seed does not overwrite existing data
    modified_acct = Account(id="acct1", name="Modified")
    ds.accounts.save(modified_acct)
    ds.seed()  # Second run should NOT overwrite existing files

    # Verify the modification was not overwritten
    final_acct = ds.accounts.get("acct1")
    assert final_acct is not None
    assert final_acct.name == "Modified"
