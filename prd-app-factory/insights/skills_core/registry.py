"""Skill registry: scan skills/, keep versions, enforce the contract, isolate broken skills.

A skill folder is `skills/<name>/` (or `skills/<name>@<version>/` to keep an older version
beside the current one). Each is loaded on its own: a skill that fails to parse, import or satisfy
its dependencies is recorded in `errors` and everything else keeps working. The registry is
immutable once built; `reload()` returns a new one.
"""

import copy
import hashlib
import importlib.util
import inspect
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from insights.contracts.skill import SkillManifest
from insights.skills_core.errors import SkillError, SkillNotFoundError
from insights.skills_core.manifest import ManifestError, parse_skill_md
from insights.skills_core.versions import parse_version

RunFn = Callable[[dict[str, Any], Any], dict[str, Any]]


@dataclass(frozen=True)
class LoadedSkill:
    manifest: SkillManifest
    run: RunFn
    path: Path
    body: str


@dataclass(frozen=True)
class SkillLoadError:
    path: str
    error: str
    name: str | None = None
    version: str | None = None


@dataclass(frozen=True)
class SkillSummary:
    name: str
    version: str
    description: str
    restricted: bool
    labels: tuple[str, ...]


class _LoadFailure(Exception):
    pass


def _import_run(folder: Path, manifest: SkillManifest) -> RunFn:
    script = folder / "scripts" / "run.py"
    if not script.is_file():
        raise _LoadFailure("scripts/run.py is missing")
    tag = hashlib.sha1(str(script.resolve()).encode("utf-8"), usedforsecurity=False).hexdigest()[:8]
    slug = f"{manifest.name}_{manifest.version}".replace("-", "_").replace(".", "_")
    module_name = f"insights_skill_{slug}_{tag}"
    spec = importlib.util.spec_from_file_location(module_name, script)
    if spec is None or spec.loader is None:
        raise _LoadFailure("scripts/run.py cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except (Exception, SystemExit) as exc:
        sys.modules.pop(module_name, None)
        raise _LoadFailure(f"scripts/run.py failed to import: {type(exc).__name__}: {exc}") from exc
    run = getattr(module, "run", None)
    if not callable(run):
        sys.modules.pop(module_name, None)
        raise _LoadFailure("scripts/run.py must define run(input, ctx)")
    try:
        inspect.signature(run).bind(None, None)
    except (TypeError, ValueError):
        sys.modules.pop(module_name, None)
        raise _LoadFailure("run must be callable as run(input, ctx)") from None
    return run  # type: ignore[no-any-return]


def _load_folder(folder: Path) -> tuple[SkillManifest, RunFn, str]:
    try:
        manifest, body = parse_skill_md(folder / "SKILL.md")
    except ManifestError as exc:
        raise _LoadFailure(str(exc)) from exc
    if folder.name not in (manifest.name, f"{manifest.name}@{manifest.version}"):
        raise _LoadFailure(
            f"folder name {folder.name!r} does not match skill {manifest.name!r}"
            f" (expected {manifest.name!r} or '{manifest.name}@{manifest.version}')"
        )
    return manifest, _import_run(folder, manifest), body


def _cyclic_names(graph: Mapping[str, set[str]]) -> set[str]:
    """Names that can reach themselves through dependencies."""
    cyclic: set[str] = set()
    for start in graph:
        stack = list(graph[start])
        seen: set[str] = set()
        while stack:
            node = stack.pop()
            if node == start:
                cyclic.add(start)
                break
            if node in seen:
                continue
            seen.add(node)
            stack.extend(graph.get(node, ()))
    return cyclic


class SkillRegistry:
    def __init__(
        self,
        skills_dir: Path,
        skills: Mapping[str, Mapping[str, LoadedSkill]],
        errors: tuple[SkillLoadError, ...],
    ) -> None:
        self.skills_dir = skills_dir
        self._skills = {name: dict(versions) for name, versions in skills.items()}
        self.errors = errors

    @classmethod
    def scan(cls, skills_dir: Path) -> "SkillRegistry":
        errors: list[SkillLoadError] = []
        loaded: list[LoadedSkill] = []
        folders = (
            sorted(p for p in skills_dir.iterdir() if p.is_dir() and p.name[0] not in "._")
            if skills_dir.is_dir()
            else []
        )
        for folder in folders:
            try:
                manifest, run, body = _load_folder(folder)
            except _LoadFailure as exc:
                errors.append(SkillLoadError(path=str(folder), error=str(exc)))
                continue
            loaded.append(LoadedSkill(manifest=manifest, run=run, path=folder, body=body))

        # Two folders claiming the same (name, version) is ambiguous: reject both.
        counts: dict[tuple[str, str], int] = {}
        for skill in loaded:
            key = (skill.manifest.name, skill.manifest.version)
            counts[key] = counts.get(key, 0) + 1
        kept: list[LoadedSkill] = []
        for skill in loaded:
            key = (skill.manifest.name, skill.manifest.version)
            if counts[key] > 1:
                errors.append(_error(skill, f"duplicate skill {key[0]}@{key[1]} in two folders"))
            else:
                kept.append(skill)

        kept = cls._resolve_dependencies(kept, errors)
        registry: dict[str, dict[str, LoadedSkill]] = {}
        for skill in kept:
            registry.setdefault(skill.manifest.name, {})[skill.manifest.version] = skill
        return cls(skills_dir, registry, tuple(errors))

    @staticmethod
    def _resolve_dependencies(
        skills: list[LoadedSkill], errors: list[SkillLoadError]
    ) -> list[LoadedSkill]:
        """Drop skills whose dependencies are missing, broken or circular, until stable."""
        remaining = list(skills)
        while True:
            present = {s.manifest.name for s in remaining}
            graph: dict[str, set[str]] = {name: set() for name in present}
            for skill in remaining:
                graph[skill.manifest.name] |= set(skill.manifest.dependencies) & present
            cyclic = _cyclic_names(graph)
            kept: list[LoadedSkill] = []
            for skill in remaining:
                missing = [d for d in skill.manifest.dependencies if d not in present]
                if missing:
                    errors.append(
                        _error(skill, f"dependency {missing[0]!r} is missing or failed to load")
                    )
                elif skill.manifest.name in cyclic:
                    errors.append(_error(skill, "dependency cycle"))
                else:
                    kept.append(skill)
            if len(kept) == len(remaining):
                return kept
            remaining = kept

    def reload(self) -> "SkillRegistry":
        return SkillRegistry.scan(self.skills_dir)

    # ---- lookup ----------------------------------------------------------------------------

    def names(self) -> list[str]:
        return sorted(self._skills)

    def versions(self, name: str) -> list[str]:
        if name not in self._skills:
            raise SkillNotFoundError(f"unknown skill {name!r}")
        return sorted(self._skills[name], key=parse_version)

    def get(self, name: str, version: str | None = None) -> LoadedSkill:
        versions = self.versions(name)
        chosen = version if version is not None else versions[-1]
        if chosen not in self._skills[name]:
            raise SkillNotFoundError(f"skill {name!r} has no version {chosen!r}")
        return self._skills[name][chosen]

    def list_skills(self, *, include_restricted: bool = False) -> list[SkillSummary]:
        out = []
        for name in self.names():
            for version in self.versions(name):
                m = self._skills[name][version].manifest
                if m.restricted and not include_restricted:
                    continue
                out.append(SkillSummary(name, version, m.description, m.restricted, m.labels))
        return out

    # ---- invocation ------------------------------------------------------------------------

    def invoke(
        self, name: str, version: str | None, input: dict[str, Any], ctx: Any
    ) -> dict[str, Any]:
        """Validate input, run the skill, validate output and label. Returns the output dict."""
        skill = self.get(name, version)
        manifest = skill.manifest

        def fail(phase: Any, message: str) -> SkillError:
            return SkillError(manifest.name, manifest.version, phase, message)

        missing_in = [k for k in manifest.validation.required_input if input.get(k) is None]
        if missing_in:
            raise fail("input", f"missing or null required input: {', '.join(missing_in)}")

        try:
            output = skill.run(copy.deepcopy(input), ctx)
        except SkillError:
            raise
        except Exception as exc:
            raise fail("execution", f"{type(exc).__name__}: {exc}") from exc

        if not isinstance(output, dict):
            raise fail("output", f"must return a dict, got {type(output).__name__}")
        self._check_label(manifest, output, fail)
        missing_out = [k for k in manifest.validation.required_output if output.get(k) is None]
        if missing_out:
            raise fail("output", f"missing or null required output: {', '.join(missing_out)}")
        return output

    @staticmethod
    def _check_label(
        manifest: SkillManifest, output: dict[str, Any], fail: Callable[[Any, str], SkillError]
    ) -> None:
        if not manifest.labels:
            if "label" in output:
                raise fail("label", "skill declares no labels but returned one")
            return
        label = output.get("label")
        if label is None:
            raise fail("label", "skill declares labels and must return 'label'")
        if label not in manifest.labels:
            raise fail(
                "label", f"undeclared label {label!r} (declared: {', '.join(manifest.labels)})"
            )


def _error(skill: LoadedSkill, message: str) -> SkillLoadError:
    return SkillLoadError(
        path=str(skill.path),
        error=message,
        name=skill.manifest.name,
        version=skill.manifest.version,
    )
