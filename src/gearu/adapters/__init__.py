"""Construct configured ecosystem adapters."""

from __future__ import annotations

from pathlib import Path

from ..models import GearuConfig
from .base import Adapter
from .npm import NpmAdapter
from .python import PythonAdapter
from .rust import RustAdapter


def build_adapters(root: Path, config: GearuConfig) -> tuple[Adapter, ...]:
    adapters: list[Adapter] = []
    if config.python is not None:
        adapters.append(PythonAdapter(root, config.python))
    if config.rust is not None:
        adapters.append(RustAdapter(root, config.rust))
    if config.npm is not None:
        adapters.append(NpmAdapter(root, config.npm))
    return tuple(adapters)
