from __future__ import annotations

import re

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


def test_dependency_tag_overrides_are_explicit() -> None:
    assert _dependency_tags(["core=v1.2.3", "cli=v1.1.0"]) == {
        "core": "v1.2.3",
        "cli": "v1.1.0",
    }
    with pytest.raises(GearuError):
        _dependency_tags(["v1.2.3"])
