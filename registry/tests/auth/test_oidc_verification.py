import json
import time
from collections import Counter
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Barrier, Thread
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from auth.oidc import OIDCConfig, RegistryIDToken
from auth.sessions import AccessTokens

_DISCOVERY = "/.well-known/openid-configuration"
_JWKS = "/jwks.json"


@pytest.fixture(scope="module")
def signing_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@dataclass
class Provider:
    url: str
    key: rsa.RSAPrivateKey
    responses: dict[str, tuple[int, object]] = field(default_factory=dict)
    requests: Counter[str] = field(default_factory=Counter)

    def token(self, *, kid: object = "current", **claims: object) -> str:
        now = int(time.time())
        payload = {"iss": self.url, "sub": "user", "aud": "web", "iat": now, "exp": now + 300, **claims}
        return jwt.encode(payload, self.key, algorithm="RS256", headers={"kid": kid})

    def jwks(self, *, kid: str = "current", use: str = "sig") -> dict[str, object]:
        key = jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key(), as_dict=True)
        return {"keys": [{**key, "kid": kid, "use": use, "alg": "RS256"}]}

    def authenticate(self, ttl: int = 3600) -> Callable[[str], RegistryIDToken]:
        return OIDCConfig(("web", "native"), self.url, self.url, ttl).build_auth_dependency()


@pytest.fixture
def provider(signing_key: rsa.RSAPrivateKey) -> Iterator[Provider]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            state.requests[self.path] += 1
            status, payload = state.responses.get(self.path, (404, {}))
            self.send_response(status)
            if status == 302:
                self.send_header("Location", state.url + "/redirected")
            self.end_headers()
            self.wfile.write(payload if isinstance(payload, bytes) else json.dumps(payload).encode())

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    state = Provider(f"http://127.0.0.1:{server.server_port}", signing_key)
    state.responses = {
        _DISCOVERY: (
            200,
            {
                "issuer": state.url,
                "jwks_uri": state.url + _JWKS,
                "id_token_signing_alg_values_supported": ["RS256"],
            },
        ),
        _JWKS: (200, state.jwks()),
    }
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield state
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_lazy_discovery_and_concurrent_audiences_share_keys(provider: Provider) -> None:
    authenticate = provider.authenticate()
    assert not provider.requests
    tokens = [provider.token(aud=aud) for aud in ("web", "native", ["other", "native"])]
    barrier = Barrier(12)

    def verify(index: int) -> RegistryIDToken:
        barrier.wait(timeout=5)
        return authenticate(tokens[index % len(tokens)])

    with ThreadPoolExecutor(max_workers=12) as executor:
        assert all(token.sub == "user" for token in executor.map(verify, range(12)))
    assert provider.requests == {_DISCOVERY: 1, _JWKS: 1}
    original_authentication = int(time.time()) - 120
    token = authenticate(
        provider.token(auth_time=original_authentication, email="user@example.com", email_verified=True)
    )
    assert AccessTokens.identity_from_oidc(token).authenticated_at == original_authentication
    assert AccessTokens.identity_from_oidc(token).verified_email == "user@example.com"


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "https://wrong.example"},
        {"aud": "other"},
        {"exp": 0},
        {"exp": int(time.time())},
        {"iat": int(time.time()) + 600},
        {"nbf": int(time.time()) + 600},
        {"sub": None},
        {"exp": None},
        {"iat": None},
    ],
)
def test_invalid_claims_are_unauthorized(provider: Provider, claims: dict[str, object]) -> None:
    with pytest.raises(HTTPException) as raised:
        provider.authenticate()(provider.token(**claims))
    assert raised.value.status_code == 401
    assert raised.value.detail == "Invalid OIDC ID token"


@pytest.mark.parametrize("missing", ["iss", "sub", "aud", "exp", "iat"])
def test_missing_required_claim_is_unauthorized(provider: Provider, missing: str) -> None:
    now = int(time.time())
    payload = {"iss": provider.url, "sub": "user", "aud": "web", "exp": now + 300, "iat": now}
    del payload[missing]
    raw = jwt.encode(payload, provider.key, algorithm="RS256", headers={"kid": "current"})
    with pytest.raises(HTTPException) as raised:
        provider.authenticate()(raw)
    assert raised.value.status_code == 401


def test_wrong_signature_and_unknown_key_are_unauthorized(provider: Provider) -> None:
    authenticate = provider.authenticate()
    other = Provider(provider.url, rsa.generate_private_key(public_exponent=65537, key_size=2048))
    for raw in (other.token(), provider.token(kid="unknown"), provider.token(kid=""), "malformed"):
        with pytest.raises(HTTPException) as raised:
            authenticate(raw)
        assert raised.value.status_code == 401
    # Unknown keys cannot force repeated requests during PyJWT's default cooldown.
    assert provider.requests == {_DISCOVERY: 1, _JWKS: 1}


