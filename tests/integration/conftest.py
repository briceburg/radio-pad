import os

import httpx
import pytest


@pytest.fixture
def registry_url():
    return os.environ["REGISTRY_URL"]


@pytest.fixture
def switchboard_url():
    return os.environ["SWITCHBOARD_URL"]


@pytest.fixture
def remote_control_url():
    return os.environ["REMOTE_CONTROL_URL"]


@pytest.fixture
def http():
    """Shared httpx client that follows redirects (handles FastAPI slash redirects)."""
    with httpx.Client(follow_redirects=True) as client:
        yield client
