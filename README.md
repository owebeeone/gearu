# Gearu

**Make repositories ready for release.**

Gearu is a small, explicit release-preparation tool for Python, Rust, and npm
projects. Its name comes from Old English *gearu*: ready, prepared, or equipped.

Gearu takes an intended version and makes the repository mechanically ready to
release:

```sh
gearu plan 0.1.0
gearu release 0.1.0
```

`plan` verifies and reports without changing tracked files or remote state.
`release` builds and tests a candidate in a temporary worktree, then creates the
local release commit and immutable tag. External actions are always explicit:

```sh
gearu release 0.1.0 --push
gearu release 0.1.0 --push --github-release
```

## Boundaries

Gearu is responsible for:

- verifying repository, branch, commit, remote tag, and dependency-tag state;
- updating versions, lockfiles, and configured dependency pins;
- running project-specific release checks;
- creating a release commit and immutable tag;
- atomically pushing the commit and tag to one repository; and
- creating the GitHub Release that starts that repository's publish workflow.

Gearu does not publish packages directly to PyPI, crates.io, or npm. Registry
credentials and publication remain in GitHub Actions, triggered by the
`release.published` event.

Cross-repository release trains are ordered and verified, but cannot be atomic:
Git only provides atomic pushes within a single remote.

## Install

Once the first release is published:

```sh
uv tool install gearu
```

For development:

```sh
uv sync
uv run python run_tests.py
```

## Configure

Add `gearu.toml` to the target repository:

```toml
[project]
name = "example"
branch = "main"
remote = "origin"
tag_prefix = "v"
github_repo = "owner/example"
# Optional for repositories that cut releases from a maintained release branch:
# source_branch = "main"

[python]
manifest = "pyproject.toml"
version = "static"

[release]
checks = [["python", "-m", "pytest", "-q"]]
```

Use `[python]` with `version = "scm"` for tag-derived versions. Rust projects
use `[rust]` with `manifests = ["Cargo.toml"]`; npm projects use `[npm]` with
`manifest = "package.json"`. Lockfile refresh commands are configurable and run
only when their ecosystem manifest changes.

Cross-repository release dependencies can verify a remote tag and update an
inline TOML pin:

```toml
[[dependencies]]
name = "example-core"
url = "https://github.com/owner/example-core"
tag = "{tag}"
pin_file = "Cargo.toml"
pin_key = "dependencies.example-core"
pin_field = "tag"
# Optional: prove Cargo.lock pins this package to the resolved tag commit.
lock_package = "example-core"
```

Override a same-version dependency deliberately with
`--dependency-tag example-core=v1.1.0`.

See [Configuration](docs/Configuration.md) for the complete schema and
[Release Process](docs/ReleaseProcess.md) for the end-to-end operator flow and
recovery rules.

## Release model

Gearu itself is published only by
[`.github/workflows/publish.yml`](.github/workflows/publish.yml) after a GitHub
Release is published. PyPI authentication uses Trusted Publishing; no PyPI API
token is stored in the repository.

## License

[MIT](LICENSE)
