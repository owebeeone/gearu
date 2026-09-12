from __future__ import annotations

import re
import subprocess

import pytest

from gearu.cli import _dependency_tags, main
from gearu.errors import GearuError


def test_no_arguments_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    output = capsys.readouterr().out
    assert "Make repositories ready for release." in output
    assert "https://github.com/owebeeone/gearu" in output


def test_help_exits_successfully(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as outcome:
        main(["--help"])

    assert outcome.value.code == 0
    assert "usage: gearu" in capsys.readouterr().out


def test_version_reports_a_pep440_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as outcome:
        main(["--version"])

    assert outcome.value.code == 0
    output = capsys.readouterr().out.strip()
    assert re.fullmatch(r"gearu [0-9]+(?:\.[0-9]+)+(?:[^ ]*)?", output)


def test_help_lists_release_commands(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    output = capsys.readouterr().out
    assert "plan" in output
    assert "release" in output
    assert "init" in output


def test_dependency_tag_overrides_are_explicit() -> None:
    assert _dependency_tags(["core=v1.2.3", "cli=v1.1.0"]) == {
        "core": "v1.2.3",
        "cli": "v1.1.0",
    }
    with pytest.raises(GearuError):
        _dependency_tags(["v1.2.3"])


def test_init_bootstraps_git_repository_without_config(
    tmp_path, capsys: pytest.CaptureFixture[str]
) -> None:
    subprocess.run(
        ["git", "init", "-b", "main", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert main(["init", "--repo", str(tmp_path)]) == 0
    assert (tmp_path / "AGENTS.md").is_file()
    assert (tmp_path / "RELEASE.md").is_file()
    assert "created AGENTS.md" in capsys.readouterr().out


@pytest.mark.parametrize(
    "arguments",
    [
        ["plan"],
        ["plan", "1.2.3", "--bump", "minor"],
        ["release"],
        ["release", "1.2.3", "--bump", "patch"],
    ],
)
def test_release_commands_require_exactly_one_version_selection(
    arguments: list[str],
) -> None:
    with pytest.raises(SystemExit) as outcome:
        main(arguments)

    assert outcome.value.code == 2
