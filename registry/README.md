# RadioPad registry

The API and WebSocket switchboard that connect RadioPad players and remote controls.

System architecture and the player-access/auth diagrams live in the [root README](../README.md#architecture).

## Usage

```sh
bin/registry
```

Open <http://localhost:8000/> for the Swagger API documentation.

## Domain model

A `RadioDial` is a curated, shareable collection of Stations identified by call sign. Stations belong to accounts; RadioDials contain ordered, account-qualified Station keys such as `community/WWOZ`, so a stream URL can be updated once without rewriting every RadioDial that uses it.

The API uses three model shapes only when they represent different data:

- `*Spec`: writable JSON without path-derived identity
- unsuffixed models: complete returned resources
- `*Summary`: reduced list/discovery projections

Player configuration stores a qualified `radio_dial` identity such as `community/briceburg`, not a registry URL. `discoverable` tells clients whether to surface a RadioDial during discovery; it is not access control.

Registry resources are account-scoped:

- `/accounts/{account_id}/stations/{call_sign}`
- `/accounts/{account_id}/radio-dials/{radio_dial_id}`
- `/accounts/{account_id}/players/{player_id}`

## Configuration

### Environment variables

| Name | Description | Default |
| --- | --- | --- |
| `REGISTRY_API_PREFIX` | API routing prefix. | `/api` |
| `REGISTRY_AUTHZ_BACKEND` | Authz backend: `local`, `s3`, or `git`. | data backend |
| `REGISTRY_AUTHZ_BACKEND_GIT_REMOTE_URL` | Authz Git remote. | data remote when both use Git; otherwise unset |
| `REGISTRY_AUTHZ_BACKEND_GIT_SSH_KEY_PATH` | Authz Git SSH key. | data key when both use Git; otherwise unset |
| `REGISTRY_AUTHZ_BACKEND_PATH` | Authz local root or Git checkout. | data path when backends match; otherwise `tmp/authz` |
| `REGISTRY_AUTHZ_BACKEND_S3_BUCKET` | Authz S3 bucket. | data bucket when both use S3; otherwise unset |
| `REGISTRY_AUTH_OIDC_BASE_URI` | OIDC discovery base URI. | issuer |
| `REGISTRY_AUTH_OIDC_CLIENT_IDS` | Allowed OIDC client IDs for writes and player control. | unset |
| `REGISTRY_AUTH_OIDC_ISSUER` | OIDC bearer-token issuer. | unset |
| `REGISTRY_AUTH_OIDC_SIGNATURE_CACHE_TTL` | OIDC discovery and key cache lifetime in seconds. | `3600` |
| `REGISTRY_BIND_HOST` | Server bind host. | `localhost` |
| `REGISTRY_BIND_PORT` | Server bind port. | `8000` |
| `REGISTRY_CORS_ORIGINS` | Comma-separated allowed CORS origins. | `capacitor://localhost,http://localhost:5173,http://localhost:5174,http://localhost,https://localhost` |
| `REGISTRY_DATA_BACKEND` | Registry data backend: `local`, `s3`, or `git`. | `local` |
| `REGISTRY_DATA_BACKEND_GIT_REMOTE_URL` | Data Git remote; set empty for an offline checkout. | `git@github.com:briceburg/radio-pad-registry-data.git` |
| `REGISTRY_DATA_BACKEND_GIT_SSH_KEY_PATH` | Data Git SSH key. | unset |
| `REGISTRY_DATA_BACKEND_PATH` | Data local root or Git checkout. | `tmp/data` |
| `REGISTRY_DATA_BACKEND_S3_BUCKET` | Data S3 bucket. | unset; required for S3 |
| `REGISTRY_GIT_AUTHOR_EMAIL` | Author email for Git writes. | `briceburg@users.noreply.github.com` |
| `REGISTRY_GIT_AUTHOR_NAME` | Author name for Git writes. | `briceburg` |
| `REGISTRY_GIT_BRANCH` | Branch used by Git backends. | `main` |
| `REGISTRY_GIT_FETCH_TTL_SECONDS` | Read fetch interval in seconds; writes always fetch. | `30` |
| `REGISTRY_LOG_LEVEL` | Uvicorn log level. | `info` |
| `REGISTRY_PROFILES` | Enabled roles: `api`, `switchboard`, or both. | `api,switchboard` |
| `REGISTRY_SEED_DATA_PATH` | Root containing `data/` and `authz/` seeds. | `seed-data` |
| `REGISTRY_SWITCHBOARD_PREFIX` | WebSocket routing prefix. | `/switchboard` |
| `REGISTRY_URL` | Registry API URL used by a split switchboard. | `http://localhost:8000/api` |

Relative paths resolve from the registry project root.

### Data and authz storage

`REGISTRY_DATA_BACKEND` selects where registry data is stored. Authz uses the same backend and location by default; set only the `REGISTRY_AUTHZ_BACKEND*` values that differ. Every backend separates the stores under `data/` and `authz/`. Use separate private authz storage when registry data is public.

#### S3 backend

S3 uses the standard AWS credential chain. The policy below covers data and shared buckets; an authz-only bucket needs only `s3:GetObject` and `s3:PutObject` for `authz/*`.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::your-bucket-name"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:DeleteObject", "s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::your-bucket-name/*"
    }
  ]
}
```

#### Git backend

Git writes the same `data/` and `authz/` layout to a checkout. It defaults to `tmp/data`, the `main` branch, and `git@github.com:briceburg/radio-pad-registry-data.git`. Set the remote to an empty value to use an existing checkout without synchronization.

Remote writes require an SSH deploy key with write access. `REGISTRY_GIT_*` applies to both stores; separate authz Git settings use `REGISTRY_AUTHZ_BACKEND_*`.

##### Fly.io deployment

Generate a keypair, add its public key to GitHub as a write-enabled deploy key, and store its private key in Fly:

```sh
ssh-keygen -t ed25519 -f ~/.ssh/radio-pad-registry-data-fly -C "radio-pad-registry fly deploy"
fly secrets set REGISTRY_DATA_BACKEND_GIT_SSH_PRIVATE_KEY="$(cat ~/.ssh/radio-pad-registry-data-fly)"
fly deploy
curl -i https://radio-pad-registry.fly.dev/healthz
```

Use `REGISTRY_AUTHZ_BACKEND_GIT_SSH_PRIVATE_KEY` for a separate authz Git remote.

## Switchboard

When the `switchboard` profile is enabled in `REGISTRY_PROFILES`, the registry mounts a WebSocket router that facilitates event-driven communication between the [RadioPad player](../player/) and connected [remote controls](../remote-control/).

Pub-sub between connected clients uses an in-memory broadcast module (`src/switchboard/broadcast.py`). Because state is held in-memory, horizontal scaling of the switchboard requires ensuring that all clients connecting to the same player land on the same server instance.

Two deployment strategies preserve that affinity:

1. **Path-based sticky sessions:** A load balancer routes a given `/{account_id}/{player_id}` path to the same process.
2. **Switchboard sharding:** Registry player resources provide opaque `switchboard_url` values, allowing different players to use distinct switchboard domains or clusters.

The switchboard partitions connections by request path and expects clients to connect to that opaque URL, which takes the form:

`wss://<switchboard_domain>/switchboard/<account_id>/<player_id>`

