"""Python ``pyproject.toml`` release adapter."""

from __future__ import annotations

from pathlib import Path

from ..errors import GearuError
from ..manifests import replace_toml_string, toml_value
from ..models import CommandSpec, FileChange, PythonConfig
from ..version import ReleaseVersion
from .base import Adapter


class PythonAdapter(Adapter):
    def __init__(self, root: Path, config: PythonConfig) -> None:
        self.root = root
        self.config = config

    def _path(self) -> Path:
        return self.root / self.config.manifest

    def current_versions(self) -> tuple[str, ...]:
        if self.config.version == "scm":
            self._validate_scm()
            return ()
        current = toml_value(self._path(), self.config.version_key)
        if not isinstance(current, str):
            raise GearuError(f"{self.config.manifest} version is not a string")
        return (current,)

    def plan(self, version: ReleaseVersion) -> tuple[FileChange, ...]:
        if self.config.version == "scm":
            self._validate_scm()
            return ()
        current = toml_value(self._path(), self.config.version_key)
        if not isinstance(current, str):
            raise GearuError(f"{self.config.manifest} version is not a string")
        if current == version.python_text:
            return ()
        return (
            FileChange(
                self.config.manifest,
                current,
                version.python_text,
                "Python distribution version",
            ),
        )

    def apply(self, version: ReleaseVersion) -> set[Path]:
        if self.config.version == "scm":
            self._validate_scm()
            return set()
        changed = replace_toml_string(
            self._path(), self.config.version_key, version.python_text
        )
        return {self.config.manifest} if changed else set()

    def validate(self, version: ReleaseVersion) -> None:
        if self.config.version == "scm":
            self._validate_scm()
            return
        current = toml_value(self._path(), self.config.version_key)
        if current != version.python_text:
            raise GearuError(
                f"{self.config.manifest} version is {current!r}, expected {version.python_text!r}"
            )

    def _validate_scm(self) -> None:
        dynamic = toml_value(self._path(), "project.dynamic")
        if not isinstance(dynamic, list) or "version" not in dynamic:
            raise GearuError(
                f"{self.config.manifest} must declare project.dynamic = ['version'] for SCM versions"
            )

    def managed_files(self) -> set[Path]:
        files = set(self.config.lockfiles)
        if self.config.version == "static":
            files.add(self.config.manifest)
        return files

    def refresh_commands(self, touched: set[Path]) -> tuple[CommandSpec, ...]:
        if self.config.lock_command is None or self.config.manifest not in touched:
            return ()
        return (self.config.lock_command,)
