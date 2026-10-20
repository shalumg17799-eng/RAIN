"""Semantic versions, MAJOR.MINOR.PATCH only, compared numerically."""

import re

_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def parse_version(text: str) -> tuple[int, int, int]:
    match = _SEMVER.match(text)
    if match is None:
        raise ValueError(f"{text!r} is not a semantic version (MAJOR.MINOR.PATCH)")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)
