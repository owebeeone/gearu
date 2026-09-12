from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "generate_cli_reference.py"


def run_generator(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )


def test_generated_cli_reference_is_current() -> None:
    result = run_generator("--check")

    assert result.returncode == 0, result.stderr


def test_generator_stdout_contains_every_command_help() -> None:
    result = run_generator()

    assert result.returncode == 0, result.stderr
    assert "# CLI Reference" in result.stdout
    assert "## `gearu`" in result.stdout
    assert "## `gearu plan`" in result.stdout
    assert "## `gearu release`" in result.stdout
