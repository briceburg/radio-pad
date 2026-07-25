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
| `REGISTRY_BACKEND` | Datastore backend: `local`, `s3`, or `git`. | `local` |
| `REGISTRY_BACKEND_PATH` | Local datastore path or Git checkout path. | `tmp/data` |
| `REGISTRY_BACKEND_PREFIX` | Object/file prefix. Git defaults to no prefix so data can live at the checkout root. | `registry-v1` for local/S3; empty for Git |
| `REGISTRY_BACKEND_S3_BUCKET` | S3 bucket name; required for the S3 backend. | unset |
| `REGISTRY_BACKEND_GIT_REMOTE_URL` | Remote used to bootstrap a missing Git checkout; set empty to disable remote operations for an existing checkout. | `git@github.com:briceburg/radio-pad-registry-data.git` |
| `REGISTRY_BACKEND_GIT_BRANCH` | Branch used for fetch and push operations. | `main` |
| `REGISTRY_BACKEND_GIT_FETCH_TTL_SECONDS` | Read-side fetch freshness window; writes always refresh first. | `30` |
| `REGISTRY_BACKEND_GIT_AUTHOR_NAME` | Author name for registry-managed commits. | `briceburg` |
| `REGISTRY_BACKEND_GIT_AUTHOR_EMAIL` | Author email for registry-managed commits; use a GitHub-linked address for attribution. | `briceburg@users.noreply.github.com` |
| `REGISTRY_BACKEND_GIT_SSH_KEY_PATH` | Optional SSH private-key path for deploy-key authentication. | unset |
| `REGISTRY_BACKEND_AUTH` | Private authorization backend: `local`, `s3`, or `git`. | same as `REGISTRY_BACKEND` |
| `REGISTRY_BACKEND_AUTH_PATH` | Private local path or Git checkout when authorization storage is split. | content path for the same backend type; otherwise `tmp/authz` |
| `REGISTRY_BACKEND_AUTH_S3_BUCKET` | Private S3 bucket when authorization does not use the content bucket. | content bucket when both use S3 |
| `REGISTRY_BACKEND_AUTH_GIT_REMOTE_URL` | Private remote for a separate authorization Git repository. | content remote when both use Git |
| `REGISTRY_BACKEND_AUTH_GIT_SSH_KEY_PATH` | Optional private key for a separate authorization Git repository. | content key when both use Git |
| `REGISTRY_AUTH_OIDC_CLIENT_IDS` | Comma-separated OIDC client IDs allowed for writes and player control. | unset |
| `REGISTRY_AUTH_OIDC_ISSUER` | OIDC issuer used to verify bearer tokens. | unset |
| `REGISTRY_AUTH_OIDC_BASE_URI` | Optional OIDC discovery base URI. | same as issuer |
| `REGISTRY_AUTH_OIDC_SIGNATURE_CACHE_TTL` | JWKS/discovery cache lifetime in seconds. | `3600` |
| `REGISTRY_PROFILES` | Enabled roles: `api`, `switchboard`, or both. | `api,switchboard` |
| `REGISTRY_API_PREFIX` | API routing prefix. | `/api` |
| `REGISTRY_SWITCHBOARD_PREFIX` | WebSocket routing prefix. | `/switchboard` |
| `REGISTRY_URL` | Registry API base URL, including the API prefix, used for split-mode switchboard authorization. | `http://localhost:8000/api` |
| `REGISTRY_CORS_ORIGINS` | Comma-separated allowed CORS origins. | `capacitor://localhost,http://localhost:5173,http://localhost:5174,http://localhost,https://localhost` |
| `REGISTRY_SEED_DATA_PATH` | Root containing public `store/` and private `auth/` seed documents. | `seed-data` |
| `REGISTRY_BIND_HOST` | Server bind host. | `localhost` |
| `REGISTRY_BIND_PORT` | Server bind port. | `8000` |
| `REGISTRY_LOG_LEVEL` | Uvicorn log level, such as `debug` or `error`. | `info` |

Relative paths resolve from the registry project root.

### Backend selection

Set `REGISTRY_BACKEND` to `local` for the default filesystem store, `s3` for S3 through boto3, or `git` for a checkout managed through the system Git executable.

#### S3 backend

