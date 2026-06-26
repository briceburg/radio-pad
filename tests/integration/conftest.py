import os

import httpx
import pytest


@pytest.fixture(scope="session")
def registry_url():
    return os.environ["REGISTRY_URL"]


@pytest.fixture(scope="session")
def switchboard_url():
    return os.environ["SWITCHBOARD_URL"]


@pytest.fixture(scope="session")
def remote_control_url():
    return os.environ["REMOTE_CONTROL_URL"]


@pytest.fixture(scope="session")
def http():
    """Shared httpx client that follows redirects (handles FastAPI slash redirects)."""
    with httpx.Client(follow_redirects=True) as client:
        yield client
