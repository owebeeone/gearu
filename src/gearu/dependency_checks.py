"""Validate release dependency resolutions recorded in ecosystem lockfiles."""

from __future__ import annotations

import tomllib
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .errors import GearuError
from .models import DependencyResolution, GearuConfig


def _cargo_git_source_matches(source: object, *, tag: str, sha: str) -> bool:
    if not isinstance(source, str) or not source.startswith("git+"):
        return False
    parsed = urlsplit(source.removeprefix("git+"))
    return parse_qs(parsed.query).get("tag") == [tag] and parsed.fragment == sha


def validate_dependency_locks(
    root: Path,
    config: GearuConfig,
    resolutions: tuple[DependencyResolution, ...],
) -> None:
    dependencies = {
        dependency.name: dependency
        for dependency in config.dependencies
        if dependency.lock_package is not None
    }
    if not dependencies:
        return
    if config.rust is None or config.rust.lockfile is None:
        raise GearuError("dependency lock_package verification requires rust.lockfile")

    path = root / config.rust.lockfile
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise GearuError(f"required Rust lockfile does not exist: {path}") from error
    except tomllib.TOMLDecodeError as error:
        raise GearuError(f"invalid Rust lockfile {path}: {error}") from error

    packages = data.get("package", [])
    by_name = {resolution.name: resolution for resolution in resolutions}
    for name, dependency in dependencies.items():
        resolution = by_name[name]
        sources = [
            package.get("source")
            for package in packages
            if isinstance(package, dict)
            and package.get("name") == dependency.lock_package
        ]
        if not any(
            _cargo_git_source_matches(
                source,
                tag=resolution.tag,
                sha=resolution.sha,
            )
            for source in sources
        ):
            raise GearuError(
                f"{config.rust.lockfile} does not pin {dependency.lock_package} "
                f"to Git tag {resolution.tag} at {resolution.sha}"
            )
