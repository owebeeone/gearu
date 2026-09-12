"""Plan and execute verified repository releases."""

from __future__ import annotations

import re
import shutil
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from .adapters import build_adapters
from .config import load_config
from .dependency_checks import validate_dependency_locks
from .errors import GearuError
from .git import GitRepository
from .github import GitHubReleases
from .manifests import replace_toml_inline_string, toml_value
from .models import (
    CommandSpec,
    DependencyConfig,
    DependencyResolution,
    FileChange,
    GearuConfig,
    ReleaseOptions,
    ReleaseOutcome,
    ReleasePlan,
)
from .process import Runner
from .version import BumpLevel, ReleaseVersion, select_bumped_version

__all__ = ["ReleaseManager", "ReleaseOptions", "ReleaseOutcome", "ReleasePlan"]


class ReleaseManager:
    def __init__(
        self,
        root: Path,
        config: GearuConfig | None = None,
        *,
        log: Callable[[str], None] = print,
    ) -> None:
        self.root = root.resolve()
        self.config = config or load_config(self.root)
        self.log = log
        self.runner = Runner(log)
        self.git = GitRepository(self.root, self.runner)

    def _version(self, value: str) -> ReleaseVersion:
        return ReleaseVersion.parse(value, tag_prefix=self.config.project.tag_prefix)

    def _select_version(
        self,
        value: str | None,
        bump: BumpLevel | None,
    ) -> tuple[ReleaseVersion, str | None]:
        if (value is None) == (bump is None):
            raise GearuError("provide exactly one of VERSION or --bump")
        if value is not None:
            return self._version(value), None

        assert bump is not None
        if self.config.project.source_branch is not None:
            source_sha = self.git.branch_commit(self.config.project.source_branch)
            with self._candidate(
                self.git.head(),
                "bump-selection",
                source_sha,
            ) as candidate:
                candidate_config = load_config(candidate)
                configured_versions = tuple(
                    current
                    for adapter in build_adapters(candidate, candidate_config)
                    for current in adapter.current_versions()
                )
        else:
            configured_versions = tuple(
                current
                for adapter in build_adapters(self.root, self.config)
                for current in adapter.current_versions()
            )
        tags = tuple(
            sorted(
                set(self.git.local_tags()).union(
                    self.git.remote_tags(self.config.project.remote)
                )
            )
        )
        selection = select_bumped_version(
            bump=bump,
            tag_prefix=self.config.project.tag_prefix,
            tags=tags,
            configured_versions=configured_versions,
        )
        return selection.version, selection.base_version

    def _values(self, version: ReleaseVersion) -> dict[str, str]:
        return {
            "name": self.config.project.name,
            "version": version.text,
            "python_version": version.python_text,
            "tag": version.tag,
            "repo": str(self.root),
        }

    def _dependency_tag(
        self,
        dependency: DependencyConfig,
        version: ReleaseVersion,
        overrides: dict[str, str],
    ) -> str:
        if dependency.name in overrides:
            tag = overrides[dependency.name]
        else:
            try:
                tag = dependency.tag_template.format_map(self._values(version))
            except (KeyError, ValueError) as error:
                raise GearuError(
                    f"invalid tag template for dependency {dependency.name!r}: {error}"
                ) from error
        if not tag or re.search(r"\s", tag):
            raise GearuError(
                f"dependency {dependency.name!r} resolved to invalid tag {tag!r}"
            )
        return tag

    def _resolve_dependencies(
        self,
        version: ReleaseVersion,
        overrides: dict[str, str],
        config: GearuConfig,
    ) -> tuple[DependencyResolution, ...]:
        configured = {dependency.name for dependency in config.dependencies}
        unknown = sorted(set(overrides).difference(configured))
        if unknown:
            raise GearuError("unknown dependency tag overrides: " + ", ".join(unknown))
        resolutions: list[DependencyResolution] = []
        for dependency in config.dependencies:
            tag = self._dependency_tag(dependency, version, overrides)
            sha = self.git.remote_tag_commit_at(dependency.url, tag)
            if sha is None:
                raise GearuError(
                    f"dependency {dependency.name} tag {tag} was not found at {dependency.url}"
                )
            resolutions.append(
                DependencyResolution(dependency.name, dependency.url, tag, sha)
            )
        return tuple(resolutions)

    def _dependency_changes(
        self,
        root: Path,
        resolutions: tuple[DependencyResolution, ...],
        config: GearuConfig,
    ) -> tuple[FileChange, ...]:
        by_name = {resolution.name: resolution for resolution in resolutions}
        changes: list[FileChange] = []
        for dependency in config.dependencies:
            if dependency.pin_file is None:
                continue
            assert dependency.pin_key is not None
            assert dependency.pin_field is not None
            value = toml_value(root / dependency.pin_file, dependency.pin_key)
            if not isinstance(value, dict) or not isinstance(
                value.get(dependency.pin_field), str
            ):
                raise GearuError(
                    f"{dependency.pin_file} has no string field "
                    f"{dependency.pin_key}.{dependency.pin_field}"
                )
            configured_url = value.get("git")
            if configured_url is not None and configured_url != dependency.url:
                raise GearuError(
                    f"{dependency.pin_file} configures {dependency.name} from "
                    f"{configured_url!r}, but gearu.toml uses {dependency.url!r}"
                )
            current = value[dependency.pin_field]
            target = by_name[dependency.name].tag
            if current != target:
                changes.append(
                    FileChange(
                        dependency.pin_file,
                        current,
                        target,
                        f"{dependency.name} dependency tag",
                    )
                )
        return tuple(changes)

    def _apply_dependency_pins(
        self,
        root: Path,
        resolutions: tuple[DependencyResolution, ...],
        config: GearuConfig,
    ) -> set[Path]:
        by_name = {resolution.name: resolution for resolution in resolutions}
        changed: set[Path] = set()
        for dependency in config.dependencies:
            if dependency.pin_file is None:
                continue
            assert dependency.pin_key is not None
            assert dependency.pin_field is not None
            if replace_toml_inline_string(
                root / dependency.pin_file,
                key=dependency.pin_key,
                field=dependency.pin_field,
                value=by_name[dependency.name].tag,
            ):
                changed.add(dependency.pin_file)
        return changed

    def _check_repository_state(
        self, version: ReleaseVersion
    ) -> tuple[str, bool, str | None]:
        project = self.config.project
        self.git.require_clean()
        branch = self.git.current_branch()
        if branch != project.branch:
            raise GearuError(
                f"on branch {branch!r}, but releases are cut from {project.branch!r}"
            )
        head = self.git.head()
        local_tag = self.git.local_tag_commit(version.tag)
        if local_tag is not None and local_tag != head:
            raise GearuError(
                f"tag {version.tag} already exists at {local_tag[:12]}, not branch HEAD "
                f"{head[:12]}; refusing to move a release tag"
            )
        remote_branch = self.git.remote_branch_commit(project.remote, project.branch)
        if remote_branch is None:
            raise GearuError(
                f"remote {project.remote!r} has no branch {project.branch!r}; push it first"
            )
        if remote_branch != head and not self.git.is_ancestor(remote_branch, head):
            raise GearuError(
                f"local {project.branch} is behind or diverged from {project.remote}/"
                f"{project.branch}; synchronize it before releasing"
            )
        remote_tag = self.git.remote_tag_commit(project.remote, version.tag)
        if remote_tag is not None and remote_tag != head:
            raise GearuError(
                f"remote tag {version.tag} points at {remote_tag[:12]}, not branch HEAD "
                f"{head[:12]}; refusing to move a release tag"
            )
        already_tagged = local_tag is not None or remote_tag is not None
        source_sha: str | None = None
        if project.source_branch is not None and not already_tagged:
            source_sha = self.git.branch_commit(project.source_branch)
            remote_source = self.git.remote_branch_commit(
                project.remote, project.source_branch
            )
            if remote_source is None:
                raise GearuError(
                    f"remote {project.remote!r} has no source branch "
                    f"{project.source_branch!r}"
                )
            if remote_source != source_sha and not self.git.is_ancestor(
                remote_source, source_sha
            ):
                raise GearuError(
                    f"local source branch {project.source_branch} is behind or diverged "
                    f"from {project.remote}/{project.source_branch}"
                )
        return head, already_tagged, source_sha

    def plan(
        self,
        value: str | None = None,
        *,
        bump: BumpLevel | None = None,
        dependency_tags: dict[str, str] | None = None,
    ) -> ReleasePlan:
        version, bump_base = self._select_version(value, bump)
        base_sha, already_tagged, source_sha = self._check_repository_state(version)
        if source_sha is not None:
            with self._candidate(base_sha, version.tag, source_sha) as candidate:
                candidate_config = load_config(candidate)
                dependencies = self._resolve_dependencies(
                    version, dependency_tags or {}, candidate_config
                )
                adapters = build_adapters(candidate, candidate_config)
                changes = [
                    change for adapter in adapters for change in adapter.plan(version)
                ]
                changes.extend(
                    self._dependency_changes(candidate, dependencies, candidate_config)
                )
                checks = candidate_config.release.checks
        else:
            dependencies = self._resolve_dependencies(
                version, dependency_tags or {}, self.config
            )
            adapters = build_adapters(self.root, self.config)
            changes = [
                change for adapter in adapters for change in adapter.plan(version)
            ]
            changes.extend(
                self._dependency_changes(self.root, dependencies, self.config)
            )
            checks = self.config.release.checks
        if already_tagged and changes:
            descriptions = ", ".join(change.path.as_posix() for change in changes)
            raise GearuError(
                f"tag {version.tag} already exists at HEAD but release metadata differs: "
                f"{descriptions}"
            )
        return ReleasePlan(
            name=self.config.project.name,
            version=version.text,
            tag=version.tag,
            branch=self.config.project.branch,
            base_sha=base_sha,
            changes=tuple(changes),
            dependencies=dependencies,
            checks=checks,
            already_tagged=already_tagged,
            source_branch=self.config.project.source_branch
            if source_sha is not None
            else None,
            source_sha=source_sha,
            bump=bump,
            bump_base=bump_base,
        )

    @contextmanager
    def _candidate(
        self, sha: str, tag: str, source_sha: str | None = None
    ) -> Iterator[Path]:
        temp_root = Path(tempfile.mkdtemp(prefix=f"gearu-{tag}-"))
        worktree = temp_root / "candidate"
        self.git.add_worktree(worktree, sha)
        try:
            if source_sha is not None and not self.git.is_ancestor(source_sha, sha):
                self.git.merge_without_commit(cwd=worktree, source=source_sha)
            yield worktree
        finally:
            try:
                self.git.remove_worktree(worktree)
            finally:
                shutil.rmtree(temp_root, ignore_errors=True)

    def _run_commands(
        self,
        commands: tuple[CommandSpec, ...],
        *,
        root: Path,
        values: dict[str, str],
    ) -> None:
        for command in commands:
            self.runner.run(command.expanded(values), cwd=root)

    def _managed_files(self, root: Path, config: GearuConfig) -> set[Path]:
        files = set(config.release.managed_files)
        for adapter in build_adapters(root, config):
            files.update(adapter.managed_files())
        files.update(
            dependency.pin_file
            for dependency in config.dependencies
            if dependency.pin_file is not None
        )
        return files

    def _prepare_candidate(
        self,
        root: Path,
        version: ReleaseVersion,
        resolutions: tuple[DependencyResolution, ...],
        preapproved_changes: set[Path] | None = None,
    ) -> tuple[str, bool]:
        config = load_config(root)
        adapters = build_adapters(root, config)
        touched: set[Path] = set()
        for adapter in adapters:
            touched.update(adapter.apply(version))
        touched.update(self._apply_dependency_pins(root, resolutions, config))
        for adapter in adapters:
            for command in adapter.refresh_commands(touched):
                self.runner.run(command.expanded(self._values(version)), cwd=root)
        for adapter in adapters:
            adapter.validate(version)
        validate_dependency_locks(root, config, resolutions)
        self._run_commands(
            config.release.checks,
            root=root,
            values=self._values(version),
        )

        changed = self.git.changed_paths(cwd=root)
        allowed = self._managed_files(root, config)
        allowed.update(preapproved_changes or set())
        unexpected = sorted(path.as_posix() for path in changed.difference(allowed))
        if unexpected:
            raise GearuError(
                "release commands changed files not declared as managed:\n  "
                + "\n  ".join(unexpected)
            )
        created_commit = bool(changed)
        target = self.git.head(cwd=root)
        if changed:
            message = config.release.commit_message.format_map(self._values(version))
            target = self.git.commit(cwd=root, paths=changed, message=message)

        self._run_commands(
            config.release.exact_checks,
            root=root,
            values=self._values(version),
        )
        self.git.require_clean(cwd=root)
        for adapter in adapters:
            adapter.validate(version)
        validate_dependency_locks(root, config, resolutions)
        return target, created_commit

    def _verify_existing_release(
        self,
        root: Path,
        version: ReleaseVersion,
        resolutions: tuple[DependencyResolution, ...],
    ) -> None:
        config = load_config(root)
        adapters = build_adapters(root, config)
        for adapter in adapters:
            adapter.validate(version)
        validate_dependency_locks(root, config, resolutions)
        self._run_commands(
            config.release.exact_checks,
            root=root,
            values=self._values(version),
        )
        self.git.require_clean(cwd=root)

    def release(
        self,
        value: str | None = None,
        options: ReleaseOptions | None = None,
        *,
        bump: BumpLevel | None = None,
    ) -> ReleaseOutcome:
        options = options or ReleaseOptions()
        if options.github_release and not options.push:
            raise GearuError("--github-release requires --push")
        plan = self.plan(
            value,
            bump=bump,
            dependency_tags=options.dependency_tags,
        )
        version = self._version(plan.version)
        target = plan.base_sha
        created_commit = False

        with self._candidate(plan.base_sha, version.tag, plan.source_sha) as candidate:
            if plan.already_tagged:
                self._verify_existing_release(candidate, version, plan.dependencies)
            else:
                merged_paths = self.git.changed_paths(cwd=candidate)
                target, created_commit = self._prepare_candidate(
                    candidate,
                    version,
                    plan.dependencies,
                    preapproved_changes=merged_paths,
                )
            self.git.fast_forward_branch(
                self.config.project.branch,
                target,
                expected_head=plan.base_sha,
            )
            self.git.ensure_tag(version.tag, target)

        if options.push:
            self.git.push_release(
                remote=self.config.project.remote,
                branch=self.config.project.branch,
                tag=version.tag,
                target=target,
            )

        github_created = False
        if options.github_release:
            repository = self.config.project.github_repo
            if repository is None:
                raise GearuError(
                    "[project].github_repo is required for --github-release"
                )
            notes = self.config.release.github_notes.format_map(self._values(version))
            github_created = GitHubReleases(self.root, self.runner).create(
                repository=repository,
                tag=version.tag,
                notes=notes,
                prerelease="-rc." in version.text,
            )

        return ReleaseOutcome(
            version=version.text,
            tag=version.tag,
            target_sha=target,
            created_commit=created_commit,
            pushed=options.push,
            github_release_created=github_created,
        )
