"""Skill framework: SKILL.md parsing, versioned registry, dynamic load + execute.

Directories are layered (DIF_SKILLS_DIRS): a skill found in a later directory replaces the same name/version from an
earlier one. A skill with `enterprise: <id>` in its frontmatter is an enterprise-specific override: it is returned only
for runs of that enterprise, must keep the shared skill's validation contract, and is invisible to other tenants."""
import importlib.util
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_FM = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.S)
REQUIRED = ("name", "version", "description")
SHARED = "*"


class SkillError(Exception):
    pass


@dataclass
class Skill:
    name: str
    version: str
    description: str
    path: Path
    dependencies: list = field(default_factory=list)
    validation: dict = field(default_factory=dict)
    examples: list = field(default_factory=list)
    body: str = ""
    restricted: bool = False
    enterprise: str | None = None
    _fn: object = None

    def meta(self):
        return {"name": self.name, "version": self.version, "description": self.description,
                "dependencies": self.dependencies, "validation": self.validation,
                "examples": self.examples, "restricted": self.restricted, "enterprise": self.enterprise}

    def _load(self):
        if self._fn is None:
            script = self.path / "scripts" / "run.py"
            if not script.exists():
                raise SkillError(f"{self.name}: scripts/run.py missing")
            modname = f"skill_{self.name.replace('-', '_')}" + (f"__{self.enterprise}" if self.enterprise else "")
            spec = importlib.util.spec_from_file_location(modname, script)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if not hasattr(mod, "run"):
                raise SkillError(f"{self.name}: scripts/run.py must define run(input, ctx)")
            self._fn = mod.run
        return self._fn

    def validate_input(self, data: dict):
        missing = [k for k in self.validation.get("required_input", []) if data.get(k) is None]
        if missing:
            raise SkillError(f"{self.name}: missing required input {missing}")

    def execute(self, data: dict, ctx: dict | None = None) -> dict:
        self.validate_input(data)
        out = self._load()(data, ctx or {})
        missing = [k for k in self.validation.get("required_output", []) if k not in out]
        if missing:
            raise SkillError(f"{self.name}: output missing {missing}")
        return out


def parse_skill_md(path: Path) -> Skill:
    text = (path / "SKILL.md").read_text()
    m = _FM.match(text)
    if not m:
        raise SkillError(f"{path.name}: SKILL.md needs YAML frontmatter")
    fm = yaml.safe_load(m.group(1)) or {}
    for k in REQUIRED:
        if k not in fm:
            raise SkillError(f"{path.name}: SKILL.md frontmatter missing '{k}'")
    ent = fm.get("enterprise")
    return Skill(name=fm["name"], version=str(fm["version"]), description=fm["description"], path=path,
                 dependencies=fm.get("dependencies", []), validation=fm.get("validation", {}),
                 examples=fm.get("examples", []), body=m.group(2), restricted=bool(fm.get("restricted", False)),
                 enterprise=str(ent) if ent else None)


def _vkey(v: str):
    return tuple(int(p) if p.isdigit() else 0 for p in v.split("."))


class SkillRegistry:
    def __init__(self, skills_dirs):
        dirs = [skills_dirs] if isinstance(skills_dirs, (str, Path)) else list(skills_dirs)
        self.dirs = [Path(d) for d in dirs]
        self.dir = self.dirs[0]
        self._skills: dict[str, dict[str, dict[str, Skill]]] = {}   # name -> version -> enterprise|"*" -> Skill
        self.errors: dict[str, str] = {}
        self.discover()

    def discover(self):
        self._skills, self.errors = {}, {}
        for d in self.dirs:
            for p in sorted(Path(d).glob("*/SKILL.md")):
                try:
                    self.register(parse_skill_md(p.parent))
                except Exception as e:  # keep platform up if one skill is broken
                    self.errors[p.parent.name] = str(e)
        self._check_overrides()
        self._check_dependencies()

    def register(self, skill: Skill):
        self._skills.setdefault(skill.name, {}).setdefault(skill.version, {})[skill.enterprise or SHARED] = skill

    def _check_overrides(self):
        """An enterprise override must satisfy the shared skill's validation contract (same required input/output)."""
        for name, vers in self._skills.items():
            for ver, by_ent in vers.items():
                shared = by_ent.get(SHARED)
                for ent, sk in list(by_ent.items()):
                    if ent == SHARED or shared is None:
                        continue
                    for key in ("required_input", "required_output"):
                        want = set(shared.validation.get(key, []))
                        have = set(sk.validation.get(key, []))
                        if not want <= have:
                            self.errors[f"{name}@{ver}[{ent}]"] = f"override drops {key} {sorted(want - have)} of the shared skill"
                            del by_ent[ent]
                            break

    def _check_dependencies(self):
        for name in list(self._skills):
            deps = {d for by_ent in self._skills[name].values() for s in by_ent.values() for d in s.dependencies}
            bad = {d for d in deps if d not in self._skills}
            if bad:  # enforce declared dependencies
                self.errors[name] = f"missing dependencies {sorted(bad)}"
                del self._skills[name]

    def get(self, name: str, version: str | None = None, enterprise: str | None = None) -> Skill:
        vers = self._skills.get(name)
        if not vers:
            raise SkillError(f"unknown skill '{name}'")
        if version is None:
            version = max(vers, key=_vkey)
        if version not in vers:
            raise SkillError(f"skill '{name}' has no version {version}")
        by_ent = vers[version]
        sk = by_ent.get(enterprise) if enterprise else None
        sk = sk or by_ent.get(SHARED)
        if sk is None:
            raise SkillError(f"skill '{name}' {version} exists only as an enterprise override for {sorted(by_ent)}")
        return sk

    def list(self, enterprise: str | None = None):
        out = []
        for vers in self._skills.values():
            for by_ent in vers.values():
                for ent, s in by_ent.items():
                    if ent == SHARED or enterprise is None or ent == enterprise:
                        out.append(s.meta())
        return out
