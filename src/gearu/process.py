"""Subprocess execution with consistent release errors."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from .errors import GearuError


class Runner:
    def __init__(self, log: Callable[[str], None]) -> None:
        self.log = log

    def run(
        self,
        command: Sequence[object],
        *,
        cwd: Path,
        capture: bool = False,
        check: bool = True,
        env: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        argv = [str(part) for part in command]
        self.log("$ " + " ".join(argv))
        merged_env = os.environ.copy()
        if env is not None:
            merged_env.update(env)
        try:
            result = subprocess.run(
                argv,
                cwd=cwd,
                capture_output=capture,
                text=True,
                env=merged_env,
                check=False,
            )
        except OSError as error:
            raise GearuError(f"could not run {argv[0]!r}: {error}") from error
        if check and result.returncode != 0:
            detail = ""
            if capture:
                output = "\n".join(
                    part.strip()
                    for part in (result.stdout, result.stderr)
                    if part.strip()
                )
                if output:
                    detail = f"\n{output}"
            raise GearuError(
                f"command failed ({result.returncode}): {' '.join(argv)}{detail}"
            )
        return result
