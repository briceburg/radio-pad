import json

from datastore import DataStore


def test_datastore_initialization():
    """DataStore initializes component stores."""
    real_store = DataStore()
    assert real_store.accounts is not None
    assert real_store.players is not None
    assert real_store.global_presets is not None
    assert real_store.account_presets is not None


def test_datastore_isolation():
    """Separate DataStore instances have independent backends and roots."""
    store1 = DataStore()
    store2 = DataStore()
    assert store1 is not store2
    assert store1.backend is not store2.backend


def test_seed_no_error(tmp_path):
    """Calling seed on an empty seed path logs error but does not raise."""
    ds = DataStore(data_path=str(tmp_path / "data"), seed_path=str(tmp_path / "missing-seed"))
    ds.seed()  # Should not raise even if seed path missing


def test_seed_copies_json_and_is_idempotent(tmp_path):
    seed_dir = tmp_path / "seed"
    data_dir = tmp_path / "data"
    # create seed files (nested)
    (seed_dir / "accounts").mkdir(parents=True)
    (seed_dir / "presets" / "global").mkdir(parents=True)
    (seed_dir / "accounts" / "acct1.json").write_text(json.dumps({"name": "Account One"}))
    (seed_dir / "presets" / "global" / "rock.json").write_text(json.dumps({"name": "Rock", "stations": []}))

    ds = DataStore(data_path=str(data_dir), seed_path=str(seed_dir))
    ds.seed()

    # assert files copied
    copied_acct = data_dir / "accounts" / "acct1.json"
    copied_preset = data_dir / "presets" / "global" / "rock.json"
    assert copied_acct.is_file()
    assert copied_preset.is_file()

    original_acct_content = copied_acct.read_text()

    # mutate target file to ensure seed does not overwrite existing
    copied_acct.write_text(json.dumps({"name": "Modified"}))
    ds.seed()  # second run should NOT overwrite existing files

    assert copied_acct.read_text() == json.dumps({"name": "Modified"})
    assert copied_preset.read_text() == (seed_dir / "presets" / "global" / "rock.json").read_text()
    # ensure original content different (i.e., file was indeed modified and not re-copied)
    assert original_acct_content != copied_acct.read_text()
