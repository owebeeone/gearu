from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gearu.cli import main
from gearu.config import load_config
from gearu.errors import GearuError
from gearu.release import ReleaseManager, ReleaseOptions


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def write_project(repo: Path, *, version_mode: str, check_command: str) -> None:
    if version_mode == "scm":
        version_metadata = 'dynamic = ["version"]'
    else:
        version_metadata = 'version = "1.0.0"'
    (repo / "pyproject.toml").write_text(
        f'[project]\nname = "demo"\n{version_metadata}\n',
        encoding="utf-8",
    )
    (repo / "gearu.toml").write_text(
        f"""
[project]
name = "demo"
branch = "main"
remote = "origin"
tag_prefix = "v"

[python]
manifest = "pyproject.toml"
version = "{version_mode}"

[release]
checks = [["python", "-c", {check_command!r}]]
""".lstrip(),
        encoding="utf-8",
    )


def make_project(
    tmp_path: Path, *, version_mode: str = "static", failing: bool = False
) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    git(tmp_path, "init", "--bare", str(remote))
    git(tmp_path, "init", "-b", "main", str(repo))
    git(repo, "config", "user.name", "Gearu Test")
    git(repo, "config", "user.email", "gearu@example.test")
    check_command = "raise SystemExit(7)" if failing else "print('candidate ok')"
    write_project(repo, version_mode=version_mode, check_command=check_command)
    git(repo, "add", ".")
    git(repo, "commit", "-m", "initial")
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", "main")
    return repo, remote


def manager(repo: Path) -> ReleaseManager:
    return ReleaseManager(repo, load_config(repo), log=lambda _message: None)


def test_static_release_commits_tags_and_can_push_on_retry(tmp_path: Path) -> None:
    repo, remote = make_project(tmp_path)
    initial = git(repo, "rev-parse", "HEAD").stdout.strip()
    release = manager(repo)

    plan = release.plan("1.2.3")
    assert plan.tag == "v1.2.3"
    assert plan.base_sha == initial
    assert [change.path.as_posix() for change in plan.changes] == ["pyproject.toml"]

    outcome = release.release("1.2.3", ReleaseOptions())
    released = git(repo, "rev-parse", "HEAD").stdout.strip()
    assert outcome.target_sha == released
    assert outcome.created_commit is True
    assert git(repo, "rev-parse", "v1.2.3^{commit}").stdout.strip() == released
    assert git(repo, "status", "--porcelain").stdout == ""
    assert git(remote, "rev-parse", "refs/heads/main").stdout.strip() == initial

    retry = release.release("1.2.3", ReleaseOptions(push=True))
    assert retry.target_sha == released
    assert retry.created_commit is False
    assert git(remote, "rev-parse", "refs/heads/main").stdout.strip() == released
    assert (
        git(remote, "rev-parse", "refs/tags/v1.2.3^{commit}").stdout.strip() == released
    )


def test_failed_candidate_does_not_change_checkout(tmp_path: Path) -> None:
    repo, _remote = make_project(tmp_path, failing=True)
    initial = git(repo, "rev-parse", "HEAD").stdout.strip()

    with pytest.raises(GearuError, match="command failed"):
        manager(repo).release("1.2.3", ReleaseOptions())

    assert git(repo, "rev-parse", "HEAD").stdout.strip() == initial
    assert git(repo, "status", "--porcelain").stdout == ""
    assert (
        git(repo, "rev-parse", "--verify", "refs/tags/v1.2.3", check=False).returncode
        != 0
    )


def test_scm_release_tags_existing_commit_without_release_commit(
    tmp_path: Path,
) -> None:
    repo, _remote = make_project(tmp_path, version_mode="scm")
    initial = git(repo, "rev-parse", "HEAD").stdout.strip()

    outcome = manager(repo).release("1.2.3", ReleaseOptions())

    assert outcome.target_sha == initial
    assert outcome.created_commit is False
    assert git(repo, "rev-parse", "v1.2.3^{commit}").stdout.strip() == initial


def test_existing_tag_is_never_moved(tmp_path: Path) -> None:
    repo, _remote = make_project(tmp_path)
    initial = git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "tag", "v1.2.3", initial)
    (repo / "note.txt").write_text("later\n", encoding="utf-8")
    git(repo, "add", "note.txt")
    git(repo, "commit", "-m", "later")

    with pytest.raises(GearuError, match="refusing to move"):
        manager(repo).release("1.2.3", ReleaseOptions())

    assert git(repo, "rev-parse", "v1.2.3^{commit}").stdout.strip() == initial


