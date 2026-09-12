"""Interface shared by ecosystem-specific version adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import CommandSpec, FileChange
from ..version import ReleaseVersion


class Adapter(ABC):
    @abstractmethod
    def plan(self, version: ReleaseVersion) -> tuple[FileChange, ...]:
        raise NotImplementedError

    @abstractmethod
    def apply(self, version: ReleaseVersion) -> set[Path]:
        raise NotImplementedError

    @abstractmethod
    def validate(self, version: ReleaseVersion) -> None:
        raise NotImplementedError

    @abstractmethod
    def managed_files(self) -> set[Path]:
        raise NotImplementedError

    @abstractmethod
    def refresh_commands(self, touched: set[Path]) -> tuple[CommandSpec, ...]:
        raise NotImplementedError
