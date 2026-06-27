from starlette.testclient import TestClient

from models import RadioDialSpec, StationSpec
from tests.api.client.radio_dials import RadioDialApi
from tests.api.client.stations import StationApi


def test_radio_dial_resolves_current_station_definitions(radio_dial_api: RadioDialApi) -> None:
    dial = radio_dial_api.get("community", "briceburg")

    assert dial["key"] == "community/briceburg"
    assert dial["discoverable"] is True
    assert [station["key"] for station in dial["stations"]] == ["community/WWOZ", "community/KEXP"]
    assert dial["stations"][0]["stream_url"] == "https://www.wwoz.org/listen/hi"


def test_radio_dial_can_mix_account_station_libraries(
    station_api: StationApi,
    radio_dial_api: RadioDialApi,
) -> None:
    station_api.put(
        "testuser1",
        "LOFI",
        StationSpec.model_validate({"stream_url": "https://lofi.example/stream"}),
    )
    payload = RadioDialSpec.model_validate(
        {
            "name": "Mixed",
            "stations": ["community/WWOZ", "testuser1/LOFI"],
        }
    )

    dial = radio_dial_api.put("testuser1", "mixed", payload)

    assert [station["key"] for station in dial["stations"]] == ["community/WWOZ", "testuser1/LOFI"]


def test_station_update_is_visible_in_resolved_radio_dial(
    station_api: StationApi,
    radio_dial_api: RadioDialApi,
) -> None:
    station_api.put(
        "community",
        "WWOZ",
        StationSpec.model_validate({"stream_url": "https://new.example/wwoz"}),
    )

    dial = radio_dial_api.get("community", "briceburg")

    assert dial["stations"][0]["stream_url"] == "https://new.example/wwoz"


def test_radio_dial_list_returns_summaries_without_stations(radio_dial_api: RadioDialApi) -> None:
    item = radio_dial_api.list("community")["items"][0]

    assert item["key"] == "community/briceburg"
    assert item["name"] == "Casa Briceburg"
    assert "stations" not in item


def test_radio_dial_put_replaces_optional_metadata(radio_dial_api: RadioDialApi) -> None:
    radio_dial_api.put(
        "testuser1",
        "replace",
        RadioDialSpec(
            name="Original",
            description="Remove me",
            discoverable=True,
            stations=["community/WWOZ"],
        ),
    )

    replaced = radio_dial_api.put(
        "testuser1",
        "replace",
        RadioDialSpec(name="Replaced", stations=["community/KEXP"]),
    )

    assert replaced["discoverable"] is False
    assert "description" not in replaced
    assert [station["call_sign"] for station in replaced["stations"]] == ["KEXP"]
    assert radio_dial_api.get("testuser1", "replace") == replaced


def test_radio_dial_rejects_missing_station(client: TestClient) -> None:
    response = client.put(
        "accounts/testuser1/radio-dials/missing",
        json={"name": "Missing", "stations": ["community/NOPE"]},
    )

    assert response.status_code == 404
    assert response.json()["details"] == {"station_key": "community/NOPE"}


def test_radio_dial_rejects_duplicate_call_signs_across_accounts(client: TestClient) -> None:
    response = client.put(
        "accounts/testuser1/radio-dials/duplicates",
        json={
            "name": "Duplicates",
            "stations": ["community/WWOZ", "testuser1/WWOZ"],
        },
    )

    assert response.status_code == 422
