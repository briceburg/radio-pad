"""Remote control — web app is serving HTML."""

# Vite dev server blocks non-localhost Host headers; override for compose network.
HEADERS = {"Host": "localhost"}


def test_serves_html(http, remote_control_url):
    resp = http.get(remote_control_url, headers=HEADERS)
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
