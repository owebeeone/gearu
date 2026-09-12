"""Cargo manifest and lockfile release adapter."""

from __future__ import annotations

from pathlib import Path

from ..errors import GearuError
from ..manifests import replace_toml_string, toml_value
from ..models import CommandSpec, FileChange, RustConfig, RustManifestConfig
from ..version import ReleaseVersion
from .base import Adapter


class RustAdapter(Adapter):
    def __init__(self, root: Path, config: RustConfig) -> None:
        self.root = root
        self.config = config

    def _key(self, manifest: RustManifestConfig) -> str:
        if manifest.key is not None:
            return manifest.key
        path = self.root / manifest.path
        try:
            package_version = toml_value(path, "package.version")
        except GearuError:
            package_version = None
        if isinstance(package_version, str):
            return "package.version"
        workspace_version = toml_value(path, "workspace.package.version")
        if isinstance(workspace_version, str):
            return "workspace.package.version"
        raise GearuError(f"could not find a package version in {manifest.path}")

    def current_versions(self) -> tuple[str, ...]:
        versions: list[str] = []
        for manifest in self.config.manifests:
            current = toml_value(self.root / manifest.path, self._key(manifest))
            if not isinstance(current, str):
                raise GearuError(f"{manifest.path} version is not a string")
            versions.append(current)
        return tuple(versions)

    def plan(self, version: ReleaseVersion) -> tuple[FileChange, ...]:
        changes: list[FileChange] = []
        for manifest in self.config.manifests:
            current = toml_value(self.root / manifest.path, self._key(manifest))
            if not isinstance(current, str):
                raise GearuError(f"{manifest.path} version is not a string")
            if current != version.text:
                changes.append(
                    FileChange(
                        manifest.path, current, version.text, "Cargo package version"
                    )
                )
        return tuple(changes)

    def apply(self, version: ReleaseVersion) -> set[Path]:
        changed: set[Path] = set()
        for manifest in self.config.manifests:
            if replace_toml_string(
                self.root / manifest.path, self._key(manifest), version.text
            ):
                changed.add(manifest.path)
        return changed

    def validate(self, version: ReleaseVersion) -> None:
        for manifest in self.config.manifests:
            current = toml_value(self.root / manifest.path, self._key(manifest))
            if current != version.text:
                raise GearuError(
                    f"{manifest.path} version is {current!r}, expected {version.text!r}"
                )

    def managed_files(self) -> set[Path]:
        files = {manifest.path for manifest in self.config.manifests}
        if self.config.lockfile is not None:
            files.add(self.config.lockfile)
        return files

    def refresh_commands(self, touched: set[Path]) -> tuple[CommandSpec, ...]:
        manifests = {manifest.path for manifest in self.config.manifests}
        if self.config.lock_command is None or not manifests.intersection(touched):
            return ()
        return (self.config.lock_command,)
