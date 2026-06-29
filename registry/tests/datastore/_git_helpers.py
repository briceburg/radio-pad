from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

TEST_IDENTITY = {
    "GIT_AUTHOR_NAME": "Tests",
    "GIT_AUTHOR_EMAIL": "tests@example.invalid",
    "GIT_COMMITTER_NAME": "Tests",
    "GIT_COMMITTER_EMAIL": "tests@example.invalid",
}


def run_git(
    *args: str,
    cwd: Path | None = None,
    check: bool = True,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command_env = os.environ.copy()
    command_env.update(env or {})
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=command_env,
        capture_output=True,
        text=True,
        check=check,
    )


def init_repo(path: Path, *, branch: str = "main", bare: bool = False) -> None:
    args = ["init", "--quiet", f"--initial-branch={branch}"]
    if bare:
        args.append("--bare")
    run_git(*args, str(path), cwd=None)
