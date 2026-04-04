"""Remote control integration tests."""

import re

# Vite dev server blocks non-localhost Host headers; override for compose network.
HEADERS = {"Host": "localhost"}


def test_serves_html(http, remote_control_url):
    resp = http.get(remote_control_url, headers=HEADERS)
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


def test_browser_bundle_uses_same_origin_service_urls(http, remote_control_url):
    resp = http.get(f"{remote_control_url}/js/services/preferences.js", headers=HEADERS)
    assert resp.status_code == 200
    assert "registry:1980" not in resp.text
    assert '"/api/"' in resp.text

    resp = http.get(f"{remote_control_url}/js/services/radio-control.js", headers=HEADERS)
    assert resp.status_code == 200
    assert "switchboard:1980" not in resp.text
    assert re.search(r'VITE_SWITCHBOARD_URL.*"/switchboard"', resp.text)


def test_registry_api_proxy(http, remote_control_url):
    resp = http.get(f"{remote_control_url}/api/accounts/briceburg", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["id"] == "briceburg"
