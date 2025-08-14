from http import HTTPStatus


def test_preset_rejects_duplicate_station_names(client):
    payload = {
        "name": "Dup Names",
        "stations": [
            {"name": "Same", "url": "https://a.example/stream"},
            {"name": "same", "url": "https://b.example/stream"},
        ],
    }
    resp = client.put("/v1/presets/dup-names", json=payload)
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    body = resp.json()
    assert any("Duplicate station name" in (err.get("msg") or str(err)) for err in body.get("detail", []))


def test_preset_rejects_duplicate_station_urls(client):
    payload = {
        "name": "Dup URLs",
        "stations": [
            {"name": "A", "url": "https://same.example/stream"},
            {"name": "B", "url": "https://same.example/stream"},
        ],
    }
    resp = client.put("/v1/presets/dup-urls", json=payload)
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    body = resp.json()
    assert any("Duplicate station URL" in (err.get("msg") or str(err)) for err in body.get("detail", []))
