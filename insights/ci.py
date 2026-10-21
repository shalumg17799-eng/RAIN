"""Static platform checks, runnable in CI: `python -m insights.ci`.

Three invariants that must hold no matter what any one skill does:

1. Pack isolation. skills/insights and skills/data are independent packs: no file in one pack
   (code, SKILL.md, spec YAML) may import, call or reference the other, and the per-pack agent
   spec folders are checked the same way. The registry additionally refuses cross-pack
   dependencies at load time; this check catches references that never reach the registry.
2. Gateway-only LLM access. Every model call goes through insights/gateway. No file under
   skills/ or insights/ outside the gateway package may import an LLM SDK.
3. Registry health. Both packs scan without a single load error, and every pack skill declares
   its pack, stage and kind, so the orchestrators can select agents by capabilities at runtime.

Each check returns a list of problems (empty means it passed) so tests can assert on them; the
CLI prints them and exits non-zero on any.
"""

import re
import sys
from pathlib import Path

PACKS = ("insights", "data")
CHECKED_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".json", ".txt"}
LLM_SDK_IMPORT = re.compile(
    r"^\s*(import\s+(anthropic|openai)\b|from\s+(anthropic|openai)[.\s])", re.MULTILINE
)
GATEWAY_PACKAGE = "insights/gateway"


def _text_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file()
        and path.suffix.lower() in CHECKED_SUFFIXES
        and "__pycache__" not in path.parts
    )


def check_pack_isolation(root: Path) -> list[str]:
    problems: list[str] = []
    for pack in PACKS:
        other = next(p for p in PACKS if p != pack)
        # the other pack's name as a path or module segment, or one of its skill folder names
        other_skills = root / "skills" / other
        skill_names = sorted(p.name for p in other_skills.iterdir()) if other_skills.is_dir() else []
        patterns = [
            re.compile(rf"skills[/\\.]{other}\b"),
            re.compile(rf"agents[/\\.]{other}\b"),
        ]
        name_pattern = (
            re.compile(r"\b(" + "|".join(re.escape(n) for n in skill_names) + r")\b")
            if skill_names
            else None
        )
        for base in (root / "skills" / pack, root / "agents" / pack):
            for path in _text_files(base):
                text = path.read_text(encoding="utf-8", errors="replace")
                rel = path.relative_to(root).as_posix()
                for pattern in patterns:
                    if pattern.search(text):
                        problems.append(f"{rel}: references the {other!r} pack ({pattern.pattern})")
                if name_pattern is not None:
                    hit = name_pattern.search(text)
                    if hit:
                        problems.append(
                            f"{rel}: references {hit.group(0)!r}, a skill of the {other!r} pack"
                        )
    return problems


def check_gateway_only_llm(root: Path) -> list[str]:
    problems: list[str] = []
    for base in (root / "skills", root / "insights"):
        for path in _text_files(base):
            if path.suffix != ".py":
                continue
            rel = path.relative_to(root).as_posix()
            if rel.startswith(GATEWAY_PACKAGE):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            hit = LLM_SDK_IMPORT.search(text)
            if hit:
                problems.append(
                    f"{rel}: imports an LLM SDK directly ({hit.group(0).strip()!r}); "
                    "all model access goes through insights.gateway"
                )
    return problems


DATASOURCE_IMPORT = re.compile(
    r"^\s*(import\s+(insights\.datasources|psycopg2|neo4j)\b"
    r"|from\s+(insights\.datasources|psycopg2|neo4j)[.\s])",
    re.MULTILINE,
)
EXECUTOR_FOLDER = "skills/insights/governed-executor"

WRITE_CALL = re.compile(
    r"\.write_text\(|\.write_bytes\(|open\([^)\n]*,\s*['\"][wax]"
    r"|os\.(remove|unlink|rename|rmdir)\b|shutil\.|\.unlink\(|\.mkdir\("
)


def check_datasource_isolation(root: Path) -> list[str]:
    """Only the governed executor touches a data source. No other skill — in either pack — may
    import a data-source adapter or a database driver; everything else sees summaries and refs."""
    problems: list[str] = []
    for path in _text_files(root / "skills"):
        if path.suffix != ".py":
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith(EXECUTOR_FOLDER):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        hit = DATASOURCE_IMPORT.search(text)
        if hit:
            problems.append(
                f"{rel}: imports a data-source module ({hit.group(0).strip()!r}); only the "
                "governed executor's deterministic core touches a data source"
            )
    return problems


def check_skills_read_only(root: Path) -> list[str]:
    """Skill code never writes to disk: artifacts are written by the runners, rows live in the
    result store, and every skill tool is read-only by the ToolRegistry contract."""
    problems: list[str] = []
    for path in _text_files(root / "skills"):
        if path.suffix != ".py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        hit = WRITE_CALL.search(text)
        if hit:
            rel = path.relative_to(root).as_posix()
            problems.append(f"{rel}: calls a write API ({hit.group(0).strip()!r}); skills are read-only")
    return problems


def check_registry(root: Path) -> list[str]:
    from insights.skills_core.registry import SkillRegistry

    registry = SkillRegistry.scan(root / "skills")
    problems = [f"{error.path}: {error.error}" for error in registry.errors]
    for name in registry.names():
        skill = registry.get(name)
        if skill.pack is None:
            problems.append(f"{name}: not inside a pack folder")
            continue
        manifest = skill.manifest
        missing = [f for f in ("pack", "stage", "kind") if getattr(manifest, f) is None]
        if missing:
            problems.append(f"{name}: manifest is missing {', '.join(missing)}")
    return problems


def run_all(root: Path) -> list[str]:
    return (
        [f"pack_isolation: {p}" for p in check_pack_isolation(root)]
        + [f"gateway_only_llm: {p}" for p in check_gateway_only_llm(root)]
        + [f"datasource_isolation: {p}" for p in check_datasource_isolation(root)]
        + [f"skills_read_only: {p}" for p in check_skills_read_only(root)]
        + [f"registry: {p}" for p in check_registry(root)]
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    problems = run_all(root)
    for problem in problems:
        print(f"FAIL {problem}")
    if problems:
        return 1
    print("insights.ci: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
