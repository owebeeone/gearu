"""npm package manifest and lockfile release adapter."""

from __future__ import annotations

import json
from pathlib import Path

from ..errors import GearuError
from ..manifests import replace_json_top_level_string
from ..models import CommandSpec, FileChange, NpmConfig
from ..version import ReleaseVersion
from .base import Adapter


class NpmAdapter(Adapter):
    def __init__(self, root: Path, config: NpmConfig) -> None:
        self.root = root
        self.config = config

    def _version(self) -> str:
        path = self.root / self.config.manifest
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as error:
            raise GearuError(
                f"could not read npm manifest {self.config.manifest}: {error}"
            ) from error
        value = data.get("version") if isinstance(data, dict) else None
        if not isinstance(value, str):
            raise GearuError(f"{self.config.manifest} has no top-level version string")
        return value

    def current_versions(self) -> tuple[str, ...]:
        return (self._version(),)

    def plan(self, version: ReleaseVersion) -> tuple[FileChange, ...]:
        current = self._version()
        if current == version.text:
            return ()
        return (
            FileChange(
                self.config.manifest, current, version.text, "npm package version"
            ),
        )

    def apply(self, version: ReleaseVersion) -> set[Path]:
        changed = replace_json_top_level_string(
            self.root / self.config.manifest, "version", version.text
        )
        return {self.config.manifest} if changed else set()

    def validate(self, version: ReleaseVersion) -> None:
        current = self._version()
        if current != version.text:
            raise GearuError(
                f"{self.config.manifest} version is {current!r}, expected {version.text!r}"
            )

    def managed_files(self) -> set[Path]:
        files = {self.config.manifest}
        if self.config.lockfile is not None:
            files.add(self.config.lockfile)
        return files

    def refresh_commands(self, touched: set[Path]) -> tuple[CommandSpec, ...]:
        if self.config.lock_command is None or self.config.manifest not in touched:
            return ()
        return (self.config.lock_command,)
