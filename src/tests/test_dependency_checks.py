from __future__ import annotations

from pathlib import Path

import pytest

from gearu.dependency_checks import validate_dependency_locks
from gearu.errors import GearuError
from gearu.models import (
    DependencyConfig,
    DependencyResolution,
    GearuConfig,
    ProjectConfig,
    ReleaseConfig,
    RustConfig,
    RustManifestConfig,
)


def config() -> GearuConfig:
    return GearuConfig(
        project=ProjectConfig("consumer"),
        release=ReleaseConfig(),
        rust=RustConfig(
            manifests=(RustManifestConfig(Path("Cargo.toml")),),
            lockfile=Path("Cargo.lock"),
        ),
        dependencies=(
            DependencyConfig(
                name="core",
                url="https://github.com/example/core",
                lock_package="example-core",
            ),
        ),
    )


def resolution() -> DependencyResolution:
    return DependencyResolution(
        name="core",
        url="https://github.com/example/core",
        tag="v1.2.3",
        sha="a" * 40,
    )


def test_validate_dependency_locks_accepts_exact_cargo_git_pin(
    tmp_path: Path,
) -> None:
    (tmp_path / "Cargo.lock").write_text(
        f"""
version = 4

[[package]]
name = "example-core"
version = "1.2.3"
source = "git+https://github.com/example/core?tag=v1.2.3#{"a" * 40}"
""".lstrip(),
        encoding="utf-8",
    )

    validate_dependency_locks(tmp_path, config(), (resolution(),))


def test_validate_dependency_locks_rejects_wrong_cargo_commit(
    tmp_path: Path,
) -> None:
    (tmp_path / "Cargo.lock").write_text(
        f"""
version = 4

[[package]]
name = "example-core"
version = "1.2.3"
source = "git+https://github.com/example/core?tag=v1.2.3#{"b" * 40}"
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(GearuError, match="does not pin example-core"):
        validate_dependency_locks(tmp_path, config(), (resolution(),))
