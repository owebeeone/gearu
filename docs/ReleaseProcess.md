# Release Process

Gearu prepares one repository release. The repository's GitHub Actions
workflow publishes artifacts or packages after a GitHub Release is published.

## Preconditions

- `gearu.toml` is committed and valid.
- The configured release branch is checked out and the working tree is clean.
- The configured remote has the release branch and any source branch.
- Project release checks work without interactive input.
- Any required dependency release tags already exist on their remotes.
- The target registry publish workflow listens for `release.published`.
- `gh` is installed and authenticated only when using `--github-release`.

## Prepare and Inspect

Choose the version explicitly. Gearu does not infer it from commits.

```sh
gearu plan 1.2.3
```

The plan verifies branch and remote state, tag immutability, dependency tags,
manifest values, and command configuration. It does not run release checks or
change tracked files, commits, tags, releases, or registry state.

## Create the Local Release

```sh
gearu release 1.2.3
```

Gearu creates a detached temporary worktree, optionally merges the source
branch, updates managed metadata and lockfiles, runs checks, commits the
candidate, and runs exact-commit checks. Only then does it fast-forward the
checked-out release branch and create the local tag.

If all versions are tag-derived and no source merge or managed file changes are
needed, the existing branch commit is tagged directly.

## Push and Publish the GitHub Release

The local step can be combined with the external steps:

```sh
gearu release 1.2.3 --push --github-release
```

`--push` atomically pushes the exact commit to the configured branch and the
immutable tag to the configured remote. `--github-release` requires `--push`
and creates the GitHub Release for that tag. Publishing the GitHub Release
starts the repository's release workflow.

Gearu never runs `cargo publish`, `npm publish`, or a Python package upload.
Those operations remain in reviewed CI workflows with registry-scoped
credentials or trusted publishing.

The same published stable release deploys the versioned documentation source
to GitHub Pages. Release candidates do not replace the stable documentation.
The Documentation workflow can also deploy an explicit Git ref manually.

## Release Candidates

Use a numbered release-candidate version:

```sh
gearu release 1.2.3-rc.1 --push --github-release
```

Gearu marks the GitHub Release as a prerelease. Python metadata uses the
normalized form `1.2.3rc1`.

## Retry and Recovery

A failed candidate check leaves the original checkout unchanged. Fix the
problem and run the same command again.

If local preparation succeeds but no push occurs, rerun with `--push`. Gearu
accepts an existing tag only when it still points to the release branch's exact
HEAD and the metadata and checks remain valid.

If the push succeeds but GitHub Release creation fails, rerun with both
`--push --github-release`. The exact push and GitHub Release creation are
idempotent.

Never move or reuse a release tag. If released contents must change, prepare a
new patch or release-candidate version. If only the publish workflow fails,
repair it and rerun the failed workflow for the same GitHub Release.

## Ordered Repository Releases

Release dependencies first, then consumers. Gearu verifies each configured
dependency tag against its remote before changing the consumer. This ordering
is deliberate but not transactional: separate Git repositories cannot be
pushed atomically as one release.
