"""Exact-ref Git operations used by the release transaction."""

from __future__ import annotations

from pathlib import Path

from .errors import GearuError
from .process import Runner


class GitRepository:
    def __init__(self, root: Path, runner: Runner) -> None:
        self.root = root.resolve()
        self.runner = runner
        if not (self.root / ".git").exists():
            raise GearuError(f"not a Git repository: {self.root}")

    def _run(
        self,
        args: list[object],
        *,
        cwd: Path | None = None,
        check: bool = True,
    ):
        return self.runner.run(
            ["git", "-C", cwd or self.root, *args],
            cwd=self.root,
            capture=True,
            check=check,
        )

    def output(self, args: list[object], *, cwd: Path | None = None) -> str:
        return self._run(args, cwd=cwd).stdout.strip()

    def current_branch(self) -> str:
        branch = self.output(["branch", "--show-current"])
        if not branch:
            raise GearuError("detached HEAD; switch to the configured release branch")
        return branch

    def head(self, *, cwd: Path | None = None) -> str:
        return self.output(["rev-parse", "HEAD"], cwd=cwd)

    def branch_commit(self, branch: str) -> str:
        result = self._run(
            ["rev-parse", "--verify", f"refs/heads/{branch}"], check=False
        )
        if result.returncode != 0:
            raise GearuError(f"local branch {branch!r} does not exist")
        return result.stdout.strip()

    def require_clean(self, *, cwd: Path | None = None) -> None:
        status = self.output(
            ["status", "--porcelain", "--untracked-files=all"], cwd=cwd
        )
        if status:
            raise GearuError(f"working tree is not clean:\n{status}")

    def local_tag_commit(self, tag: str) -> str | None:
        result = self._run(
            ["rev-parse", "-q", "--verify", f"refs/tags/{tag}^{{commit}}"],
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else None

    def remote_branch_commit(self, remote: str, branch: str) -> str | None:
        result = self._run(["ls-remote", remote, f"refs/heads/{branch}"])
        rows = [row.split() for row in result.stdout.splitlines() if row.strip()]
        return rows[0][0] if rows else None

    def remote_tag_commit(self, remote: str, tag: str) -> str | None:
        return self.remote_tag_commit_at(remote, tag)

    def remote_tag_commit_at(self, url: str, tag: str) -> str | None:
        ref = f"refs/tags/{tag}"
        result = self._run(["ls-remote", "--tags", url, ref, f"{ref}^{{}}"])
        refs = {
            name: sha
            for sha, name in (
                row.split() for row in result.stdout.splitlines() if row.strip()
            )
        }
        return refs.get(f"{ref}^{{}}", refs.get(ref))

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        result = self._run(
            ["merge-base", "--is-ancestor", ancestor, descendant],
            check=False,
        )
        return result.returncode == 0

    def add_worktree(self, path: Path, sha: str) -> None:
        self._run(["worktree", "add", "--detach", path, sha])

    def merge_without_commit(self, *, cwd: Path, source: str) -> None:
        result = self._run(
            ["merge", "--no-ff", "--no-commit", source],
            cwd=cwd,
            check=False,
        )
        if result.returncode != 0:
            conflicts = self.output(
                ["diff", "--name-only", "--diff-filter=U"],
                cwd=cwd,
            )
            detail = f"\nConflicts:\n{conflicts}" if conflicts else ""
            raise GearuError(
                f"could not merge source branch into release candidate{detail}"
            )

    def remove_worktree(self, path: Path) -> None:
        result = self._run(["worktree", "remove", "--force", path], check=False)
        self._run(["worktree", "prune"], check=False)
        if result.returncode != 0 and path.exists():
            raise GearuError(f"could not remove temporary Git worktree {path}")

    def changed_paths(self, *, cwd: Path) -> set[Path]:
        output = self._run(
            ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
            cwd=cwd,
        ).stdout
        records = output.split("\0")
        paths: set[Path] = set()
        index = 0
        while index < len(records):
            record = records[index]
            index += 1
            if not record:
                continue
            if len(record) < 4:
                raise GearuError("could not parse Git status output")
            status = record[:2]
            paths.add(Path(record[3:]))
            if "R" in status or "C" in status:
                index += 1
        return paths

    def commit(self, *, cwd: Path, paths: set[Path], message: str) -> str:
        ordered = sorted(path.as_posix() for path in paths)
        self._run(["add", "--", *ordered], cwd=cwd)
        staged = self.output(["diff", "--cached", "--name-only"], cwd=cwd)
        if not staged:
            raise GearuError("release changes disappeared before commit")
        self._run(["commit", "-m", message], cwd=cwd)
        return self.head(cwd=cwd)

    def fast_forward_branch(
        self, branch: str, target: str, *, expected_head: str
    ) -> None:
        if self.current_branch() != branch:
            raise GearuError(
                f"checkout left configured branch {branch!r} during release"
            )
        if self.head() != expected_head:
            raise GearuError(
                "release branch changed while the candidate was being verified"
            )
        if target != expected_head:
            self._run(["merge", "--ff-only", target])

    def ensure_tag(self, tag: str, target: str) -> bool:
        existing = self.local_tag_commit(tag)
        if existing is not None:
            if existing != target:
                raise GearuError(
                    f"tag {tag} already exists at {existing[:12]}, not {target[:12]}; "
                    "refusing to move a release tag"
                )
            return False
        self._run(["tag", tag, target])
        return True

    def push_release(self, *, remote: str, branch: str, tag: str, target: str) -> None:
        result = self._run(
            [
                "push",
                "--atomic",
                remote,
                f"{target}:refs/heads/{branch}",
                f"{target}:refs/tags/{tag}",
            ],
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip()
            suffix = f"\n{detail}" if detail else ""
            raise GearuError(
                f"atomic push of {branch} and {tag} failed; the remote was left unchanged{suffix}"
            )
