"""Configuration and release result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .errors import GearuError


@dataclass(frozen=True)
class CommandSpec:
    argv: tuple[str, ...]
    name: str = ""

    def expanded(self, values: dict[str, str]) -> tuple[str, ...]:
        try:
            return tuple(part.format_map(values) for part in self.argv)
        except (KeyError, ValueError) as error:
            raise GearuError(
                f"invalid command template in {' '.join(self.argv)!r}: {error}"
            ) from error


@dataclass(frozen=True)
class ProjectConfig:
    name: str
    branch: str = "main"
    remote: str = "origin"
    tag_prefix: str = "v"
    github_repo: str | None = None
    source_branch: str | None = None


@dataclass(frozen=True)
class PythonConfig:
    manifest: Path = Path("pyproject.toml")
    version: str = "static"
    version_key: str = "project.version"
    lockfiles: tuple[Path, ...] = ()
    lock_command: CommandSpec | None = None


@dataclass(frozen=True)
class RustManifestConfig:
    path: Path
    key: str | None = None


@dataclass(frozen=True)
class RustConfig:
    manifests: tuple[RustManifestConfig, ...]
    lockfile: Path | None = None
    lock_command: CommandSpec | None = None


@dataclass(frozen=True)
class NpmConfig:
    manifest: Path = Path("package.json")
    lockfile: Path | None = None
    lock_command: CommandSpec | None = None


@dataclass(frozen=True)
class DependencyConfig:
    name: str
    url: str
    tag_template: str = "{tag}"
    pin_file: Path | None = None
    pin_key: str | None = None
    pin_field: str | None = None
    lock_package: str | None = None


@dataclass(frozen=True)
class ReleaseConfig:
    checks: tuple[CommandSpec, ...] = ()
    exact_checks: tuple[CommandSpec, ...] = ()
    managed_files: tuple[Path, ...] = ()
    commit_message: str = "chore(release): {name} {version}"
    github_notes: str = "{name} {tag}."


@dataclass(frozen=True)
class GearuConfig:
    project: ProjectConfig
    release: ReleaseConfig
    python: PythonConfig | None = None
    rust: RustConfig | None = None
    npm: NpmConfig | None = None
    dependencies: tuple[DependencyConfig, ...] = ()


@dataclass(frozen=True)
class FileChange:
    path: Path
    current: str
    target: str
    reason: str


@dataclass(frozen=True)
class DependencyResolution:
    name: str
    url: str
    tag: str
    sha: str


@dataclass(frozen=True)
class ReleasePlan:
    name: str
    version: str
    tag: str
    branch: str
    base_sha: str
    changes: tuple[FileChange, ...]
    dependencies: tuple[DependencyResolution, ...]
    checks: tuple[CommandSpec, ...]
    already_tagged: bool = False
    source_branch: str | None = None
    source_sha: str | None = None
    bump: str | None = None
    bump_base: str | None = None


@dataclass(frozen=True)
class ReleaseOptions:
    push: bool = False
    github_release: bool = False
    dependency_tags: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ReleaseOutcome:
    version: str
    tag: str
    target_sha: str
    created_commit: bool
    pushed: bool
    github_release_created: bool
