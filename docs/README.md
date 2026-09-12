# Gearu

Gearu is a small, explicit release-preparation tool for Python, Rust, and npm
projects. It turns an intended version into a verified commit and immutable Git
tag, then can push that exact release and create its GitHub Release.

```sh
gearu plan 0.1.0
gearu release 0.1.0 --push --github-release
```

`plan` validates and reports without changing tracked files or remote state.
`release` works in a temporary candidate worktree, so failed checks do not
leave the normal checkout partly prepared.

Install reusable release guidance in a repository with:

```sh
gearu init
```

This idempotently manages a concise Gearu section in `AGENTS.md` and a complete
operator guide in `RELEASE.md`, while preserving project-specific content.

## Start Here

- [Configuration](Configuration.md) describes every `gearu.toml` setting.
- [Release Process](ReleaseProcess.md) covers preparation, publication, and
  recovery.
- [CLI Reference](CLI.md) is generated from Gearu's actual argument parser.

## Publication Boundary

Gearu prepares repositories and creates GitHub Releases. It never publishes
directly to PyPI, crates.io, or npm. Registry publication remains in each
project's reviewed GitHub Actions workflow, triggered by `release.published`.