def test_release_verifies_and_updates_remote_dependency_tag(tmp_path: Path) -> None:
    dependency_remote = tmp_path / "dependency.git"
    dependency_repo = tmp_path / "dependency"
    git(tmp_path, "init", "--bare", str(dependency_remote))
    git(tmp_path, "init", "-b", "main", str(dependency_repo))
    git(dependency_repo, "config", "user.name", "Gearu Test")
    git(dependency_repo, "config", "user.email", "gearu@example.test")
    (dependency_repo / "README.md").write_text("dependency\n", encoding="utf-8")
    git(dependency_repo, "add", ".")
    git(dependency_repo, "commit", "-m", "dependency")
    git(dependency_repo, "tag", "v1.2.3")
    git(dependency_repo, "remote", "add", "origin", str(dependency_remote))
    git(dependency_repo, "push", "origin", "main", "v1.2.3")

    repo, _remote = make_project(tmp_path / "consumer")
    with (repo / "pyproject.toml").open("a", encoding="utf-8") as manifest:
        manifest.write(
            f'\n[dependencies]\ncore = {{ git = "{dependency_remote}", tag = "v1.0.0" }}\n'
        )
    with (repo / "gearu.toml").open("a", encoding="utf-8") as config:
        config.write(
            f"""

[[dependencies]]
name = "core"
url = "{dependency_remote}"
tag = "{{tag}}"
pin_file = "pyproject.toml"
pin_key = "dependencies.core"
pin_field = "tag"
"""
        )
    git(repo, "add", ".")
    git(repo, "commit", "-m", "configure dependency")
    git(repo, "push", "origin", "main")

    plan = manager(repo).plan("1.2.3")
    assert plan.dependencies[0].tag == "v1.2.3"
    assert any(change.reason == "core dependency tag" for change in plan.changes)

    manager(repo).release("1.2.3", ReleaseOptions())
    data = (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert 'tag = "v1.2.3"' in data


def test_missing_dependency_tag_stops_before_candidate_changes(tmp_path: Path) -> None:
    dependency_remote = tmp_path / "missing-dependency.git"
    git(tmp_path, "init", "--bare", str(dependency_remote))
    repo, _remote = make_project(tmp_path / "consumer")
    with (repo / "gearu.toml").open("a", encoding="utf-8") as config:
        config.write(
            f'\n[[dependencies]]\nname = "core"\nurl = "{dependency_remote}"\n'
        )
    git(repo, "add", "gearu.toml")
    git(repo, "commit", "-m", "configure dependency")
    git(repo, "push", "origin", "main")
    initial = git(repo, "rev-parse", "HEAD").stdout.strip()

    with pytest.raises(GearuError, match="was not found"):
        manager(repo).release("1.2.3", ReleaseOptions())

    assert git(repo, "rev-parse", "HEAD").stdout.strip() == initial
    assert git(repo, "status", "--porcelain").stdout == ""


def test_release_branch_merges_source_inside_candidate(tmp_path: Path) -> None:
    repo, remote = make_project(tmp_path)
    config_path = repo / "gearu.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            'branch = "main"',
            'branch = "release"\nsource_branch = "main"',
        ),
        encoding="utf-8",
    )
    git(repo, "add", "gearu.toml")
    git(repo, "commit", "-m", "configure release branch")
    git(repo, "push", "origin", "main")
    git(repo, "branch", "release")
    git(repo, "push", "-u", "origin", "release")
    (repo / "feature.txt").write_text("from main\n", encoding="utf-8")
    git(repo, "add", "feature.txt")
    git(repo, "commit", "-m", "feature")
    git(repo, "push", "origin", "main")
    git(repo, "switch", "release")
    release_base = git(repo, "rev-parse", "HEAD").stdout.strip()

    plan = manager(repo).plan("1.2.3")
    assert plan.source_branch == "main"
    assert plan.source_sha == git(repo, "rev-parse", "main").stdout.strip()

    outcome = manager(repo).release("1.2.3", ReleaseOptions())
    assert outcome.created_commit is True
    assert git(repo, "rev-parse", "HEAD").stdout.strip() != release_base
    assert (repo / "feature.txt").read_text(encoding="utf-8") == "from main\n"
    assert git(repo, "status", "--porcelain").stdout == ""
    assert git(remote, "rev-parse", "refs/heads/release").stdout.strip() == release_base


