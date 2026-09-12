"""Install managed Gearu release guidance in a repository."""

from __future__ import annotations

from pathlib import Path

from .errors import GearuError

AGENTS_START = "<!-- gearu:agents:start -->"
AGENTS_END = "<!-- gearu:agents:end -->"
RELEASE_START = "<!-- gearu:release:start -->"
RELEASE_END = "<!-- gearu:release:end -->"

AGENTS_BLOCK = f"""{AGENTS_START}
## Releases

- This repository uses [Gearu](https://owebeeone.github.io/gearu/) for release
  preparation.
- Read `RELEASE.md` before planning or performing a release.
- `gearu plan VERSION` and `gearu plan --bump LEVEL` are read-only. Do not run
  `gearu release`, push a release tag, or create a GitHub Release unless the
  user explicitly requests it.
- Never move or reuse a release tag. Correct released content with a new version.
- Never publish directly to PyPI, crates.io, or npm from a local checkout.
  Registry publication belongs in the repository's release workflow.
{AGENTS_END}"""

RELEASE_BLOCK = f"""{RELEASE_START}
## Gearu Release Process

Gearu prepares and verifies the repository, creates an immutable tag, and can
create the GitHub Release that starts this repository's publication workflow.
It does not publish directly to package registries.

Full documentation: <https://owebeeone.github.io/gearu/>

### Install

Install the released tool with:

```sh
uv tool install gearu
```

Upgrade an existing installation with:

```sh
uv tool upgrade gearu
```

To test the unreleased `main` branch, install it directly from its repository:

```sh
uv tool install git+https://github.com/owebeeone/gearu.git
```

Verify the installation with `gearu --version`.

### Preconditions

- Read `gearu.toml` and this repository's release workflow.
- Choose an explicit release version or an explicit major, minor, or patch bump.
  Gearu does not infer release intent from commits.
- Use a clean checkout on the branch configured by `project.branch`.
- Synchronize configured release and source branches with their remote.
- Release required cross-repository dependencies first.
- Install and authenticate `gh` before requesting GitHub Release creation.

### Plan

Always inspect the read-only plan first:

```sh
gearu plan VERSION
```

Or ask Gearu to select the next version:

```sh
gearu plan --bump patch
gearu plan --bump minor
gearu plan --bump major
```

Gearu compares configured package versions with valid local and remote release
tags, then bumps the highest version. It reads remote tags directly and does not
fetch or create local tags while planning.

For a release candidate, use a numbered version such as `1.2.3-rc.1`.

Override a configured dependency tag only when the release intentionally uses a
different version:

```sh
gearu plan VERSION --dependency-tag DEPENDENCY=TAG
```

### Prepare the Local Release

After reviewing the plan:

```sh
gearu release VERSION
```

The release command can select the version itself:

```sh
gearu release --bump minor
```

This recalculates the next version at release time. To lock the version reviewed
in a prior bump plan, pass that plan's reported `VERSION` explicitly.

Gearu builds and tests in a temporary worktree. Only a successful candidate is
applied to the local release branch and tagged. This step does not change a
remote repository.

### Push and Create the GitHub Release

Push the exact release commit and tag atomically:

```sh
gearu release VERSION --push
```

Create the GitHub Release after that push:

```sh
gearu release VERSION --push --github-release
```

The final command starts workflows listening for `release.published`, including
package publication and documentation deployment where configured.

### Recovery

- If candidate checks fail, fix the problem and rerun; the normal checkout is
  left unchanged.
- If local preparation succeeds, rerun the same version with `--push`.
- If the push succeeds but GitHub Release creation fails, rerun with
  `--push --github-release`.
- If released contents must change, use a new patch or release-candidate version.
  Never move or replace the existing tag.
- If only a publication workflow fails, repair and rerun that workflow for the
  same GitHub Release.
{RELEASE_END}"""


def _read(path: Path) -> str | None:
    try:
        return path.read_bytes().decode("utf-8")
    except FileNotFoundError:
        return None
    except UnicodeDecodeError as error:
        raise GearuError(f"{path} is not UTF-8 text") from error


def _render(
    path: Path,
    current: str | None,
    *,
    heading: str,
    start: str,
    end: str,
    block: str,
) -> str:
    newline = "\r\n" if current is not None and "\r\n" in current else "\n"
    rendered_block = block.replace("\n", newline)
    if current is None:
        return f"{heading}{newline}{newline}{rendered_block}{newline}"

    starts = current.count(start)
    ends = current.count(end)
    if starts == 1 and ends == 1:
        start_index = current.index(start)
        end_index = current.index(end)
        if end_index < start_index:
            raise GearuError(f"{path.name} has malformed Gearu managed-section markers")
        end_index += len(end)
        return current[:start_index] + rendered_block + current[end_index:]
    if starts or ends:
        raise GearuError(f"{path.name} has malformed Gearu managed-section markers")
    if "gearu" in current.lower():
        raise GearuError(
            f"{path.name} contains unmanaged Gearu guidance; reconcile it before init"
        )

    prefix = current.rstrip("\r\n")
    separator = f"{newline}{newline}" if prefix else ""
    return f"{prefix}{separator}{rendered_block}{newline}"


def initialize_release_docs(root: Path) -> tuple[Path, ...]:
    specifications = (
        (
            Path("AGENTS.md"),
            "# AGENTS",
            AGENTS_START,
            AGENTS_END,
            AGENTS_BLOCK,
        ),
        (
            Path("RELEASE.md"),
            "# Release Process",
            RELEASE_START,
            RELEASE_END,
            RELEASE_BLOCK,
        ),
    )
    updates: list[tuple[Path, str | None, str]] = []
    for relative, heading, start, end, block in specifications:
        path = root / relative
        current = _read(path)
        updated = _render(
            path,
            current,
            heading=heading,
            start=start,
            end=end,
            block=block,
        )
        updates.append((relative, current, updated))

    changed: list[Path] = []
    for relative, current, updated in updates:
        if current == updated:
            continue
        (root / relative).write_text(updated, encoding="utf-8", newline="")
        changed.append(relative)
    return tuple(changed)
