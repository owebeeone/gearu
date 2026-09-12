"""Targeted manifest updates that preserve surrounding formatting and comments."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from .errors import GearuError


def _toml_data(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise GearuError(f"manifest not found: {path}") from error
    except tomllib.TOMLDecodeError as error:
        raise GearuError(f"invalid TOML in {path}: {error}") from error


def toml_value(path: Path, key: str) -> Any:
    value: Any = _toml_data(path)
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise GearuError(f"{path} has no TOML key {key!r}")
        value = value[part]
    return value


def _table_bounds(
    lines: list[str], table: tuple[str, ...], *, path: Path
) -> tuple[int, int]:
    if not table:
        first_table = next(
            (
                index
                for index, line in enumerate(lines)
                if line.lstrip().startswith("[")
            ),
            len(lines),
        )
        return 0, first_table
    header = r"\.\s*".join(re.escape(part) for part in table)
    pattern = re.compile(rf"^\s*\[\s*{header}\s*\]\s*(?:#.*)?(?:\r?\n)?$")
    start = next(
        (index + 1 for index, line in enumerate(lines) if pattern.match(line)), None
    )
    if start is None:
        raise GearuError(f"{path} has no TOML table {'.'.join(table)!r}")
    end = next(
        (
            index
            for index in range(start, len(lines))
            if lines[index].lstrip().startswith("[")
        ),
        len(lines),
    )
    return start, end


def replace_toml_string(path: Path, key: str, value: str) -> bool:
    current = toml_value(path, key)
    if not isinstance(current, str):
        raise GearuError(f"{path} TOML key {key!r} is not a string")
    if current == value:
        return False

    parts = tuple(key.split("."))
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    start, end = _table_bounds(lines, parts[:-1], path=path)
    assignment = re.compile(
        rf"^(\s*{re.escape(parts[-1])}\s*=\s*)([\"'])([^\"']*)([\"'])(.*)$"
    )
    matches: list[int] = []
    for index in range(start, end):
        match = assignment.match(lines[index].rstrip("\r\n"))
        if match is not None and match.group(2) == match.group(4):
            matches.append(index)
    if len(matches) != 1:
        raise GearuError(
            f"expected one editable {key!r} assignment in {path}, found {len(matches)}"
        )
    index = matches[0]
    original = lines[index]
    ending = original[len(original.rstrip("\r\n")) :]
    match = assignment.match(original.rstrip("\r\n"))
    assert match is not None
    lines[index] = (
        f"{match.group(1)}{match.group(2)}{value}{match.group(4)}{match.group(5)}{ending}"
    )
    updated = "".join(lines)
    parsed = tomllib.loads(updated)
    observed: Any = parsed
    for part in parts:
        observed = observed[part]
    if observed != value:
        raise GearuError(f"updating {key!r} in {path} did not produce {value!r}")
    path.write_text(updated, encoding="utf-8", newline="")
    return True


def replace_toml_inline_string(path: Path, *, key: str, field: str, value: str) -> bool:
    current = toml_value(path, key)
    if not isinstance(current, dict) or not isinstance(current.get(field), str):
        raise GearuError(f"{path} TOML key {key!r} has no string field {field!r}")
    if current[field] == value:
        return False

    parts = tuple(key.split("."))
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    start, end = _table_bounds(lines, parts[:-1], path=path)
    assignment = re.compile(rf"^(\s*{re.escape(parts[-1])}\s*=\s*\{{)(.*)(\}}.*)$")
    matches = [
        (index, assignment.match(lines[index].rstrip("\r\n")))
        for index in range(start, end)
    ]
    matches = [(index, match) for index, match in matches if match is not None]
    if len(matches) != 1:
        raise GearuError(f"expected one inline-table assignment for {key!r} in {path}")
    index, match = matches[0]
    assert match is not None
    original = lines[index]
    ending = original[len(original.rstrip("\r\n")) :]
    field_pattern = re.compile(rf"(\b{re.escape(field)}\s*=\s*)([\"'])([^\"']*)([\"'])")
    middle, count = field_pattern.subn(
        lambda item: f"{item.group(1)}{item.group(2)}{value}{item.group(4)}",
        match.group(2),
        count=1,
    )
    if count != 1:
        raise GearuError(
            f"expected one {field!r} field in inline table {key!r} in {path}"
        )
    lines[index] = f"{match.group(1)}{middle}{match.group(3)}{ending}"
    updated = "".join(lines)
    parsed = tomllib.loads(updated)
    observed: Any = parsed
    for part in parts:
        observed = observed[part]
    if observed.get(field) != value:
        raise GearuError(
            f"updating {key!r}.{field} in {path} did not produce {value!r}"
        )
    path.write_text(updated, encoding="utf-8", newline="")
    return True


def replace_json_top_level_string(path: Path, key: str, value: str) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except FileNotFoundError as error:
        raise GearuError(f"manifest not found: {path}") from error
    except json.JSONDecodeError as error:
        raise GearuError(f"invalid JSON in {path}: {error}") from error
    if not isinstance(data, dict) or not isinstance(data.get(key), str):
        raise GearuError(f"{path} has no top-level string field {key!r}")
    if data[key] == value:
        return False
    pattern = re.compile(rf'^(\s*"{re.escape(key)}"\s*:\s*)"[^"\\]*"', re.MULTILINE)
    updated, count = pattern.subn(rf'\g<1>"{value}"', text, count=1)
    if count != 1:
        raise GearuError(f"expected one editable top-level {key!r} field in {path}")
    parsed = json.loads(updated)
    if not isinstance(parsed, dict) or parsed.get(key) != value:
        raise GearuError(f"updating {key!r} in {path} did not produce {value!r}")
    path.write_text(updated, encoding="utf-8", newline="")
    return True
