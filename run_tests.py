#!/usr/bin/env python3
"""Run the Gearu test suite from any platform."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent
    subprocess.run(
        [sys.executable, "-m", "pytest", "src/tests", "-q"],
        check=True,
        cwd=root,
    )


if __name__ == "__main__":
    main()

