"""Prod smoke test for the registry git backend.

Exercises entrypoint SSH plumbing and system Git without a real remote.
Run inside the registry-git prod container via compose.prod-smoke.yaml.
"""

import json
import os
import pathlib
import subprocess
import tempfile


def git(*args: str, cwd: pathlib.Path | None = None, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def main() -> None:
    # -- entrypoint plumbing --
    key = pathlib.Path(os.environ["REGISTRY_BACKEND_GIT_SSH_KEY_PATH"])
    assert key.exists(), f"SSH key not written: {key}"
    cmd = os.environ.get("GIT_SSH_COMMAND", "")
    assert str(key) in cmd, f"GIT_SSH_COMMAND missing key: {cmd}"
    assert "UserKnownHostsFile=" in cmd, f"GIT_SSH_COMMAND missing known-hosts path: {cmd}"
    assert "StrictHostKeyChecking" in cmd, f"GIT_SSH_COMMAND missing host check: {cmd}"
    known_hosts = pathlib.Path(
        next(arg.split("=", 1)[1] for arg in cmd.split() if arg.startswith("UserKnownHostsFile="))
    )
    assert known_hosts.exists(), f"SSH known-hosts file not created: {known_hosts}"
    print(f"entrypoint: ok  (GIT_SSH_COMMAND={cmd})")

    print(f"system git: {git('--version')}")

    # -- local init / add / commit round-trip --
    with tempfile.TemporaryDirectory() as td:
        rp = pathlib.Path(td) / "smoke"
        git("init", "--quiet", "--initial-branch=main", str(rp))
        (rp / "test.json").write_text(json.dumps({"ok": True}))
        git("add", "--", "test.json", cwd=rp)
        identity = os.environ | {
            "GIT_AUTHOR_NAME": "smoke",
            "GIT_AUTHOR_EMAIL": "smoke@test",
            "GIT_COMMITTER_NAME": "smoke",
            "GIT_COMMITTER_EMAIL": "smoke@test",
        }
        git("commit", "--quiet", "--message", "smoke", cwd=rp, env=identity)
        sha = git("rev-parse", "HEAD", cwd=rp)
        assert sha
        print(f"system git: local commit {sha[:12]}")

    print("registry-git smoke: ok")


if __name__ == "__main__":
    main()
