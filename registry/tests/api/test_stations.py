from models import StationSpec
from tests.api.client.stations import StationApi


def test_station_create_normalizes_call_sign(station_api: StationApi) -> None:
    station = station_api.put(
        "testuser1",
        "wxna",
        StationSpec.model_validate({"stream_url": "https://wxna.example/stream"}),
    )

    assert station == {
        "key": "testuser1/WXNA",
        "call_sign": "WXNA",
        "stream_url": "https://wxna.example/stream",
    }
    assert station_api.get("testuser1", "WXNA") == station


def test_station_list_is_ordered_and_paginated(station_api: StationApi) -> None:
    station_api.put(
        "testuser1",
        "ZTEST",
        StationSpec.model_validate({"stream_url": "https://z.example/stream"}),
    )
    station_api.put(
        "testuser1",
        "ATEST",
        StationSpec.model_validate({"stream_url": "https://a.example/stream"}),
    )

    data = station_api.list("testuser1")

    assert [station["call_sign"] for station in data["items"]] == ["ATEST", "ZTEST"]


def test_distinct_call_signs_may_share_stream_url(station_api: StationApi) -> None:
    spec = StationSpec.model_validate({"stream_url": "https://simulcast.example/stream"})

    station_api.put("testuser1", "KAAA", spec)
    station_api.put("testuser1", "KBBB", spec)

    assert station_api.get("testuser1", "KAAA")["stream_url"] == station_api.get("testuser1", "KBBB")["stream_url"]
