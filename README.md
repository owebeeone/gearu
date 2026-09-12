# Gearu

**Make repositories ready for release.**

Gearu is a small, explicit release-preparation tool for Python, Rust, and npm
projects. Its name comes from Old English *gearu*: ready, prepared, or equipped.

Gearu will take an intended version and make the repository mechanically ready
to release:

```sh
gearu plan 0.1.0
gearu release 0.1.0
```

The release engine is not implemented yet. This initial repository establishes
the package, command-line entry point, test layout, and trusted publication
path.

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
python -m pip install --editable .
python -m pip install pytest
python run_tests.py
```

## Current CLI

The bootstrap CLI exposes package metadata while the release engine is built:

```sh
gearu --help
gearu --version
```

## Release model

Gearu itself is published only by
[`.github/workflows/publish.yml`](.github/workflows/publish.yml) after a GitHub
Release is published. PyPI authentication uses Trusted Publishing; no PyPI API
token is stored in the repository.

## License

[MIT](LICENSE)

