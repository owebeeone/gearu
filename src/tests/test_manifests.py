from __future__ import annotations

import json
import tomllib
from pathlib import Path

from gearu.manifests import (
    replace_json_top_level_string,
    replace_toml_inline_string,
    replace_toml_string,
)


def test_replace_toml_string_preserves_surrounding_text(tmp_path: Path) -> None:
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(
        '# heading\n[project]\nname = "demo"\nversion = "1.0.0"  # release\n\n[tool.demo]\nversion = "keep"\n',
        encoding="utf-8",
    )

    changed = replace_toml_string(manifest, "project.version", "1.2.3")

    assert changed is True
    assert manifest.read_text(encoding="utf-8") == (
        '# heading\n[project]\nname = "demo"\nversion = "1.2.3"  # release\n\n[tool.demo]\nversion = "keep"\n'
    )
    assert (
        tomllib.loads(manifest.read_text(encoding="utf-8"))["project"]["version"]
        == "1.2.3"
    )


def test_replace_json_version_preserves_indentation_and_other_fields(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "package.json"
    manifest.write_text(
        '{\n  "name": "demo",\n  "version": "1.0.0",\n  "private": true\n}\n',
        encoding="utf-8",
    )

    changed = replace_json_top_level_string(manifest, "version", "1.2.3")

    assert changed is True
    assert manifest.read_text(encoding="utf-8") == (
        '{\n  "name": "demo",\n  "version": "1.2.3",\n  "private": true\n}\n'
    )
    assert json.loads(manifest.read_text(encoding="utf-8"))["version"] == "1.2.3"


def test_replace_inline_toml_dependency_tag(tmp_path: Path) -> None:
    manifest = tmp_path / "Cargo.toml"
    manifest.write_text(
        '[dependencies]\ngwz-core = { git = "https://example.test/core", tag = "v1.0.0" } # pin\n',
        encoding="utf-8",
    )

    changed = replace_toml_inline_string(
        manifest,
        key="dependencies.gwz-core",
        field="tag",
        value="v1.2.3",
    )

    assert changed is True
    assert manifest.read_text(encoding="utf-8") == (
        '[dependencies]\ngwz-core = { git = "https://example.test/core", tag = "v1.2.3" } # pin\n'
    )
