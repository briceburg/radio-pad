"""Prod smoke test for the registry git backend.

Exercises entrypoint SSH plumbing and dulwich operations without a real remote.
Run inside the registry-git prod container via compose.prod-smoke.yaml.
"""

import json
import os
import pathlib
import tempfile


def main() -> None:
    # -- entrypoint plumbing --
    key = pathlib.Path(os.environ["REGISTRY_BACKEND_GIT_SSH_KEY_PATH"])
    assert key.exists(), f"SSH key not written: {key}"
    cmd = os.environ.get("GIT_SSH_COMMAND", "")
    assert str(key) in cmd, f"GIT_SSH_COMMAND missing key: {cmd}"
    assert "StrictHostKeyChecking" in cmd, f"GIT_SSH_COMMAND missing host check: {cmd}"
    print(f"entrypoint: ok  (GIT_SSH_COMMAND={cmd})")

    # -- dulwich native extensions load --
    from dulwich import porcelain
    from dulwich.client import SSHGitClient, get_transport_and_path
    from dulwich.repo import Repo

    print("dulwich: imported")

    # -- local init / add / commit round-trip --
    with tempfile.TemporaryDirectory() as td:
        rp = pathlib.Path(td) / "smoke"
        porcelain.init(str(rp))
        (rp / "test.json").write_text(json.dumps({"ok": True}))
        porcelain.add(str(rp), paths=["test.json"])
        sha = porcelain.commit(
            str(rp),
            message=b"smoke",
            author=b"smoke <smoke@test>",
            committer=b"smoke <smoke@test>",
        )
        assert sha and Repo(str(rp)).head() == sha
        print(f"dulwich: local commit {sha.hex()[:12]}")

    # -- SSH transport picks up GIT_SSH_COMMAND --
    client, _ = get_transport_and_path("git@github.com:example/repo.git")
    assert isinstance(client, SSHGitClient), f"wrong client: {type(client)}"
    assert client.ssh_command == cmd, f"transport mismatch: {client.ssh_command!r}"
    print("dulwich: SSH transport wired")

    print("registry-git smoke: ok")


if __name__ == "__main__":
    main()
