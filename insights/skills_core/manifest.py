"""Parse SKILL.md: YAML front matter between `---` fences, then free-form Markdown."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from insights.contracts.skill import SkillManifest
from insights.yamlio import load_yaml

_FENCE = "---"


class ManifestError(ValueError):
    """SKILL.md is missing, malformed or does not satisfy the manifest contract."""


def parse_skill_md(path: Path) -> tuple[SkillManifest, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"cannot read {path}: {exc}") from exc

    lines = text.splitlines()
    if not lines or lines[0].strip() != _FENCE:
        raise ManifestError(f"{path}: SKILL.md must start with '---' front matter")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == _FENCE)
    except StopIteration:
        raise ManifestError(f"{path}: front matter is not closed with '---'") from None

    try:
        raw = load_yaml("\n".join(lines[1:end]))
    except (yaml.YAMLError, ValueError) as exc:
        raise ManifestError(f"{path}: front matter is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ManifestError(f"{path}: front matter must be a mapping")

    try:
        manifest = SkillManifest.model_validate(raw)
    except ValidationError as exc:
        raise ManifestError(f"{path}: invalid manifest: {exc}") from exc
    return manifest, "\n".join(lines[end + 1 :]).lstrip("\n")
