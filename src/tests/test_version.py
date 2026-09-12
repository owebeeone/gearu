from __future__ import annotations

import pytest

from gearu.errors import GearuError
from gearu.version import ReleaseVersion, select_bumped_version


@pytest.mark.parametrize("value", ["1.2.3", "v1.2.3"])
def test_release_version_accepts_plain_or_tagged_version(value: str) -> None:
    version = ReleaseVersion.parse(value, tag_prefix="v")

    assert version.text == "1.2.3"
    assert version.tag == "v1.2.3"
    assert version.python_text == "1.2.3"


def test_release_version_normalizes_release_candidate_for_python() -> None:
    version = ReleaseVersion.parse("v1.2.3-rc.4", tag_prefix="v")

    assert version.text == "1.2.3-rc.4"
    assert version.python_text == "1.2.3rc4"


@pytest.mark.parametrize(
    "value",
    ["", "1.2", "01.2.3", "1.02.3", "1.2.03", "1.2.3-rc.0", "release-1.2.3"],
)
def test_release_version_rejects_ambiguous_versions(value: str) -> None:
    with pytest.raises(GearuError):
        ReleaseVersion.parse(value, tag_prefix="v")


def test_bump_uses_configured_version_when_it_is_newest() -> None:
    selection = select_bumped_version(
        bump="minor",
        tag_prefix="v",
        tags=("v1.1.0",),
        configured_versions=("1.2.3",),
    )

    assert selection.version.text == "1.3.0"
    assert selection.base_version == "1.2.3"


def test_bump_uses_highest_local_or_remote_release_tag() -> None:
    selection = select_bumped_version(
        bump="patch",
        tag_prefix="v",
        tags=("not-a-release", "9.0.0", "v1.9.0", "v2.0.0-rc.2"),
        configured_versions=("1.2.3",),
    )

    assert selection.version.tag == "v2.0.1"
    assert selection.base_version == "2.0.0"


def test_bump_starts_from_zero_without_versions_or_tags() -> None:
    selection = select_bumped_version(
        bump="minor",
        tag_prefix="v",
        tags=(),
        configured_versions=(),
    )

    assert selection.version.tag == "v0.1.0"
    assert selection.base_version == "0.0.0"


def test_bump_accepts_python_normalized_release_candidate_version() -> None:
    selection = select_bumped_version(
        bump="patch",
        tag_prefix="v",
        tags=(),
        configured_versions=("1.2.3rc4",),
    )

    assert selection.version.tag == "v1.2.4"


def test_bump_rejects_disagreeing_configured_versions() -> None:
    with pytest.raises(GearuError, match="configured versions disagree"):
        select_bumped_version(
            bump="patch",
            tag_prefix="v",
            tags=(),
            configured_versions=("1.2.3", "2.0.0"),
        )


def test_bump_rejects_unknown_level_for_programmatic_callers() -> None:
    with pytest.raises(GearuError, match="bump must be major, minor, or patch"):
        select_bumped_version(
            bump="banana",  # type: ignore[arg-type]
            tag_prefix="v",
            tags=(),
            configured_versions=("1.2.3",),
        )
