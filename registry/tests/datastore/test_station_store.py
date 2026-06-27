from pathlib import Path

import pytest

from datastore.backends import LocalBackend
from datastore.stores import Stations
from models import StationSpec


def _store(tmp_path: Path) -> Stations:
    return Stations(LocalBackend(str(tmp_path)))


def test_station_updates_preserve_the_account_aggregate(tmp_path: Path) -> None:
    stations = _store(tmp_path)
    stations.upsert("account", "WWOZ", StationSpec.model_validate({"stream_url": "https://example.com/wwoz"}))
    stations.upsert("account", "KEXP", StationSpec.model_validate({"stream_url": "https://example.com/kexp"}))

    assert [station.call_sign for station in stations.list("account")] == ["KEXP", "WWOZ"]


def test_station_seed_rejects_call_sign_collisions_after_normalization(tmp_path: Path) -> None:
    stations = _store(tmp_path)

    with pytest.raises(ValueError, match="Duplicate station call sign: WWOZ"):
        stations.seed(
            {
                "WWOZ": {"stream_url": "https://example.com/first"},
                "wwoz": {"stream_url": "https://example.com/second"},
            },
            path_params={"account_id": "account"},
        )


def test_station_seed_preserves_id_as_a_call_sign(tmp_path: Path) -> None:
    stations = _store(tmp_path)
    stations.seed(
        {
            "id": {"stream_url": "https://example.com/id"},
            "account_id": "account",
        },
        path_params={"account_id": "account"},
    )

    station = stations.get("account", "ID")
    assert station is not None
    assert station.call_sign == "ID"
