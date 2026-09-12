"""Explicit release-version parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .errors import GearuError

_NUMBER = r"(?:0|[1-9][0-9]*)"
_VERSION = re.compile(rf"{_NUMBER}\.{_NUMBER}\.{_NUMBER}(?:-rc\.[1-9][0-9]*)?")
_CONFIGURED_VERSION = re.compile(
    rf"({_NUMBER})\.({_NUMBER})\.({_NUMBER})(?:(?:-rc\.|rc)[1-9][0-9]*)?"
)

BumpLevel = Literal["major", "minor", "patch"]


@dataclass(frozen=True)
class ReleaseVersion:
    """A normalized SemVer release and its configured Git tag."""

    text: str
    tag: str

    @classmethod
    def parse(cls, value: str, *, tag_prefix: str) -> ReleaseVersion:
        text = (
            value[len(tag_prefix) :]
            if tag_prefix and value.startswith(tag_prefix)
            else value
        )
        if _VERSION.fullmatch(text) is None:
            raise GearuError(
                "version must look like X.Y.Z or X.Y.Z-rc.N without leading zeroes"
            )
        return cls(text=text, tag=f"{tag_prefix}{text}")

    @property
    def python_text(self) -> str:
        return re.sub(r"-rc\.([1-9][0-9]*)$", r"rc\1", self.text)


@dataclass(frozen=True)
class BumpSelection:
    version: ReleaseVersion
    base_version: str


def _version_core(value: str) -> tuple[int, int, int]:
    match = _CONFIGURED_VERSION.fullmatch(value)
    if match is None:
        raise GearuError(f"cannot bump from invalid configured version {value!r}")
    return tuple(int(part) for part in match.groups())


def select_bumped_version(
    *,
    bump: BumpLevel,
    tag_prefix: str,
    tags: tuple[str, ...],
    configured_versions: tuple[str, ...],
) -> BumpSelection:
    if bump not in ("major", "minor", "patch"):
        raise GearuError("bump must be major, minor, or patch")
    configured_cores = {_version_core(version) for version in configured_versions}
    if len(configured_cores) > 1:
        versions = ", ".join(sorted(configured_versions))
        raise GearuError(f"configured versions disagree; cannot bump: {versions}")

    tag_cores: list[tuple[int, int, int]] = []
    for tag in tags:
        if tag_prefix and not tag.startswith(tag_prefix):
            continue
        try:
            release = ReleaseVersion.parse(tag, tag_prefix=tag_prefix)
        except GearuError:
            continue
        tag_cores.append(_version_core(release.text))

    candidates = [*configured_cores, *tag_cores]
    major, minor, patch = max(candidates, default=(0, 0, 0))
    base_version = f"{major}.{minor}.{patch}"
    if bump == "major":
        target = f"{major + 1}.0.0"
    elif bump == "minor":
        target = f"{major}.{minor + 1}.0"
    else:
        target = f"{major}.{minor}.{patch + 1}"
    return BumpSelection(
        version=ReleaseVersion.parse(target, tag_prefix=tag_prefix),
        base_version=base_version,
    )
