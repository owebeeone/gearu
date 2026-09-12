from __future__ import annotations

from pathlib import Path

import pytest

from gearu.config import load_config
from gearu.errors import GearuError


def test_load_config_supports_scm_python_project(tmp_path: Path) -> None:
    (tmp_path / "gearu.toml").write_text(
        """
[project]
name = "gearu"
branch = "main"
remote = "origin"
tag_prefix = "v"
github_repo = "owebeeone/gearu"

[python]
manifest = "pyproject.toml"
version = "scm"

[release]
checks = [["python", "run_tests.py"]]
""".lstrip(),
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config.project.name == "gearu"
    assert config.project.github_repo == "owebeeone/gearu"
    assert config.python is not None
    assert config.python.version == "scm"
    assert config.release.checks[0].argv == ("python", "run_tests.py")


@pytest.mark.parametrize(
    "command",
    [
        '["cargo", "publish"]',
        '["npm", "publish"]',
        '["uv", "publish"]',
        '["python", "-m", "twine", "upload", "dist/file.whl"]',
    ],
)
def test_config_rejects_local_registry_publish_commands(
    tmp_path: Path, command: str
) -> None:
    (tmp_path / "gearu.toml").write_text(
        f"""
[project]
name = "unsafe"

[python]
version = "scm"

[release]
checks = [{command}]
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(GearuError, match="publishing belongs in CI"):
        load_config(tmp_path)


def test_config_allows_registry_dry_run(tmp_path: Path) -> None:
    (tmp_path / "gearu.toml").write_text(
        """
[project]
name = "safe"

[rust]

[release]
checks = [["cargo", "publish", "--dry-run"]]
""".lstrip(),
        encoding="utf-8",
    )

    config = load_config(tmp_path)
    assert config.release.checks[0].argv[-1] == "--dry-run"


def test_config_requires_a_release_check(tmp_path: Path) -> None:
    (tmp_path / "gearu.toml").write_text(
        """
[project]
name = "unchecked"

[python]
version = "scm"
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(GearuError, match="at least one verification command"):
        load_config(tmp_path)


def test_config_rejects_unknown_template_fields(tmp_path: Path) -> None:
    (tmp_path / "gearu.toml").write_text(
        """
[project]
name = "bad-template"

[python]
version = "scm"

[release]
checks = [["python", "-c", "print('{unknown}')"]]
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(GearuError, match="unsupported template fields: unknown"):
        load_config(tmp_path)


def test_config_rejects_malformed_github_repository(tmp_path: Path) -> None:
    (tmp_path / "gearu.toml").write_text(
        """
[project]
name = "bad-repository"
github_repo = "owebeeone/gearu/extra"

[python]
version = "scm"

[release]
checks = [["python", "-c", "pass"]]
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(GearuError, match="OWNER/REPOSITORY"):
        load_config(tmp_path)


def test_lock_package_requires_a_rust_lockfile(tmp_path: Path) -> None:
    (tmp_path / "gearu.toml").write_text(
        """
[project]
name = "consumer"

[rust]

[[dependencies]]
name = "core"
url = "https://github.com/example/core"
lock_package = "example-core"

[release]
checks = [["cargo", "test"]]
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(GearuError, match="requires rust.lockfile"):
        load_config(tmp_path)
