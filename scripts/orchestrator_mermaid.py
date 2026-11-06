"""Render each pack's orchestrator as Mermaid, FROM the YAML and the registry — never by hand.

Usage: python scripts/orchestrator_mermaid.py [insights|data|all]

The drawing is honest about the architecture: every stage is reached from the supervisor and
returns to it (there is no hardcoded sequence), fan-out stages show their per-item branch node,
refine loop-backs are derived from the candidate skills' declared labels, and the terminal stage
is marked. The dotted stage-to-stage edges show the DATA dependencies (consumes/produces) the
supervisor derives its forward order from.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from insights.runtime.supervisor import (  # noqa: E402
    REFINE_PREFIX,
    load_orchestrator,
    refine_target,
    registry_views,
)
from insights.skills_core.registry import SkillRegistry  # noqa: E402


def mermaid(pack: str) -> str:
    orch = load_orchestrator(ROOT / "agents" / pack / "orchestrator.yaml")
    registry = SkillRegistry.scan(ROOT / "skills")
    views = registry_views(registry, orch.pack)
    stage_names = tuple(stage.stage for stage in orch.stages)

    lines = [
        f"%% {orch.name} v{orch.version} — generated from agents/{pack}/orchestrator.yaml",
        "flowchart TD",
        f'    SUP(["supervisor<br/><i>picks the next agent from the registry</i>"])',
        "    START((start)) --> SUP",
    ]
    for stage in orch.stages:
        candidates = views.get(stage.stage, [])
        skills = "<br/>".join(f"{v.name} ({v.kind})" for v in candidates) or "?"
        shape = ("[[", "]]") if stage.terminal else ("[", "]")
        lines.append(f'    {stage.stage}{shape[0]}"{stage.stage}<br/><i>{skills}</i>"{shape[1]}')
        lines.append(f"    SUP -.selects.-> {stage.stage}")
        if stage.fanout is not None:
            item = f"{stage.stage}__item"
            lines.append(f'    {item}(("per-item run<br/>{stage.fanout.item_key}"))')
            lines.append(f"    {stage.stage} ==Send==> {item}")
            lines.append(f"    {item} --> SUP")
        else:
            lines.append(f"    {stage.stage} --> SUP")
        if stage.terminal:
            lines.append(f"    {stage.stage} --> DONE((end))")
        for label in sorted({l for v in candidates for l in v.labels}):
            if label.startswith(REFINE_PREFIX):
                target = refine_target(label, views, stage.stage, stage_names)
                if target:
                    lines.append(f"    {stage.stage} -. {label}<br/>(max_refines={orch.limits.max_refines}) .-> {target}")
            elif label == "escalate" or label in stage.terminal_labels:
                pass  # every escalation routes through the supervisor to the terminal stage
    lines.append(f"    SUP -.escalations & exhaustion.-> {orch.terminal_stage.stage}")
    lines.append(f'    style SUP fill:#003087,color:#fff')
    lines.append(f"    style {orch.terminal_stage.stage} fill:#e8f5e9")
    return "\n".join(lines)


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    packs = ("insights", "data") if which == "all" else (which,)
    for pack in packs:
        print(f"```mermaid\n{mermaid(pack)}\n```\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
