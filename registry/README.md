# radio-pad-registry

registry.radiopad.dev - uniting players, remote-controls, and switchboards

## Usage

```bash
# run these once
python -m venv venv
. venv/bin/activate
pip3 install -r requirements.txt

# run everytime you want to start the registry
bin/registry
```

see the swagger API docs by visiting: http://localhost:8000/

### Python version notes

- The repository targets Python `3.13` language semantics in tooling and type checking.
- The locked runtime dependencies in `requirements.txt` support installing and running the service on Python `3.14` as well.

### Dependency workflow

- `requirements-latest.txt` is the editable runtime dependency source.
- `requirements.txt` is the frozen runtime lockfile used by Docker and CI.
- `requirements-dev.txt` contains development-only tools used for `bin/ci` and `pytest`.

### Environment Variables

name | description | default
--- | --- | ---
REGISTRY_BACKEND | datastore backend, either `s3`, `local`, or `git` | `local`
REGISTRY_BACKEND_PATH | datastore location. required when backend is `local`. | `tmp/data`
REGISTRY_BACKEND_PREFIX | prefix to apply to objects/files. For `git`, the default is empty so data can live at repo root. | `registry-v1` for `local`/`s3`, empty for `git`
REGISTRY_BACKEND_S3_BUCKET | name of S3 bucket. required when backend is `s3` | `None`
REGISTRY_BACKEND_GIT_REPO_PATH | local git checkout path. used for an existing clone or as the clone target when the backend bootstraps the repo. | `/tmp/radio-pad-registry-data`
REGISTRY_BACKEND_GIT_REMOTE_URL | git remote URL used to bootstrap a clone when `REGISTRY_BACKEND_GIT_REPO_PATH` does not already exist. | `git@github.com:briceburg/radio-pad-registry-data.git`
REGISTRY_BACKEND_GIT_BRANCH | branch used for fetch/push operations. | `main`
REGISTRY_BACKEND_GIT_FETCH_TTL_SECONDS | read-side fetch freshness window; writes always refresh first. | `30`
REGISTRY_BACKEND_GIT_AUTHOR_NAME | commit author name for registry-managed writes. | `briceburg`
REGISTRY_BACKEND_GIT_AUTHOR_EMAIL | commit author email for registry-managed writes. | `briceburg@users.noreply.github.com`
REGISTRY_BACKEND_GIT_SSH_KEY_PATH | optional SSH private key path for deploy-key authentication. | `None`
REGISTRY_BACKEND_GIT_SSH_PRIVATE_KEY | optional SSH private key contents for container deployments. When set, the entrypoint writes it to a private key file and exports `REGISTRY_BACKEND_GIT_SSH_KEY_PATH` automatically. | `None`
REGISTRY_BIND_HOST | host to bind to | `localhost`
REGISTRY_BIND_PORT | port to bind to | `8000`
REGISTRY_LOG_LEVEL | uvicorn log level, e.g. `debug`, `error` | `info`
REGISTRY_SEED_PATH | location of data to seed the datastore with. | `data`

> relative paths are relative to the project root.

### Backend selection

The registry supports pluggable storage backends.

- Default: file store on local disk.
- Optional: S3-backed store using boto3.
- Optional: Git-backed store using `dulwich`.

Select the backend via the `REGISTRY_BACKEND` environment variable.

#### S3 Backend

If using the S3 backend, it is assumed your environment provides the authentication necessary for _reading_ and _writing_ to the `REGISTRY_BACKEND_S3_BUCKET` bucket -- e.g. the evironment provides an appropriate AWS_ACCESS_KEY, [IAM Roles Anywhere](https://docs.aws.amazon.com/rolesanywhere/latest/userguide/introduction.html), or ec2/ecs-task metadata identity to the AWS SDK with these _minimal_ permissions:


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
- `accounts/<account>/presets/<preset>.json`
- `presets/<preset>.json`

For the dedicated data repository, the recommended layout is to keep those directories at the repository root and leave `REGISTRY_BACKEND_PREFIX` unset.

The default bootstrap remote is `git@github.com:briceburg/radio-pad-registry-data.git`, the default local checkout path is `/tmp/radio-pad-registry-data`, and the default commit identity is the GitHub noreply identity for `briceburg`. Those defaults can be overridden with the `REGISTRY_BACKEND_GIT_*` environment variables.

The intended authentication model is a write-enabled GitHub deploy key over SSH. In container deployments, the simplest pattern is to inject the private key contents as `REGISTRY_BACKEND_GIT_SSH_PRIVATE_KEY` and let the entrypoint materialize it into a private key file automatically.

#### Fly.io deployment

The checked-in `fly.toml` is now configured for the Git backend:

- `REGISTRY_BACKEND=git`
- `REGISTRY_BACKEND_GIT_REPO_PATH=/tmp/radio-pad-registry-data`
- `REGISTRY_BACKEND_GIT_REMOTE_URL=git@github.com:briceburg/radio-pad-registry-data.git`
- `REGISTRY_BACKEND_GIT_AUTHOR_NAME=briceburg`
- `REGISTRY_BACKEND_GIT_AUTHOR_EMAIL=briceburg@users.noreply.github.com`
- `UVICORN_WORKERS=1`

`UVICORN_WORKERS=1` is intentional for now because the Git backend currently only coordinates writes with a process-local lock. This is a temporary safety setting, and we should revisit it after adding a cross-process lock or another coordination mechanism that makes multi-worker Git writes safe.

A setting of `1` does **not** mean the service can only handle one request at a time. A single uvicorn worker still runs an async event loop and can serve multiple requests concurrently, especially for normal I/O-bound API traffic.

In this container setup, if `UVICORN_WORKERS` is left unset, `bin/docker/entrypoint.sh` defaults it to the detected CPU count. That is often a reasonable target for backends that are safe to run across multiple worker processes. For the current Git backend, though, `1` is the safest setting until the locking story is improved.

The local checkout is stored under `/tmp`, so no Fly volume is required for the current setup. If startup latency or clone churn becomes worth optimizing later, switching that checkout to a Fly volume-backed path would still be a reasonable follow-up.

Recommended deploy procedure:

1. Create a dedicated deploy key for the app:

```sh
ssh-keygen -t ed25519 -f ~/.ssh/radio-pad-registry-data-fly -C "radio-pad-registry fly deploy"
```

2. Add the public key to `briceburg/radio-pad-registry-data` as a GitHub deploy key with write access.

3. Upload the private key to Fly as a secret:

```sh
fly secrets set REGISTRY_BACKEND_GIT_SSH_PRIVATE_KEY="$(cat ~/.ssh/radio-pad-registry-data-fly)"
```

4. Deploy the application:

```sh
fly deploy
```

5. Verify the release:

```sh
fly status
curl -i https://radio-pad-registry.fly.dev/healthz
```

At container startup, `bin/docker/entrypoint.sh` writes `REGISTRY_BACKEND_GIT_SSH_PRIVATE_KEY` to a private key file, exports `REGISTRY_BACKEND_GIT_SSH_KEY_PATH`, and populates `known_hosts` for `github.com`. No extra SSH setup is required inside the image beyond supplying the Fly secret.

## Testing

To run the tests, first install the development dependencies:

```sh
pip install -r requirements-dev.txt
```

If you update runtime dependencies, edit `requirements-latest.txt` first and then re-freeze `requirements.txt`.

Then, run the default test suite using pytest:

```sh
pytest
```

### Performance Tests

The suite includes performance tests that are disabled by default. To run them, use the `performance` marker:

```sh
pytest -m performance
```

To view the output from performance tests, set the log level:

```sh
pytest -m performance --log-cli-level=INFO
```
