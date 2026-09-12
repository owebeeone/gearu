"""Command-line entry point for Gearu."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .bootstrap import initialize_release_docs
from .config import load_config
from .errors import GearuError
from .models import ReleasePlan
from .release import ReleaseManager, ReleaseOptions


class _HelpFormatter(argparse.HelpFormatter):
    def __init__(self, prog: str) -> None:
        super().__init__(prog, max_help_position=24, width=88)


def _add_repo_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="repository or a path inside it (default: current directory)",
    )


def _add_release_arguments(parser: argparse.ArgumentParser) -> None:
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "version",
        nargs="?",
        help="explicit release version, e.g. 1.2.3 or v1.2.3",
    )
    selection.add_argument(
        "--bump",
        choices=("major", "minor", "patch"),
        help="select the next version from configured versions and release tags",
    )
    _add_repo_argument(parser)
    parser.add_argument(
        "--dependency-tag",
        action="append",
        default=[],
        metavar="NAME=TAG",
        help="override one configured dependency tag; repeat as needed",
    )


def _dependency_tags(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        name, separator, tag = value.partition("=")
        if not separator or not name or not tag:
            raise GearuError(f"dependency tag override must be NAME=TAG, got {value!r}")
        if name in parsed:
            raise GearuError(
                f"dependency tag override {name!r} was provided more than once"
            )
        parsed[name] = tag
    return parsed


def _git_repository_root(start: Path) -> Path:
    resolved = start.resolve()
    candidates = (
        (resolved, *resolved.parents) if resolved.is_dir() else resolved.parents
    )
    for candidate in candidates:
        if (candidate / ".git").exists():
            return candidate
    raise GearuError(f"could not find a Git repository from {start}")


def _repository_root(start: Path) -> Path:
    root = _git_repository_root(start)
    if not (root / "gearu.toml").is_file():
        raise GearuError(f"no gearu.toml found at {root / 'gearu.toml'}")
    return root


def _print_plan(plan: ReleasePlan) -> None:
    print(f"Project: {plan.name}")
    print(f"Release: {plan.version} ({plan.tag})")
    print(f"Branch:  {plan.branch} at {plan.base_sha}")
    if plan.bump is not None and plan.bump_base is not None:
        print(f"Bump:    {plan.bump} from {plan.bump_base}")
    if plan.source_branch is not None and plan.source_sha is not None:
        print(f"Merge:   {plan.source_branch} at {plan.source_sha}")
    if plan.already_tagged:
        print("State:   tag already exists at branch HEAD")
    print("Changes:")
    if plan.changes:
        for change in plan.changes:
            print(
                f"  {change.path}: {change.current} -> {change.target} "
                f"({change.reason})"
            )
    else:
        print("  none; version is tag-derived or metadata is already current")
    print("Dependencies:")
    if plan.dependencies:
        for dependency in plan.dependencies:
            print(f"  {dependency.name} {dependency.tag} at {dependency.sha[:12]}")
    else:
        print("  none")
    print("Checks:")
    if plan.checks:
        for command in plan.checks:
            print("  " + " ".join(command.argv))
    else:
        print("  none configured")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gearu",
        description="Make repositories ready for release.",
        epilog="Project: https://github.com/owebeeone/gearu",
        formatter_class=_HelpFormatter,
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    commands = parser.add_subparsers(dest="command")

    init = commands.add_parser(
        "init",
        help="install or update repository release guidance",
        formatter_class=_HelpFormatter,
    )
    _add_repo_argument(init)

    plan = commands.add_parser(
        "plan",
        help="validate and display a release plan",
        formatter_class=_HelpFormatter,
    )
    _add_release_arguments(plan)

    release = commands.add_parser(
        "release",
        help="prepare, verify, commit, and tag a release",
        formatter_class=_HelpFormatter,
    )
    _add_release_arguments(release)
    release.add_argument(
        "--push",
        action="store_true",
        help="atomically push the exact branch commit and tag",
    )
    release.add_argument(
        "--github-release",
        action="store_true",
        help="create the GitHub Release after pushing the tag (requires --push)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        if args.command == "init":
            root = _git_repository_root(args.repo)
            existing = {
                path
                for path in (Path("AGENTS.md"), Path("RELEASE.md"))
                if (root / path).is_file()
            }
            changed = set(initialize_release_docs(root))
            for path in (Path("AGENTS.md"), Path("RELEASE.md")):
                if path not in changed:
                    state = "already current"
                else:
                    state = "updated" if path in existing else "created"
                print(f"gearu: {state} {path}")
            return 0
        root = _repository_root(args.repo)
        manager = ReleaseManager(
            root, load_config(root), log=lambda message: print(f"gearu: {message}")
        )
        dependency_tags = _dependency_tags(args.dependency_tag)
        if args.command == "plan":
            _print_plan(
                manager.plan(
                    args.version,
                    bump=args.bump,
                    dependency_tags=dependency_tags,
                )
            )
            return 0
        outcome = manager.release(
            args.version,
            ReleaseOptions(
                push=args.push,
                github_release=args.github_release,
                dependency_tags=dependency_tags,
            ),
            bump=args.bump,
        )
        print(f"gearu: {outcome.tag} -> {outcome.target_sha[:12]}")
        if not args.push:
            print(
                "gearu: release is local; rerun with --push to publish the branch and tag"
            )
        return 0
    except GearuError as error:
        print(f"gearu: error: {error}", file=sys.stderr)
        return 1
