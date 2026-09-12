"""Load and validate ``gearu.toml``."""

from __future__ import annotations

import tomllib
from pathlib import Path
from string import Formatter
from typing import Any

from .errors import GearuError
from .models import (
    CommandSpec,
    DependencyConfig,
    GearuConfig,
    NpmConfig,
    ProjectConfig,
    PythonConfig,
    ReleaseConfig,
    RustConfig,
    RustManifestConfig,
)

_TEMPLATE_FIELDS = frozenset({"name", "version", "python_version", "tag", "repo"})


def _string(value: object, *, field: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not value and not allow_empty):
        qualifier = "a string" if allow_empty else "a non-empty string"
        raise GearuError(f"{field} must be {qualifier}")
    return value


def _template(value: object, *, field: str, allow_empty: bool = False) -> str:
    template = _string(value, field=field, allow_empty=allow_empty)
    try:
        parsed = tuple(Formatter().parse(template))
    except ValueError as error:
        raise GearuError(f"{field} is not a valid template: {error}") from error
    fields = {item[1] for item in parsed if item[1] is not None}
    unsupported = sorted(fields.difference(_TEMPLATE_FIELDS))
    if unsupported:
        raise GearuError(
            f"{field} uses unsupported template fields: {', '.join(unsupported)}"
        )
    return template


def _relative_path(value: object, *, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise GearuError(f"{field} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise GearuError(f"{field} must stay inside the repository")
    return path


def _command(value: object, *, field: str) -> CommandSpec:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(part, str) for part in value)
    ):
        raise GearuError(f"{field} must be a non-empty array of strings")
    command = CommandSpec(
        tuple(
            _template(part, field=f"{field}[{index}]", allow_empty=True)
            for index, part in enumerate(value)
        )
    )
    _reject_registry_publish(command, field=field)
    return command


def _reject_registry_publish(command: CommandSpec, *, field: str) -> None:
    argv = command.argv
    executable = Path(argv[0]).name.lower()
    dry_run = "--dry-run" in argv
    direct_publish = (
        (executable == "cargo" and "publish" in argv[1:] and not dry_run)
        or (
            executable in {"npm", "pnpm", "yarn"}
            and "publish" in argv[1:]
            and not dry_run
        )
        or (
            executable in {"uv", "poetry", "flit", "hatch"}
            and "publish" in argv[1:]
            and not dry_run
        )
        or (executable == "twine" and "upload" in argv[1:])
        or (
            executable.startswith("python")
            and len(argv) >= 4
            and argv[1:4] == ("-m", "twine", "upload")
        )
    )
    if direct_publish:
        raise GearuError(
            f"{field} attempts direct registry publication; publishing belongs in CI"
        )