The S3 backend uses the standard AWS credential chain, including environment credentials, [IAM Roles Anywhere](https://docs.aws.amazon.com/rolesanywhere/latest/userguide/introduction.html), and EC2/ECS task identities. Its identity needs these minimum permissions for `REGISTRY_BACKEND_S3_BUCKET`:

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

The Git backend stores registry data in a normal Git checkout and keeps the same logical path layout:

- `accounts/<account>.json`
- `accounts/<account>/players/<player>.json`
- `accounts/<account>/stations.json`
- `accounts/<account>/radio-dials/<radio-dial>.json`

The recommended layout for a dedicated data repository is to keep those directories at the repository root and leave `REGISTRY_BACKEND_PREFIX` unset.

By default, the Git backend uses `tmp/data` as its checkout path, `git@github.com:briceburg/radio-pad-registry-data.git` as its bootstrap remote, and the GitHub noreply identity for `briceburg` for registry-managed commits.

The intended authentication model is a write-enabled GitHub deploy key over SSH. To run without remote sync, set `REGISTRY_BACKEND_GIT_REMOTE_URL=` and place an existing checkout in `REGISTRY_BACKEND_PATH`.

Git operations run as fixed subprocess argument lists without a shell. The container includes Git and OpenSSH, disables interactive credential prompts, and uses `GIT_SSH_COMMAND` for deploy-key configuration.

##### Fly.io deployment

The checked-in `fly.toml` uses `tmp/data` as the local checkout. The backend also uses a repo-scoped file lock so processes sharing the same checkout serialize Git operations safely.

Deploy by generating an SSH keypair, adding the **public** key to the data repo as a write-enabled GitHub deploy key, storing the **private** key in the Fly secret `REGISTRY_BACKEND_GIT_SSH_PRIVATE_KEY`, and then deploying:

```sh
ssh-keygen -t ed25519 -f ~/.ssh/radio-pad-registry-data-fly -C "radio-pad-registry fly deploy"
# add ~/.ssh/radio-pad-registry-data-fly.pub to GitHub as a deploy key with write access
fly secrets set REGISTRY_BACKEND_GIT_SSH_PRIVATE_KEY="$(cat ~/.ssh/radio-pad-registry-data-fly)"
fly deploy
curl -i https://radio-pad-registry.fly.dev/healthz
```

Use a volume for `REGISTRY_BACKEND_PATH` if startup clone latency becomes a problem.

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

## Authentication and account-owner seeding

Resource reads remain public. Writes and player control become protected when both `REGISTRY_AUTH_OIDC_CLIENT_IDS` and `REGISTRY_AUTH_OIDC_ISSUER` are configured. Clients discover this mode through `GET /api/auth/status`; split switchboards validate a controller through `GET /api/auth/players/{account_id}/{player_id}/control`. Both auth responses use `Cache-Control: no-store`.

The registry verifies OIDC bearer tokens against an allowed client-id list and then applies account-owner ACL checks from a separate private authz store. Account emails authorize only when the OIDC token explicitly reports the email as verified.

For Google sign-in, `REGISTRY_AUTH_OIDC_CLIENT_IDS` must contain the same Web client ID used by the remote-control build; native Android and iOS client IDs are not token audiences. The root [Google sign-in setup](../README.md#google-sign-in) covers local Compose wiring; standalone browser and native setup lives in the [remote-control README](../remote-control/README.md#local-configuration).

The checked-in seed directories live under a dedicated `seed-data/` root:

- `seed-data/store/...` for public datastore seed content
- `seed-data/auth/...` for account-owner authz seeds

Account-owner seeds initialize local authz data. Documents live at `registry-authz-v1/accounts/<account>.json` and can contain verified emails or issuer-qualified OIDC subjects.

Authorization storage is always private and supports local, S3, and Git. By default it shares the content backend under the fixed `registry-authz-v1` prefix. Set `REGISTRY_BACKEND_AUTH` and the needed location override only when the stores are split. Registry content may be public only when authorization uses separate private storage.

Shared Git storage uses the same checkout lock and reconciliation behavior. For a separate private Git repository, set its auth path, remote, and optional deploy key. On Fly, store the key in `REGISTRY_BACKEND_AUTH_GIT_SSH_PRIVATE_KEY`.

Authorization reads are not cached, so a successful S3 update affects the next HTTP authorization check or new WebSocket connection without restarting the registry. An already-authenticated WebSocket remains authorized until it disconnects or its token expires.

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
