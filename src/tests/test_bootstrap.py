from __future__ import annotations

from pathlib import Path

import pytest

from gearu.bootstrap import initialize_release_docs
from gearu.errors import GearuError


def test_init_creates_release_guidance(tmp_path: Path) -> None:
    changed = initialize_release_docs(tmp_path)

    assert changed == (Path("AGENTS.md"), Path("RELEASE.md"))
    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    release = (tmp_path / "RELEASE.md").read_text(encoding="utf-8")
    assert agents.startswith("# AGENTS\n")
    assert "<!-- gearu:agents:start -->" in agents
    assert "Read `RELEASE.md`" in agents
    assert release.startswith("# Release Process\n")
    assert "<!-- gearu:release:start -->" in release
    assert "gearu plan VERSION" in release
    assert "https://owebeeone.github.io/gearu/" in release


def test_init_is_idempotent(tmp_path: Path) -> None:
    initialize_release_docs(tmp_path)
    agents = (tmp_path / "AGENTS.md").read_bytes()
    release = (tmp_path / "RELEASE.md").read_bytes()

    changed = initialize_release_docs(tmp_path)

    assert changed == ()
    assert (tmp_path / "AGENTS.md").read_bytes() == agents
    assert (tmp_path / "RELEASE.md").read_bytes() == release


def test_init_preserves_existing_repository_guidance(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text(
        "# AGENTS\n\nKeep this project rule.\n",
        encoding="utf-8",
    )
    (tmp_path / "RELEASE.md").write_text(
        "# Releases\n\nKeep this project-specific release step.\n",
        encoding="utf-8",
    )

    initialize_release_docs(tmp_path)

    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    release = (tmp_path / "RELEASE.md").read_text(encoding="utf-8")
    assert "Keep this project rule." in agents
    assert agents.count("<!-- gearu:agents:start -->") == 1
    assert "Keep this project-specific release step." in release
    assert release.count("<!-- gearu:release:start -->") == 1


def test_init_refuses_ambiguous_existing_gearu_guidance(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text(
        "# AGENTS\n\nUse Gearu with local rules.\n",
        encoding="utf-8",
    )

    with pytest.raises(GearuError, match="unmanaged Gearu guidance"):
        initialize_release_docs(tmp_path)

    assert not (tmp_path / "RELEASE.md").exists()


def test_init_refuses_reversed_managed_markers(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text(
        "# AGENTS\n\n<!-- gearu:agents:end -->\n<!-- gearu:agents:start -->\n",
        encoding="utf-8",
    )

    with pytest.raises(GearuError, match="malformed Gearu managed-section"):
        initialize_release_docs(tmp_path)

    assert not (tmp_path / "RELEASE.md").exists()