def _commands(value: object, *, field: str) -> tuple[CommandSpec, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise GearuError(f"{field} must be an array of command arrays")
    return tuple(
        _command(item, field=f"{field}[{index}]") for index, item in enumerate(value)
    )


def _paths(value: object, *, field: str) -> tuple[Path, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise GearuError(f"{field} must be an array of paths")
    return tuple(
        _relative_path(item, field=f"{field}[{index}]")
        for index, item in enumerate(value)
    )


def _optional_command(
    table: dict[str, Any], key: str, *, field: str
) -> CommandSpec | None:
    value = table.get(key)
    return None if value is None else _command(value, field=field)


def _load_python(data: object) -> PythonConfig | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise GearuError("[python] must be a table")
    mode = data.get("version", "static")
    if mode not in ("static", "scm"):
        raise GearuError("python.version must be 'static' or 'scm'")
    return PythonConfig(
        manifest=_relative_path(
            data.get("manifest", "pyproject.toml"), field="python.manifest"
        ),
        version=mode,
        version_key=str(data.get("version_key", "project.version")),
        lockfiles=_paths(data.get("lockfiles"), field="python.lockfiles"),
        lock_command=_optional_command(
            data, "lock_command", field="python.lock_command"
        ),
    )


def _load_rust(data: object) -> RustConfig | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise GearuError("[rust] must be a table")
    raw_manifests = data.get("manifests", ["Cargo.toml"])
    if not isinstance(raw_manifests, list) or not raw_manifests:
        raise GearuError("rust.manifests must be a non-empty array")
    manifests: list[RustManifestConfig] = []
    for index, item in enumerate(raw_manifests):
        if isinstance(item, str):
            manifests.append(
                RustManifestConfig(
                    _relative_path(item, field=f"rust.manifests[{index}]")
                )
            )
        elif isinstance(item, dict):
            manifests.append(
                RustManifestConfig(
                    _relative_path(
                        item.get("path"), field=f"rust.manifests[{index}].path"
                    ),
                    str(item["key"]) if "key" in item else None,
                )
            )
        else:
            raise GearuError(f"rust.manifests[{index}] must be a path or table")
    raw_lockfile = data.get("lockfile")
    lockfile = (
        None
        if raw_lockfile is None
        else _relative_path(raw_lockfile, field="rust.lockfile")
    )
    lock_command = _optional_command(data, "lock_command", field="rust.lock_command")
    if lockfile is not None and lock_command is None:
        lock_command = CommandSpec(("cargo", "generate-lockfile"))
    return RustConfig(tuple(manifests), lockfile, lock_command)


def _load_npm(data: object) -> NpmConfig | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise GearuError("[npm] must be a table")
    raw_lockfile = data.get("lockfile")
    lockfile = (
        None
        if raw_lockfile is None
        else _relative_path(raw_lockfile, field="npm.lockfile")
    )
    lock_command = _optional_command(data, "lock_command", field="npm.lock_command")
    if lockfile is not None and lock_command is None:
        lock_command = CommandSpec(
            ("npm", "install", "--package-lock-only", "--ignore-scripts")
        )
    return NpmConfig(
        manifest=_relative_path(
            data.get("manifest", "package.json"), field="npm.manifest"
        ),
        lockfile=lockfile,
        lock_command=lock_command,
    )


def _load_dependencies(data: object) -> tuple[DependencyConfig, ...]:
    if data is None:
        return ()
    if not isinstance(data, list):
        raise GearuError("[[dependencies]] must be an array of tables")
    dependencies: list[DependencyConfig] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise GearuError(f"dependencies[{index}] must be a table")
        try:
            name = item["name"]
            url = item["url"]
        except KeyError as error:
            raise GearuError(
                f"dependencies[{index}] is missing {error.args[0]}"
            ) from error
        name = _string(name, field=f"dependencies[{index}].name")
        url = _string(url, field=f"dependencies[{index}].url")
        pin_values = (item.get("pin_file"), item.get("pin_key"), item.get("pin_field"))
        if any(value is not None for value in pin_values) and not all(
            isinstance(value, str) and value for value in pin_values
        ):
            raise GearuError(
                f"dependencies[{index}] pin_file, pin_key, and pin_field must be set together"
            )
        dependencies.append(
            DependencyConfig(
                name=name,
                url=url,
                tag_template=_template(
                    item.get("tag", "{tag}"),
                    field=f"dependencies[{index}].tag",
                ),
                pin_file=(
                    _relative_path(
                        pin_values[0], field=f"dependencies[{index}].pin_file"
                    )
                    if pin_values[0] is not None
                    else None
                ),
                pin_key=pin_values[1],
                pin_field=pin_values[2],
                lock_package=(
                    _string(
                        item["lock_package"],
                        field=f"dependencies[{index}].lock_package",
                    )
                    if "lock_package" in item
                    else None
                ),
            )
        )
    names = [dependency.name for dependency in dependencies]
    if len(set(names)) != len(names):
        raise GearuError("dependency names must be unique")
    return tuple(dependencies)


def load_config(root: Path) -> GearuConfig:
    path = root / "gearu.toml"
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise GearuError(f"no gearu.toml found at {path}") from error
    except tomllib.TOMLDecodeError as error:
        raise GearuError(f"invalid gearu.toml: {error}") from error

    project_data = data.get("project")
    if not isinstance(project_data, dict) or not isinstance(
        project_data.get("name"), str
    ):
        raise GearuError("[project].name is required")
    project = ProjectConfig(
        name=_string(project_data["name"], field="project.name"),
        branch=_string(project_data.get("branch", "main"), field="project.branch"),
        remote=_string(project_data.get("remote", "origin"), field="project.remote"),
        tag_prefix=_string(
            project_data.get("tag_prefix", "v"),
            field="project.tag_prefix",
            allow_empty=True,
        ),
        github_repo=(
            _string(project_data["github_repo"], field="project.github_repo")
            if "github_repo" in project_data
            else None
        ),
        source_branch=(
            _string(project_data["source_branch"], field="project.source_branch")
            if "source_branch" in project_data
            else None
        ),
    )
    if project.github_repo is not None and (
        project.github_repo.count("/") != 1
        or any(character.isspace() for character in project.github_repo)
    ):
        raise GearuError("project.github_repo must have the form OWNER/REPOSITORY")
    if project.source_branch == project.branch:
        raise GearuError("project.source_branch must differ from project.branch")

    release_data = data.get("release", {})
    if not isinstance(release_data, dict):
        raise GearuError("[release] must be a table")
    checks = _commands(release_data.get("checks"), field="release.checks")
    if not checks:
        raise GearuError(
            "release.checks must contain at least one verification command"
        )
    exact_checks = _commands(
        release_data.get("exact_checks"), field="release.exact_checks"
    )
    release = ReleaseConfig(
        checks=checks,
        exact_checks=exact_checks or checks,
        managed_files=_paths(
            release_data.get("managed_files"), field="release.managed_files"
        ),
        commit_message=_template(
            release_data.get("commit_message", "chore(release): {name} {version}"),
            field="release.commit_message",
        ),
        github_notes=_template(
            release_data.get("github_notes", "{name} {tag}."),
            field="release.github_notes",
            allow_empty=True,
        ),
    )

    config = GearuConfig(
        project=project,
        release=release,
        python=_load_python(data.get("python")),
        rust=_load_rust(data.get("rust")),
        npm=_load_npm(data.get("npm")),
        dependencies=_load_dependencies(data.get("dependencies")),
    )
    if config.python is None and config.rust is None and config.npm is None:
        raise GearuError(
            "gearu.toml must configure at least one of [python], [rust], or [npm]"
        )
    lock_dependencies = [
        dependency.name
        for dependency in config.dependencies
        if dependency.lock_package is not None
    ]
    if lock_dependencies and (config.rust is None or config.rust.lockfile is None):
        raise GearuError(
            "dependency lock_package verification requires rust.lockfile: "
            + ", ".join(lock_dependencies)
        )
    return config
