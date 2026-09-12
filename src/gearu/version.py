"""Explicit release-version parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import GearuError

_NUMBER = r"(?:0|[1-9][0-9]*)"
_VERSION = re.compile(rf"{_NUMBER}\.{_NUMBER}\.{_NUMBER}(?:-rc\.[1-9][0-9]*)?")


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
