import pytest

from auth.oidc import OIDCConfig


def test_oidc_config_from_env_returns_none_when_oidc_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REGISTRY_AUTH_OIDC_CLIENT_ID", raising=False)
    monkeypatch.delenv("REGISTRY_AUTH_OIDC_ISSUER", raising=False)

    assert OIDCConfig.from_env() is None


@pytest.mark.parametrize(
    ("client_id", "issuer"),
    [
        ("radio-pad-remote-control", None),
        (None, "https://accounts.google.com"),
    ],
)
def test_oidc_config_from_env_requires_client_id_and_issuer(
    monkeypatch: pytest.MonkeyPatch,
    client_id: str | None,
    issuer: str | None,
) -> None:
    if client_id is None:
        monkeypatch.delenv("REGISTRY_AUTH_OIDC_CLIENT_ID", raising=False)
    else:
        monkeypatch.setenv("REGISTRY_AUTH_OIDC_CLIENT_ID", client_id)

    if issuer is None:
        monkeypatch.delenv("REGISTRY_AUTH_OIDC_ISSUER", raising=False)
    else:
        monkeypatch.setenv("REGISTRY_AUTH_OIDC_ISSUER", issuer)

    with pytest.raises(
        ValueError,
        match="REGISTRY_AUTH_OIDC_CLIENT_ID and REGISTRY_AUTH_OIDC_ISSUER must both be set",
    ):
        OIDCConfig.from_env()


def test_oidc_config_from_env_defaults_optional_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGISTRY_AUTH_OIDC_CLIENT_ID", "radio-pad-remote-control")
    monkeypatch.setenv("REGISTRY_AUTH_OIDC_ISSUER", "https://accounts.google.com")

    config = OIDCConfig.from_env()

    assert config is not None
    assert config.base_authorization_server_uri == "https://accounts.google.com"
    assert config.audience == "radio-pad-remote-control"
    assert config.signature_cache_ttl == 3600


def test_oidc_config_from_env_honors_optional_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGISTRY_AUTH_OIDC_CLIENT_ID", "radio-pad-remote-control")
    monkeypatch.setenv("REGISTRY_AUTH_OIDC_ISSUER", "https://accounts.google.com")
    monkeypatch.setenv("REGISTRY_AUTH_OIDC_BASE_URI", "https://accounts.google.com")
    monkeypatch.setenv("REGISTRY_AUTH_OIDC_AUDIENCE", "registry-writes")
    monkeypatch.setenv("REGISTRY_AUTH_OIDC_SIGNATURE_CACHE_TTL", "120")

    config = OIDCConfig.from_env()

    assert config is not None
    assert config.base_authorization_server_uri == "https://accounts.google.com"
    assert config.audience == "registry-writes"
    assert config.signature_cache_ttl == 120
