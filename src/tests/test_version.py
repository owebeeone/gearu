from __future__ import annotations

import pytest

from gearu.errors import GearuError
from gearu.version import ReleaseVersion


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
