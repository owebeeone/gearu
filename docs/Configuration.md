# Gearu Configuration

Each repository managed by Gearu has a `gearu.toml` at its root. Paths are
relative to that root. Commands are arrays of arguments and are run directly,
without a shell.

## Project

```toml
[project]
name = "example"
branch = "main"                 # default: main
remote = "origin"               # default: origin
tag_prefix = "v"                # default: v; may be empty
github_repo = "owner/example"   # required by --github-release
source_branch = "main"          # optional branch merged into branch
```

`source_branch` supports repositories that maintain a separate release branch.
Run Gearu while the configured `branch` is checked out. The source branch is
merged only in the temporary release candidate.

## Release Checks

```toml
[release]
checks = [
  ["cargo", "test", "--locked"],
  ["cargo", "publish", "--dry-run"],
]
exact_checks = [["cargo", "test", "--locked"]]
managed_files = ["docs/CLI.md"]
commit_message = "chore(release): {name} {version}"
github_notes = "{name} {tag}."
```

At least one `checks` command is required. `exact_checks` defaults to `checks`
and runs after the candidate commit is created. A check may update only files
owned by an ecosystem adapter or listed in `managed_files`; any other change
stops the release.

Direct registry publication commands are rejected. Dry runs are allowed.
Registry publication belongs in the repository's GitHub Actions workflow.

These template fields are available in commands, dependency tags, commit
messages, and GitHub release notes:

- `{name}`: configured project name
- `{version}`: release version such as `1.2.3-rc.1`
- `{python_version}`: Python-normalized version such as `1.2.3rc1`
- `{tag}`: full Git tag such as `v1.2.3-rc.1`
- `{repo}`: absolute repository path

Use doubled braces, `{{` and `}}`, when a literal brace is needed.

## Python

For a static version in `pyproject.toml`:

```toml
[python]
manifest = "pyproject.toml"       # default
version = "static"                # default
version_key = "project.version"   # default
lockfiles = ["uv.lock"]
lock_command = ["uv", "lock"]
```

For a version derived from Git tags with `setuptools-scm`:

```toml
[python]
version = "scm"
```

SCM mode requires `version` in `project.dynamic` and does not edit the
manifest. Release candidates use the Python form `1.2.3rc1` for static
versions.

## Rust

```toml
[rust]
manifests = ["Cargo.toml"]
lockfile = "Cargo.lock"
lock_command = ["cargo", "generate-lockfile"]
```

The default manifest is `Cargo.toml`. Gearu finds either `package.version` or
`workspace.package.version`. Specify a key when a manifest is ambiguous:

```toml
[rust]
manifests = [
  { path = "Cargo.toml", key = "workspace.package.version" },
  { path = "crates/cli/Cargo.toml", key = "package.version" },
]
lockfile = "Cargo.lock"
```

When `lockfile` is configured and `lock_command` is omitted, Gearu runs
`cargo generate-lockfile` after a configured Cargo manifest changes.

## npm

```toml
[npm]
manifest = "package.json"         # default
lockfile = "package-lock.json"
lock_command = [
  "npm", "install", "--package-lock-only", "--ignore-scripts",
]
```

Gearu updates the top-level `version`. The shown lock command is the default
when `lockfile` is configured.

## Release Dependencies

Gearu can require a tag in another Git repository and update a TOML inline
table to use it:

```toml
[[dependencies]]
name = "example-core"
url = "https://github.com/owner/example-core"
tag = "{tag}"                       # default
pin_file = "Cargo.toml"
pin_key = "dependencies.example-core"
pin_field = "tag"
lock_package = "example-core"       # optional Cargo.lock verification
```

`pin_file`, `pin_key`, and `pin_field` must be specified together. If the
inline table has a `git` field, its URL must match `url`.

`lock_package` requires `[rust].lockfile`. It verifies that `Cargo.lock`
records the named package as a Git source using the resolved tag and the exact
remote commit behind that tag. This catches stale locks and accidental local
workspace or path resolution.

Override one dependency tag for a release with:

```sh
gearu plan 1.2.3 --dependency-tag example-core=v1.2.2
```
