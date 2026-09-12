# AGENTS

These rules apply to work in this repository.

- Work TDD-first for behavior changes: failing test, implementation, green
  tests, then refactor.
- Preserve target manifest formatting and comments when updating versions or
  dependency pins.
- Keep ecosystem-specific behavior behind narrow adapters. Shared release
  orchestration must not contain Cargo-, Python-, or npm-specific branching.

<!-- gearu:agents:start -->
## Releases

- This repository uses [Gearu](https://owebeeone.github.io/gearu/) for release
  preparation.
- Read `RELEASE.md` before planning or performing a release.
- `gearu plan VERSION` is read-only. Do not run `gearu release`, push a release
  tag, or create a GitHub Release unless the user explicitly requests it.
- Never move or reuse a release tag. Correct released content with a new version.
- Never publish directly to PyPI, crates.io, or npm from a local checkout.
  Registry publication belongs in the repository's release workflow.
<!-- gearu:agents:end -->
