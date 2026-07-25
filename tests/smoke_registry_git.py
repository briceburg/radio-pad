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
    key_count = 0
    for role in ("DATA", "AUTHZ"):
        if not os.environ.get(f"REGISTRY_{role}_BACKEND_GIT_SSH_PRIVATE_KEY"):
            continue
        variable = f"REGISTRY_{role}_BACKEND_GIT_SSH_KEY_PATH"
        key_path = os.environ.get(variable)
        assert key_path, f"{variable} not exported"
        key = pathlib.Path(key_path)
        assert key.is_file(), f"SSH key not written: {key}"
        key_count += 1
    assert key_count, "No Git SSH private key configured"
    assert (pathlib.Path.home() / ".ssh").is_dir(), "SSH home not created"
    print("entrypoint: ok")

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
