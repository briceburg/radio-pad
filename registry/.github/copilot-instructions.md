## Copilot instructions for radio-pad-registry

FastAPI and Pydantic driven service to register and share resources connecting [radio-pad](https://github.com/briceburg/radio-pad) players and clients (aka remote-controls) — such as global or account-specific station presets.

Data is stored as JSON files in a hierarchical datastore layer using swappable backends (local storage, S3, etc.), accessed via a typed `ModelStore` built on a backend `ObjectStore` interface.

### Quick references
- this is an in-development project -- there is no need to maintain compatability with older clients or code. please avoid shims.
- `bin/ci` is used by the CI pipeline to run static analysis checks.
- `pytest` is used for running tests
- `.github/workflows/ci.yaml` runs both bin/ci and pytest as part of CI before merge.
- Please run commands in an activated virtual environment (venv). 
- `requirements-latest.txt` is used to add dependendencies. this is frozen to `requirements.txt`. `requirements-dev.txt` is for development dependencies, and should be installed before running pytest or `bin/ci`.
