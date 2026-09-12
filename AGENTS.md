# AGENTS

These rules apply to work in this repository.

- Work TDD-first for behavior changes: failing test, implementation, green
  tests, then refactor.
- Gearu receives an explicit release version. It does not infer release intent
  from commit messages.
- Gearu prepares and verifies releases; registry publication belongs to the
  target repository's GitHub Actions workflow.
- Never publish to PyPI, crates.io, or npm from a local checkout. Local package
  checks must use build, validation, or dry-run commands only.
- Treat commit, tag, push, and GitHub Release creation as separate stages with
  explicit preconditions. Never move or replace an existing release tag.
- Preserve target manifest formatting and comments when updating versions or
  dependency pins.
- Keep ecosystem-specific behavior behind narrow adapters. Shared release
  orchestration must not contain Cargo-, Python-, or npm-specific branching.