Example: `wss://registry.radiopad.dev/switchboard/briceburg/living-room`

Controllers must send `{"event":"authenticate","data":{"token":...}}` as their first message. The token is null when auth is disabled. The switchboard validates access and replies with `authenticated` before subscribing the controller, replaying state, or accepting commands. It closes rejected and expired sessions with WebSocket policy code `1008`. Bearer tokens are never placed in switchboard URLs.

The switchboard accepts state events from players and command events from controllers. State events such as `player_presence`, `radio_dial_url`, `playback_state`, and scoped non-OK `player_status` values are retained so newly connected controllers receive the current player state. Player-owned `playback_state` contains confirmed `call_sign`, in-flight `requested_call_sign`, and terminal `failed_call_sign` values; each may be null. A new request or stop clears the prior failure. The latest valid request wins, and duplicate requests do not restart playback. Commands such as `playback_start`, `playback_stop`, `volume_up`, and `volume_down` are transient and are never retained.

## Authentication and authz

Registry API reads are currently unauthenticated. Writes and player control become protected when both `REGISTRY_AUTH_OIDC_CLIENT_IDS` and `REGISTRY_AUTH_OIDC_ISSUER` are configured. Clients discover this mode through `GET /api/auth/status`; split switchboards validate a controller through `GET /api/auth/players/{account_id}/{player_id}/control`. Both auth responses use `Cache-Control: no-store`.

The registry verifies OIDC bearer tokens against an allowed client-id list, then checks the private account-owner store. Email ownership requires an explicitly verified OIDC email claim.

For Google sign-in, `REGISTRY_AUTH_OIDC_CLIENT_IDS` must contain the same Web client ID used by the remote-control build; native Android and iOS client IDs are not token audiences. The root [Google sign-in setup](../README.md#google-sign-in) covers local Compose wiring; standalone browser and native setup lives in the [remote-control README](../remote-control/README.md#local-configuration).

Registry and account-owner seeds live under `seed-data/data/` and `seed-data/authz/`. Owner documents live at `authz/accounts/<account>.json` and contain email addresses or issuer-qualified OIDC subjects.

An S3 update applies to the next HTTP check or WebSocket connection without a restart. Existing WebSockets remain authorized until disconnect or token expiry.

## Development

For Compose-based development with all services, see the [root README](../README.md#development).

For registry dependency changes, follow the root [toolchain policy](../README.md#toolchain-and-dependency-policy): edit `pyproject.toml` and regenerate only `uv.lock` with `uv lock`.

### Testing

Run the default test suite and static checks with:

```sh
bin/ci
```

Use `uv run pytest` for tests without static checks. Performance tests are excluded by default; target functional or performance tests with:

```sh
uv run pytest tests/functional -m 'not performance'
uv run pytest tests/functional/test_performance.py -m performance
uv run pytest tests/functional/test_performance.py -m performance --log-cli-level=INFO
```

## License

[GNU Affero General Public License v3.0](./LICENSE)
