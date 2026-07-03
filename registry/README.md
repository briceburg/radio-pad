# radio-pad registry

registry.radiopad.dev - uniting players, remote-controls, and switchboards

System architecture and the player-access/auth diagrams live in the [root README](../README.md#architecture).

## Usage

```bash
# run every time you want to start the registry
bin/registry
```

see the swagger API docs by visiting: http://localhost:8000/

## Domain model

A `RadioDial` is a curated, shareable collection of Stations identified by call sign. Stations belong to accounts;
RadioDials contain ordered, account-qualified Station keys such as `community/WWOZ`, so a stream URL can be updated
once without rewriting every RadioDial that uses it.

The API uses three model shapes only when they represent different data:

- `*Spec`: writable JSON without path-derived identity
- unsuffixed models: complete returned resources
- `*Summary`: reduced list/discovery projections

Player configuration stores a qualified `radio_dial` identity such as `community/briceburg`, not a registry URL.
`discoverable` tells clients whether to surface a RadioDial during discovery; it is not access control.

Registry resources are account-scoped:

- `/accounts/{account_id}/stations/{call_sign}`
- `/accounts/{account_id}/radio-dials/{radio_dial_id}`
- `/accounts/{account_id}/players/{player_id}`

### Dependency workflow

Project-wide toolchain and update policy lives in the [root README](../README.md#toolchain-and-dependency-policy). For registry changes, edit runtime and development dependencies in `pyproject.toml`, regenerate only `uv.lock` with `uv lock`, and keep Docker or CI pins unchanged unless the registry runtime or `uv` version is intentionally changing.

### Environment Variables

name | description | default
--- | --- | ---
REGISTRY_BACKEND | datastore backend, either `s3`, `local`, or `git` | `local`
REGISTRY_BACKEND_PATH | datastore location. required when backend is `local`; for `git`, this is the local checkout path. | `tmp/data`
REGISTRY_BACKEND_PREFIX | prefix to apply to objects/files. For `git`, the default is empty so data can live at repo root. | `registry-v1` for `local`/`s3`, empty for `git`
REGISTRY_BACKEND_S3_BUCKET | name of S3 bucket. required when backend is `s3` | `None`
REGISTRY_BACKEND_GIT_REMOTE_URL | git remote URL used to bootstrap a clone when `REGISTRY_BACKEND_PATH` does not already exist. Set to empty to disable remote operations for an existing checkout. | `git@github.com:briceburg/radio-pad-registry-data.git`
REGISTRY_BACKEND_GIT_BRANCH | branch used for fetch/push operations. | `main`
REGISTRY_BACKEND_GIT_FETCH_TTL_SECONDS | read-side fetch freshness window; writes always refresh first. | `30`
REGISTRY_BACKEND_GIT_AUTHOR_NAME | commit author name for registry-managed writes. | `briceburg`
REGISTRY_BACKEND_GIT_AUTHOR_EMAIL | commit author email for registry-managed writes. Use a GitHub-linked address (for example a GitHub noreply email) if you want GitHub to attribute commits to your account. | `briceburg@users.noreply.github.com`
REGISTRY_BACKEND_GIT_SSH_KEY_PATH | optional SSH private key path used to configure `GIT_SSH_COMMAND` for deploy-key authentication. | `None`
REGISTRY_AUTH_OIDC_CLIENT_IDS | comma-separated allowed OIDC client ids for write and player-control auth. | `None`
REGISTRY_AUTH_OIDC_ISSUER | OIDC issuer used to verify bearer tokens for writes and player control. | `None`
REGISTRY_AUTH_OIDC_BASE_URI | optional OIDC discovery base URI for `fastapi-oidc`; defaults to `REGISTRY_AUTH_OIDC_ISSUER`. | same as issuer
REGISTRY_AUTH_OIDC_SIGNATURE_CACHE_TTL | JWKS/discovery cache TTL in seconds for bearer token verification. | `3600`
REGISTRY_AUTHZ_PATH | local private authz data path for account-owner rules. This can share a Fly volume with the public datastore as long as it uses a separate directory. | `tmp/authz`
REGISTRY_AUTHZ_PREFIX | prefix to apply to local private authz files. | `registry-authz-v1`
REGISTRY_PROFILES | Comma separated list of application roles to enable. Options are `api` and `switchboard`. | `api,switchboard`
REGISTRY_API_PREFIX | API routing prefix. | `/api`
REGISTRY_SWITCHBOARD_PREFIX | WebSocket routing prefix. | `/switchboard`
REGISTRY_URL | Base URL of the registry API, including the API prefix (used by switchboard for remote auth in split mode). | `http://localhost:8000/api`
REGISTRY_CORS_ORIGINS | Comma-separated list of allowed CORS origins. | `capacitor://localhost,http://localhost:5173,http://localhost:5174,http://localhost,https://localhost`
REGISTRY_SEED_DATA_PATH | root location of checked-in seed documents. Store seeds load from `store/` and authz seeds load from `auth/` beneath this root. | `seed-data`
REGISTRY_BIND_HOST | host to bind to | `localhost`
REGISTRY_BIND_PORT | port to bind to | `8000`
REGISTRY_LOG_LEVEL | uvicorn log level, e.g. `debug`, `error` | `info`

> relative paths are relative to the project root.

### Backend selection

The registry supports pluggable storage backends.

- Default: file store on local disk.
- Optional: S3-backed store using boto3.
- Optional: Git-backed store using the system Git executable.

Select the backend via the `REGISTRY_BACKEND` environment variable.

#### S3 Backend

If using the S3 backend, it is assumed your environment provides the authentication necessary for _reading_ and _writing_ to the `REGISTRY_BACKEND_S3_BUCKET` bucket -- e.g. the environment provides an appropriate AWS_ACCESS_KEY, [IAM Roles Anywhere](https://docs.aws.amazon.com/rolesanywhere/latest/userguide/introduction.html), or ec2/ecs-task metadata identity to the AWS SDK with these _minimal_ permissions:


```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:DeleteObject",
                "s3:GetObject",
                "s3:HeadObject",
                "s3:ListBucket",
                "s3:PutObject",
            ],
            "Resource": [
                "arn:aws:s3:::your-bucket-name",
                "arn:aws:s3:::your-bucket-name/*"
            ]
        }
    ]
}
```

#### Git Backend

The Git backend stores registry data in a normal git checkout and keeps the same logical path layout:

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

#### Switchboard (WebSockets)

When the `switchboard` profile is enabled in `REGISTRY_PROFILES`, the registry mounts a WebSocket router that facilitates event-driven communication between the [radio-pad player](../player/) and connected [remote controls](../remote-control/).

Pub-sub between connected clients uses an in-memory broadcast module (`src/switchboard/broadcast.py`). Because state is held in-memory, horizontal scaling of the switchboard requires ensuring that all clients connecting to the same player land on the same server instance.

There are two primary ways to scale the switchboard:
1. **Path-based sticky sessions**: A front-end load balancer routes all traffic for a specific `/{account_id}/{player_id}` path to the same backend process.
2. **Switchboard Sharding**: The registry API issues opaque `switchboard_url` properties in its player configurations. This allows the backend to distribute different players to distinct switchboard domains or clusters based on capacity (e.g., `wss://sb-east-1.radiopad.dev/switchboard/...`), rather than relying on a single monolithic endpoint.

The switchboard partitions connections by request path and expects clients to connect to that opaque URL, which takes the form:

`wss://<switchboard_domain>/switchboard/<account_id>/<player_id>`

Example: `wss://registry.radiopad.dev/switchboard/briceburg/living-room`

Controllers must send `{"event":"authenticate","data":{"token":...}}` as their first message. The token is null when
auth is disabled. The switchboard validates access and replies with `authenticated` before subscribing the controller,
replaying state, or accepting commands. It closes rejected and expired sessions with WebSocket policy code `1008`.
Bearer tokens are never placed in switchboard URLs.

The switchboard accepts state events from players and command events from controllers. State events such as `player_presence`, `radio_dial_url`, `playback_state`, and scoped non-OK `player_status` values are retained so newly connected controllers receive the current player state. Player-owned `playback_state` contains confirmed `call_sign`, in-flight `requested_call_sign`, and terminal `failed_call_sign` values; each may be null. A new request or stop clears the prior failure. The latest valid request wins, and duplicate requests do not restart playback. Commands such as `playback_start`, `playback_stop`, `volume_up`, and `volume_down` are transient and are never retained.

### Authentication and account-owner seeding

Resource reads remain public. Writes and player control become protected when both
`REGISTRY_AUTH_OIDC_CLIENT_IDS` and `REGISTRY_AUTH_OIDC_ISSUER` are configured. Clients discover this mode through
`GET /api/auth/status`; split switchboards validate a controller through
`GET /api/auth/players/{account_id}/{player_id}/control`. Both auth responses use `Cache-Control: no-store`.

The registry verifies OIDC bearer tokens against an allowed client-id list and then applies account-owner ACL checks from a separate private local authz store.

For Google OIDC, use one issuer and list the web, Android, and iOS client ids used by `remote-control`:

```sh
REGISTRY_AUTH_OIDC_ISSUER=https://accounts.google.com
REGISTRY_AUTH_OIDC_CLIENT_IDS=web-client-id.apps.googleusercontent.com,android-client-id.apps.googleusercontent.com,ios-client-id.apps.googleusercontent.com
```

Match this with the Google client setup documented in `radio-pad/remote-control/README.md`.

The checked-in seed documents live under a dedicated `seed-data/` root:

- `seed-data/store/...` for public datastore seed content
- `seed-data/auth/...` for private authz seed content

The initial authz documents follow the same seed-file pattern as the public datastore, but live under `seed-data/auth/accounts/<account>.json`.

These files are intended to stay human-friendly and easy to review. The checked-in defaults make
`briceburg@gmail.com` an owner of both the `briceburg` and `community` accounts. An account can have
multiple owners by listing multiple verified emails or OIDC subjects in its document.
Provision that account-owner document before the account's first authenticated write.

If you later want less public identity exposure, you can replace email entries with OIDC `subject` entries after first login.

For the broader system view, including the switchboard/player control boundary, see the diagrams in the [root README](../README.md#architecture).

In production, the private authz store should use a separate local path such as `REGISTRY_AUTHZ_PATH=/data/authz`, even if the public datastore also uses local storage on the same Fly volume.

## Testing

For compose-based development with all services, see the [root README](../README.md#development).

Run the default test suite and static checks with:

```sh
bin/ci
```

To run only pytest:

```sh
uv run pytest
```

This runs the regular unit, API, datastore, and functional tests. Performance tests are excluded by default.

To run the functional tests directly:

```sh
uv run pytest tests/functional -m 'not performance'
```

### Performance Tests

The suite includes performance tests that are disabled by default. To run them, use the `performance` marker:

```sh
uv run pytest tests/functional/test_performance.py -m performance
```

To view the output from performance tests, set the log level:

```sh
uv run pytest tests/functional/test_performance.py -m performance --log-cli-level=INFO
```