def test_symmetric_and_unsigned_tokens_are_rejected_before_discovery(provider: Provider) -> None:
    for algorithm, key in (("HS256", "a" * 32), ("none", "")):
        raw = jwt.encode({"sub": "user"}, key, algorithm=algorithm, headers={"kid": "current"})
        with pytest.raises(HTTPException) as raised:
            provider.authenticate()(raw)
        assert raised.value.status_code == 401
    assert not provider.requests


@pytest.mark.parametrize(
    ("path", "status", "payload"),
    [
        (_DISCOVERY, 503, {}),
        (_DISCOVERY, 302, {}),
        (_DISCOVERY, 200, []),
        (_DISCOVERY, 200, b"{"),
        (_DISCOVERY, 200, {"issuer": "wrong"}),
        (_JWKS, 503, {}),
        (_JWKS, 302, {}),
        (_JWKS, 200, []),
        (_JWKS, 200, b"{"),
        (_JWKS, 200, {"keys": []}),
        (_JWKS, 200, {"keys": [{"kty": "RSA", "kid": "current", "n": None, "e": "AQAB"}]}),
    ],
)
def test_provider_failures_are_generic_internal_errors(
    provider: Provider, path: str, status: int, payload: object, caplog: pytest.LogCaptureFixture
) -> None:
    provider.responses[path] = (status, payload)
    raw = provider.token(sub="never-log-this-identity")
    with pytest.raises(HTTPException) as raised:
        provider.authenticate()(raw)
    assert raised.value.status_code == 500
    assert raised.value.detail == "OIDC provider unavailable"
    assert "/redirected" not in provider.requests
    assert raw not in caplog.text
    assert "never-log-this-identity" not in caplog.text


def test_encryption_keys_are_provider_failure(provider: Provider) -> None:
    provider.responses[_JWKS] = (200, provider.jwks(use="enc"))
    with pytest.raises(HTTPException) as raised:
        provider.authenticate()(provider.token())
    assert raised.value.status_code == 500


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("issuer", "https://wrong.example"),
        ("jwks_uri", "file:///tmp/keys.json"),
        ("id_token_signing_alg_values_supported", ["HS256"]),
    ],
)
def test_discovery_must_match_trusted_configuration(provider: Provider, field: str, value: object) -> None:
    metadata = provider.responses[_DISCOVERY][1]
    assert isinstance(metadata, dict)
    provider.responses[_DISCOVERY] = (200, {**metadata, field: value})
    with pytest.raises(HTTPException) as raised:
        provider.authenticate()(provider.token())
    assert raised.value.status_code == 500
    assert provider.requests == {_DISCOVERY: 1}


def test_rotation_cooldown_and_failed_refresh_preserve_valid_keys(
    provider: Provider, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = [time.monotonic()]
    monkeypatch.setattr("jwt.jwks_client.time", SimpleNamespace(monotonic=lambda: clock[0]))
    authenticate = provider.authenticate()
    current = provider.token()
    authenticate(current)
    provider.responses[_JWKS] = (503, {})
    clock[0] += 31
    with pytest.raises(HTTPException) as raised:
        authenticate(provider.token(kid="next"))
    assert raised.value.status_code == 500
    assert authenticate(current).sub == "user"
    assert provider.requests[_JWKS] == 2
    provider.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    provider.responses[_JWKS] = (200, provider.jwks(kid="next"))
    assert authenticate(provider.token(kid="next")).sub == "user"
    assert provider.requests[_JWKS] == 3
    with pytest.raises(HTTPException) as raised:
        authenticate(current)
    assert raised.value.status_code == 401
    assert provider.requests[_JWKS] == 3


def test_zero_ttl_fetches_each_time(provider: Provider) -> None:
    authenticate = provider.authenticate(ttl=0)
    for _ in range(2):
        authenticate(provider.token())
    assert provider.requests == {_DISCOVERY: 2, _JWKS: 2}


def test_expired_discovery_and_keys_are_refetched(provider: Provider) -> None:
    authenticate = provider.authenticate(ttl=1)
    authenticate(provider.token())
    time.sleep(1.05)
    provider.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    provider.responses[_JWKS] = (200, provider.jwks())
    authenticate(provider.token())
    assert provider.requests == {_DISCOVERY: 2, _JWKS: 2}
