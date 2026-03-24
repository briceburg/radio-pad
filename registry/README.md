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
REGISTRY_BACKEND_PATH | datastore location. required when backend is `local`; for `git`, this is the local checkout path. | `tmp/data`
REGISTRY_BACKEND_PREFIX | prefix to apply to objects/files. For `git`, the default is empty so data can live at repo root. | `registry-v1` for `local`/`s3`, empty for `git`
REGISTRY_BACKEND_S3_BUCKET | name of S3 bucket. required when backend is `s3` | `None`
REGISTRY_BACKEND_GIT_REMOTE_URL | git remote URL used to bootstrap a clone when `REGISTRY_BACKEND_PATH` does not already exist. Set to empty to disable remote operations for an existing checkout. | `git@github.com:briceburg/radio-pad-registry-data.git`
REGISTRY_BACKEND_GIT_BRANCH | branch used for fetch/push operations. | `main`
REGISTRY_BACKEND_GIT_FETCH_TTL_SECONDS | read-side fetch freshness window; writes always refresh first. | `30`
REGISTRY_BACKEND_GIT_AUTHOR_NAME | commit author name for registry-managed writes. | `briceburg`
REGISTRY_BACKEND_GIT_AUTHOR_EMAIL | commit author email for registry-managed writes. | `briceburg@users.noreply.github.com`
REGISTRY_BACKEND_GIT_SSH_KEY_PATH | optional SSH private key path for deploy-key authentication. | `None`
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

By default, the Git backend uses `tmp/data` as its checkout path, `git@github.com:briceburg/radio-pad-registry-data.git` as its bootstrap remote, and the GitHub noreply identity for `briceburg` for registry-managed commits.

The intended authentication model is a write-enabled GitHub deploy key over SSH. To run without remote sync, set `REGISTRY_BACKEND_GIT_REMOTE_URL=` and place an existing checkout in `REGISTRY_BACKEND_PATH`.

#### Fly.io deployment

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

This runs the regular unit, API, datastore, and functional tests. Performance tests are excluded by default.

To run the functional tests directly:

```sh
pytest tests/functional -m 'not performance'
```

### Performance Tests

The suite includes performance tests that are disabled by default. To run them, use the `performance` marker:

```sh
pytest tests/functional/test_performance.py -m performance
```

To view the output from performance tests, set the log level:

```sh
pytest tests/functional/test_performance.py -m performance --log-cli-level=INFO
```