def test_dependency_pin_url_must_match_verified_remote(tmp_path: Path) -> None:
    dependency_remote = tmp_path / "dependency.git"
    dependency_repo = tmp_path / "dependency"
    git(tmp_path, "init", "--bare", str(dependency_remote))
    git(tmp_path, "init", "-b", "main", str(dependency_repo))
    git(dependency_repo, "config", "user.name", "Gearu Test")
    git(dependency_repo, "config", "user.email", "gearu@example.test")
    (dependency_repo / "README.md").write_text("dependency\n", encoding="utf-8")
    git(dependency_repo, "add", ".")
    git(dependency_repo, "commit", "-m", "dependency")
    git(dependency_repo, "tag", "v1.2.3")
    git(dependency_repo, "remote", "add", "origin", str(dependency_remote))
    git(dependency_repo, "push", "origin", "main", "v1.2.3")

    repo, _remote = make_project(tmp_path / "consumer")
    with (repo / "pyproject.toml").open("a", encoding="utf-8") as manifest:
        manifest.write(
            '\n[dependencies]\ncore = { git = "https://example.invalid/core", '
            'tag = "v1.0.0" }\n'
        )
    with (repo / "gearu.toml").open("a", encoding="utf-8") as config:
        config.write(
            f"""

[[dependencies]]
name = "core"
url = "{dependency_remote}"
tag = "{{tag}}"
pin_file = "pyproject.toml"
pin_key = "dependencies.core"
pin_field = "tag"
"""
        )
    git(repo, "add", ".")
    git(repo, "commit", "-m", "configure dependency")
    git(repo, "push", "origin", "main")

    with pytest.raises(GearuError, match="but gearu.toml uses"):
        manager(repo).plan("1.2.3")


def test_cli_plan_is_non_mutating(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, _remote = make_project(tmp_path)
    initial = git(repo, "rev-parse", "HEAD").stdout.strip()

    result = main(["plan", "1.2.3", "--repo", str(repo)])

    assert result == 0
    assert "Release: 1.2.3 (v1.2.3)" in capsys.readouterr().out
    assert git(repo, "rev-parse", "HEAD").stdout.strip() == initial
    assert git(repo, "status", "--porcelain").stdout == ""


def test_plan_bump_uses_manifest_version_without_creating_tag(tmp_path: Path) -> None:
    repo, _remote = make_project(tmp_path)

    plan = manager(repo).plan(None, bump="minor")

    assert plan.version == "1.1.0"
    assert plan.tag == "v1.1.0"
    assert plan.bump == "minor"
    assert plan.bump_base == "1.0.0"
    assert (
        git(repo, "rev-parse", "--verify", "refs/tags/v1.1.0", check=False).returncode
        != 0
    )


def test_plan_bump_considers_remote_release_tags(tmp_path: Path) -> None:
    repo, _remote = make_project(tmp_path)
    git(repo, "tag", "v1.4.2")
    git(repo, "push", "origin", "v1.4.2")
    git(repo, "tag", "-d", "v1.4.2")

    plan = manager(repo).plan(None, bump="patch")

    assert plan.version == "1.4.3"
    assert plan.bump_base == "1.4.2"
    assert (
        git(repo, "rev-parse", "--verify", "refs/tags/v1.4.3", check=False).returncode
        != 0
    )


def test_release_accepts_bump_instead_of_explicit_version(tmp_path: Path) -> None:
    repo, _remote = make_project(tmp_path)

    outcome = manager(repo).release(None, ReleaseOptions(), bump="minor")

    assert outcome.version == "1.1.0"
    assert git(repo, "rev-parse", "v1.1.0^{commit}").returncode == 0


def test_cli_plan_accepts_bump_without_version(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, _remote = make_project(tmp_path)

    result = main(["plan", "--bump", "minor", "--repo", str(repo)])

    assert result == 0
    output = capsys.readouterr().out
    assert "Release: 1.1.0 (v1.1.0)" in output
    assert "Bump:    minor from 1.0.0" in output


def test_bump_uses_version_from_merged_source_branch(tmp_path: Path) -> None:
    repo, _remote = make_project(tmp_path)
    config_path = repo / "gearu.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            'branch = "main"',
            'branch = "release"\nsource_branch = "main"',
        ),
        encoding="utf-8",
    )
    git(repo, "add", "gearu.toml")
    git(repo, "commit", "-m", "configure release branch")
    git(repo, "push", "origin", "main")
    git(repo, "branch", "release")
    git(repo, "push", "-u", "origin", "release")
    manifest = repo / "pyproject.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'version = "1.0.0"', 'version = "2.0.0"'
        ),
        encoding="utf-8",
    )
    git(repo, "add", "pyproject.toml")
    git(repo, "commit", "-m", "advance source version")
    git(repo, "push", "origin", "main")
    git(repo, "switch", "release")

    plan = manager(repo).plan(None, bump="minor")

    assert plan.version == "2.1.0"
    assert plan.bump_base == "2.0.0"
