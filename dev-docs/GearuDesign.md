# Gearu Design

## Purpose

Gearu turns an explicit release version or semantic-version bump selection into
a verified repository release. It coordinates common Git operations while
delegating manifest and lockfile work to narrow ecosystem adapters.

It is intentionally not a conventional-commit interpreter, package registry
client, build system, or deployment framework.

## Initial interface

```text
gearu init
gearu plan VERSION
gearu release VERSION
```

`init` installs marker-delimited release guidance in `AGENTS.md` and
`RELEASE.md`. It requires a Git repository but not `gearu.toml`, preserves
project-specific text, and produces no change when its managed sections are
already current.

`plan` is read-only. It resolves configuration, reads remote tags, checks
preconditions, and reports the exact files, commands, commit, tag, and remote
operations that `release` would perform.

With `--bump`, Gearu compares configured package versions and local and remote
release tags. It reads the remote refs directly rather than fetching them into
the local repository. Source-branch projects derive configured versions from
the merged candidate.

`release` executes that plan in a temporary detached worktree. A failed
candidate is removed without changing the user's checkout. The verified commit
is fast-forwarded into the configured local branch only after candidate and
exact-commit checks pass.

## Configuration

Each target repository contains `gearu.toml`. Shared orchestration reads common
repository and release settings. Ecosystem adapters own their specific manifest
paths, dependency pins, lockfile refresh commands, and validation gates.

When `project.source_branch` is configured, the source branch is merged into the
configured release branch inside the temporary candidate. The user must have the
release branch checked out, but a conflict cannot leave that checkout mid-merge.

The first adapters are:

- Rust: `Cargo.toml` and `Cargo.lock`;
- Python: `pyproject.toml` and supported lockfiles; and
- npm: `package.json` and supported lockfiles.

## Release stages

1. Validate the explicit version or bump selection and configuration.
2. Require a clean checkout on the configured release branch.
3. Fetch and validate upstream branch and tag state.
4. Verify required dependency releases and immutable tags.
5. Update manifests, dependency pins, and lockfiles.
6. Run configured checks against the resulting tree in a temporary worktree.
7. Create the release commit.
8. Re-run identity-sensitive checks against the exact commit.
9. Create the immutable tag.
10. Atomically push the exact commit to that repository's branch and tag.
11. Create the GitHub Release.

Registry publication is never a Gearu stage. The GitHub Release triggers the
target repository's separately reviewed publish workflow.

## Cross-repository trains

A release train may require matching versions across repositories, such as
`gwz-core`, `gwz-cli`, and `gwz-py`. Gearu must verify and sequence those
releases. It must not imply transactionality across remotes or attempt to move a
tag after a later repository fails.
