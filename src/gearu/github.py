"""Create GitHub Releases after the exact tag has been pushed."""

from __future__ import annotations

import shutil
from pathlib import Path

from .errors import GearuError
from .process import Runner


class GitHubReleases:
    def __init__(self, root: Path, runner: Runner) -> None:
        self.root = root
        self.runner = runner

    def create(
        self, *, repository: str, tag: str, notes: str, prerelease: bool
    ) -> bool:
        if shutil.which("gh") is None:
            raise GearuError("creating a GitHub Release requires the `gh` command")
        existing = self.runner.run(
            ["gh", "release", "view", tag, "--repo", repository],
            cwd=self.root,
            capture=True,
            check=False,
        )
        if existing.returncode == 0:
            return False
        command = [
            "gh",
            "release",
            "create",
            tag,
            "--verify-tag",
            "--repo",
            repository,
            "--title",
            tag,
            "--notes",
            notes,
        ]
        if prerelease:
            command.append("--prerelease")
        self.runner.run(command, cwd=self.root)
        return True
