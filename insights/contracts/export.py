"""Export the contracts as JSON Schema files: python -m insights.contracts.export [out_dir]."""

import json
import sys
from pathlib import Path

from pydantic import BaseModel

from insights.contracts.agent import AgentDef
from insights.contracts.events import AuditEvent, StageEvent
from insights.contracts.gateway import CompletionResult, Message
from insights.contracts.principal import Principal
from insights.contracts.profile import AppProfile
from insights.contracts.record import RunRecord
from insights.contracts.request import AskRequest
from insights.contracts.response import AskResponse
from insights.contracts.skill import SkillManifest
from insights.contracts.state import RunState

SCHEMAS: dict[str, type[BaseModel]] = {
    "ask-request": AskRequest,
    "ask-response": AskResponse,
    "principal": Principal,
    "app-profile": AppProfile,
    "run-state": RunState,
    "run-record": RunRecord,
    "skill-manifest": SkillManifest,
    "agent": AgentDef,
    "stage-event": StageEvent,
    "audit-event": AuditEvent,
    "gateway-message": Message,
    "gateway-completion-result": CompletionResult,
}


def render(model: type[BaseModel]) -> str:
    """Deterministic text: sorted keys, two-space indent, trailing newline."""
    return json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"


def export_schemas(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, model in SCHEMAS.items():
        target = out_dir / f"{name}.schema.json"
        target.write_text(render(model), encoding="utf-8", newline="\n")
        written.append(target)
    return written


def main(argv: list[str]) -> int:
    from insights.cli import repo_root

    out = Path(argv[0]) if argv else repo_root() / "docs" / "contracts"
    for path in export_schemas(out):
        sys.stdout.write(f"wrote {path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
