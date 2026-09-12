"""Command-line entry point for Gearu."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import load_config
from .errors import GearuError
from .models import ReleasePlan
from .release import ReleaseManager, ReleaseOptions


class _HelpFormatter(argparse.HelpFormatter):
    def __init__(self, prog: str) -> None:
        super().__init__(prog, max_help_position=24, width=88)


def _add_release_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "version", help="explicit release version, e.g. 1.2.3 or v1.2.3"
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="repository or a path inside it (default: current directory)",
    )
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


def _repository_root(start: Path) -> Path:
    resolved = start.resolve()
    candidates = (
        (resolved, *resolved.parents) if resolved.is_dir() else resolved.parents
    )
    for candidate in candidates:
        if (candidate / ".git").exists() and (candidate / "gearu.toml").is_file():
            return candidate
    raise GearuError(
        f"could not find a Git repository containing gearu.toml from {start}"
    )


def _print_plan(plan: ReleasePlan) -> None:
    print(f"Project: {plan.name}")
    print(f"Release: {plan.version} ({plan.tag})")
    print(f"Branch:  {plan.branch} at {plan.base_sha}")
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
        root = _repository_root(args.repo)
        manager = ReleaseManager(
            root, load_config(root), log=lambda message: print(f"gearu: {message}")
        )
        dependency_tags = _dependency_tags(args.dependency_tag)
        if args.command == "plan":
            _print_plan(manager.plan(args.version, dependency_tags=dependency_tags))
            return 0
        outcome = manager.release(
            args.version,
            ReleaseOptions(
                push=args.push,
                github_release=args.github_release,
                dependency_tags=dependency_tags,
            ),
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
