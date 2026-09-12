from __future__ import annotations

import json
import tomllib
from pathlib import Path

from gearu.adapters.npm import NpmAdapter
from gearu.adapters.rust import RustAdapter
from gearu.models import NpmConfig, RustConfig, RustManifestConfig
from gearu.version import ReleaseVersion


def test_rust_adapter_updates_package_and_workspace_versions(tmp_path: Path) -> None:
    package = tmp_path / "crate" / "Cargo.toml"
    workspace = tmp_path / "Cargo.toml"
    package.parent.mkdir()
    package.write_text(
        '[package]\nname = "demo"\nversion = "1.0.0"\n', encoding="utf-8"
    )
    workspace.write_text('[workspace.package]\nversion = "1.0.0"\n', encoding="utf-8")
    adapter = RustAdapter(
        tmp_path,
        RustConfig(
            manifests=(
                RustManifestConfig(Path("Cargo.toml")),
                RustManifestConfig(Path("crate/Cargo.toml")),
            )
        ),
    )
    version = ReleaseVersion.parse("1.2.3", tag_prefix="v")

    assert len(adapter.plan(version)) == 2
    assert adapter.apply(version) == {Path("Cargo.toml"), Path("crate/Cargo.toml")}
    adapter.validate(version)
    assert (
        tomllib.loads(workspace.read_text())["workspace"]["package"]["version"]
        == "1.2.3"
    )
    assert tomllib.loads(package.read_text())["package"]["version"] == "1.2.3"


def test_npm_adapter_updates_only_top_level_version(tmp_path: Path) -> None:
    manifest = tmp_path / "package.json"
    manifest.write_text(
        '{\n  "name": "demo",\n  "version": "1.0.0",\n  "config": {"version": "keep"}\n}\n',
        encoding="utf-8",
    )
    adapter = NpmAdapter(tmp_path, NpmConfig())
    version = ReleaseVersion.parse("1.2.3", tag_prefix="v")

    assert len(adapter.plan(version)) == 1
    assert adapter.apply(version) == {Path("package.json")}
    adapter.validate(version)
    data = json.loads(manifest.read_text())
    assert data["version"] == "1.2.3"
    assert data["config"]["version"] == "keep"
