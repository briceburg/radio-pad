import multiprocessing
import os
import shutil
import socket
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

from lib.constants import BASE_DIR


def run_server(data_path: str, host: str, port: int):
    os.environ["DATA_PATH"] = data_path
    uvicorn.run("registry:app", host=host, port=port, log_level="warning")


@pytest.fixture(scope="session")
def functional_tests_root() -> Path:
    root = BASE_DIR / "tmp" / "tests" / "functional"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture(scope="session")
def functional_client(functional_tests_root: Path):
    functional_data = functional_tests_root / "data"
    if functional_data.exists():
        shutil.rmtree(functional_data)
    functional_data.mkdir(parents=True, exist_ok=True)

    host = "127.0.0.1"
    # Pick an ephemeral free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        port = s.getsockname()[1]
    base_url = f"http://{host}:{port}"

    # Use "forkserver" if available, else fallback to "spawn" (Python 3.13+ default is "spawn")
    ctx = multiprocessing.get_context(
        "forkserver" if "forkserver" in multiprocessing.get_all_start_methods() else "spawn"
    )
    server_process = ctx.Process(target=run_server, args=(str(functional_data), host, port))
    server_process.daemon = True
    try:
        server_process.start()
        # Wait for the server to be ready by polling the health check endpoint
        max_wait = 10  # seconds (allow a bit more in CI)
        start_time = time.time()
        delay = 0.05
        while time.time() - start_time < max_wait:
            try:
                r = httpx.get(f"{base_url}/healthz", timeout=1.0)
                if r.status_code in (200, 204):
                    break
            except httpx.HTTPError:
                time.sleep(delay)
                delay = min(delay * 2, 0.5)  # progressive backoff up to 500ms
        else:
            pytest.fail("Server did not start within the specified timeout.")

        with httpx.Client(base_url=base_url, timeout=httpx.Timeout(5.0)) as client:
            yield client

    finally:
        if server_process.is_alive():
            server_process.terminate()
            server_process.join(timeout=2)
        if server_process.is_alive():
            # Fallback to kill if terminate didn't stop it promptly
            server_process.kill()
            server_process.join(timeout=2)
        if functional_data.exists():
            shutil.rmtree(functional_data)
