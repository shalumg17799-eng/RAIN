"""The five factory agents. Each is a role prompt + a skill set + a tool allowlist;
none contains domain knowledge. Skills live in factory/skills/ (including the
RAIDE profiling and data-quality skills); FACTORY_EXTRA_SKILLS_DIRS can add more."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from factory.config import SKILLS_DIR

def _skill_dirs() -> list[Path]:
    dirs = [SKILLS_DIR]
    for raw in os.environ.get("FACTORY_EXTRA_SKILLS_DIRS", "").split(os.pathsep):
        if raw.strip():
            dirs.append(Path(raw.strip()))
    return dirs


def load_skill(name: str) -> str | None:
    for base in _skill_dirs():
        for path in [base / name / "SKILL.md", *base.glob(f"**/skills/{name}/SKILL.md")]:
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                return re.sub(r"^---.*?---\s*", "", text, count=1, flags=re.S)  # drop frontmatter
    return None


COMMON_RULES = """
How you work:
- You are one of five agents in the PRD-to-App Factory. A coordinator starts you, gives you a task, and
  reads your `finish` handoff. Humans review the outputs at approval gates, so be exact and honest.
- Use only your tools. Every file you produce goes into the App Pack through a tool; never claim an output
  you did not save. Read earlier agents' outputs with `read_pack_file` (manifest.yaml, data_contract.yaml,
  metrics.yaml, reports/*, handoffs/*).
- Nothing about any particular domain is built into the factory: everything comes from this app's PRD and data.
- When a tool returns an error, fix the input and call it again. Do not stop at the first problem.
- Work efficiently: batch related items into one tool call where the tool accepts lists.
- End by calling `finish` exactly once. Status `blocked` only when you cannot proceed without a human.
"""


@dataclass
class AgentSpec:
    name: str
    title: str
    role: str
    tools: list[str]
    skills: list[str]
    optional_skills: list[str] = field(default_factory=list)
    effort: str = "high"
    max_turns: int = 60

    def system_prompt(self) -> str:
        parts = [f"You are the {self.title} agent. {self.role}", COMMON_RULES]
        for s in self.skills:
            text = load_skill(s)
            if text is None:
                raise FileNotFoundError(f"required skill {s!r} not found")
            parts.append(f"<skill name=\"{s}\">\n{text}\n</skill>")
        for s in self.optional_skills:
            text = load_skill(s)
            if text:
                parts.append(f"<skill name=\"{s}\" optional=\"true\">\n{text}\n</skill>")
        return "\n\n".join(parts)


COMMON_TOOLS = ["read_pack_file", "finish"]

AGENTS: dict[str, AgentSpec] = {
    "requirements": AgentSpec(
        name="requirements", title="Requirements",
        role="You read the product requirements document and write the App Manifest and the data contract.",
        tools=COMMON_TOOLS + ["read_prd", "save_app_info", "save_personas", "save_kpis", "save_signals",
                              "save_data_sources", "validate_manifest", "save_data_contract"],
        skills=["prd-ingest", "data-contract"], effort="high"),
    "data": AgentSpec(
        name="data", title="Data",
        role="You profile or generate the app's data, load it as a versioned dataset into the app's staging "
             "schema, check it against the data contract and record data-quality checks. When conformance "
             "findings say the data cannot reproduce PRD figures, you recalibrate it with minimal changes.",
        tools=COMMON_TOOLS + ["list_input_files", "profile_file", "run_python", "load_tables", "contract_check",
                              "dq_check", "run_sql"],
        skills=["data-sourcing"], optional_skills=["raide-profiling", "raide-dq"], effort="high", max_turns=80),
    "knowledge": AgentSpec(
        name="knowledge", title="Knowledge & AI",
        role="You build the metric layer (one verified query per PRD figure), the knowledge layer (ontology, "
             "graph, join hints, examples) and the governed AI profile with per-persona access and row-level "
             "security.",
        tools=COMMON_TOOLS + ["describe_schema", "run_sql", "list_figures", "save_metric", "save_join_hints",
                              "save_ontology", "save_examples", "save_governed_profile"],
        skills=["metric-layer", "governed-ai"], effort="high", max_turns=90),
    "app": AgentSpec(
        name="app", title="App builder",
        role="You configure the generic runtime app's screens for every persona and preview them against live data.",
        tools=COMMON_TOOLS + ["save_ui_config", "preview_runtime"],
        skills=["ui-config"], effort="medium", max_turns=25),
    "release": AgentSpec(
        name="release", title="QA & release",
        role="You verify the generated app against its PRD and security model, classify every failure for "
             "routing, and - after human approval - prepare and run the Azure deployment.",
        tools=COMMON_TOOLS + ["run_conformance", "run_sql", "run_security_checks", "smoke_test_ask",
                              "record_findings", "prepare_deployment", "deploy_to_azure", "write_release_notes"],
        skills=["prd-conformance"], effort="high", max_turns=60),
}
