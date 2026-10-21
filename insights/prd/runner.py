"""Run the PRD design graph (agents/prd-agent.yaml) end to end.

The runner owns everything outside the graph: governed gateway access under the `design` purpose
with the least-privilege `svc-prd-design` principal and no response cache, document and schema
loading, the SQLite checkpointer, typed StageEvents as JSON lines, artifact file writing, and the
run budget. All step logic lives in the skills; all routing lives in prd-agent.yaml.

Checkpointing and retention: every superstep's full graph state — including the PRD document and
every draft artifact — is persisted to `<output>/checkpoints/<run_id>.sqlite` so an interrupted
run resumes from its last good stage (`--resume <run_id>`). Because that state IS PRD content,
the policy is: the run's checkpoint database is DELETED on successful completion, kept on an
interrupted or failed run for resume, and any checkpoint file older than RETENTION_DAYS is pruned
whenever a new run starts.
"""

import csv
import hashlib
import json
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import yaml

from insights.contracts.enums import EventType
from insights.contracts.events import StageEvent
from insights.contracts.principal import Principal
from insights.contracts.profile import load_app_profile
from insights.gateway.config import GatewayConfig, build_gateway
from insights.runtime.agent import assert_valid_agent, load_agent
from insights.runtime.events import EventEmitter, EventSink
from insights.runtime.graph import build_graph, sqlite_checkpointer
from insights.runtime.limits import EffectiveLimits, compute_recursion_limit
from insights.runtime.scope import RunScope
from insights.runtime.stores import (
    InMemoryAuditSink,
    InMemoryResultStore,
    MonotonicDeadline,
    TokenMeter,
)
from insights.skills_core.protocols import Services
from insights.skills_core.registry import SkillRegistry

ROOT = Path(__file__).resolve().parents[2]
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

DESIGN_SUBJECT = "svc-prd-design"
DESIGN_TENANT = "svc-internal"
DEFAULT_RUN_TOKEN_BUDGET = 900_000
"""Prompt + completion tokens one whole PRD design run may spend across every agent stage.
Override with INSIGHTS_PRD_TOKEN_BUDGET; the agent definition's max_tokens is a second cap.
Sizing for the RAIN spec (6 personas): stage 1 ~120k + 6 question runs ~180k + entities ~60k
+ scenario ~40k + 6 ontology runs ~300k leaves ~200k headroom for one audit loop-back."""
RETENTION_DAYS = 7
"""Checkpoint databases older than this are pruned at run start: they hold PRD content."""


# ---- document and schema loading (no database is ever touched here) ------------------------


def read_document(path: Path) -> str:
    """Extract text from DOCX, Markdown, or plain text."""
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8")
    if suffix != ".docx":
        raise ValueError("supported PRD formats are .docx, .md, and .txt")
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    body = root.find(f"{{{W_NS}}}body")
    if body is None:
        raise ValueError("DOCX has no document body")
    blocks: list[str] = []
    for child in body:
        if child.tag == f"{{{W_NS}}}p":
            text = "".join(node.text or "" for node in child.iter(f"{{{W_NS}}}t")).strip()
            if text:
                blocks.append(text)
        elif child.tag == f"{{{W_NS}}}tbl":
            for row in child.findall(f"{{{W_NS}}}tr"):
                cells = []
                for cell in row.findall(f"{{{W_NS}}}tc"):
                    text = " ".join(
                        "".join(node.text or "" for node in paragraph.iter(f"{{{W_NS}}}t")).strip()
                        for paragraph in cell.findall(f"{{{W_NS}}}p")
                    ).strip()
                    cells.append(text)
                blocks.append(" | ".join(cells))
    return "\n".join(blocks)


def read_csv_schema(directory: Path) -> dict[str, list[str]]:
    schema: dict[str, list[str]] = {}
    if not directory.is_dir():
        return schema
    for path in sorted(directory.glob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            schema[path.stem] = next(csv.reader(handle), [])
    return schema


def read_catalog_schema(path: Path) -> dict[str, list[str]]:
    if not path.is_file():
        return {}
    from insights.catalog.snapshot import load_snapshot

    snapshot = load_snapshot(path)
    return {table.name: [column.name for column in table.columns] for table in snapshot.tables}


# ---- governed access -------------------------------------------------------------------------


class DesignRuntime:
    """Governed LLM access for the PRD design agents: LLMGateway under the `design` purpose, a
    least-privilege service principal (no roles, no entitlements, no database reach), the
    response cache disabled so PRD content is never stored, and one shared token meter so the
    run budget is enforced across stages."""

    def __init__(self, environ: dict[str, str], *, app_path: Path | None = None) -> None:
        config = GatewayConfig.from_env(environ)
        config = config.model_copy(
            update={"timeout_s": max(config.timeout_s, 900.0), "cache_ttl_seconds": 0}
        )
        self.gateway = build_gateway(config)
        self.app = load_app_profile(app_path or ROOT / "apps" / "rain" / "app.yaml")
        self.principal = Principal(
            subject=DESIGN_SUBJECT,
            tenant=DESIGN_TENANT,
            roles=(),
            entitlement_digest=hashlib.sha256(
                f"{DESIGN_SUBJECT}:no-entitlements".encode("utf-8")
            ).hexdigest(),
        )
        self.meter = TokenMeter()
        raw_budget = (environ.get("INSIGHTS_PRD_TOKEN_BUDGET") or "").strip()
        self.run_token_budget = int(raw_budget) if raw_budget.isdigit() else DEFAULT_RUN_TOKEN_BUDGET

    def usage_report(self) -> dict[str, int]:
        usage = self.meter.total()
        return {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total": usage.total,
            "run_token_budget": self.run_token_budget,
        }


# ---- the runner -------------------------------------------------------------------------------


def _write_yaml(path: Path, value: Any) -> None:
    path.write_text(yaml.safe_dump(value, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def prune_checkpoints(output_dir: Path, *, now: float | None = None) -> None:
    checkpoints = output_dir / "checkpoints"
    if not checkpoints.is_dir():
        return
    cutoff = (now or time.time()) - RETENTION_DAYS * 86_400
    for path in checkpoints.glob("*.sqlite"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            pass


class PrdRunner:
    def __init__(
        self,
        environ: dict[str, str],
        *,
        root: Path = ROOT,
        agent_path: Path | None = None,
        app_path: Path | None = None,
        design: DesignRuntime | None = None,
        registry: SkillRegistry | None = None,
    ) -> None:
        self.root = root
        self.design = design or DesignRuntime(environ, app_path=app_path)
        self.registry = registry or SkillRegistry.scan(root / "skills")
        self.agent = load_agent(agent_path or root / "agents" / "prd-agent.yaml")
        assert_valid_agent(self.agent, self.registry)

    def run(
        self,
        input_path: Path,
        output_dir: Path,
        *,
        csv_dir: Path,
        catalog_path: Path,
        existing_upper_path: Path | None = None,
        db_state_path: Path | None = None,
        run_id: str | None = None,
        resume: bool = False,
        event_sink: EventSink | None = None,
    ) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        prune_checkpoints(output_dir)
        run_id = run_id or uuid.uuid4().hex
        checkpoint_path = output_dir / "checkpoints" / f"{run_id}.sqlite"
        if resume and not checkpoint_path.is_file():
            raise ValueError(f"nothing to resume: no checkpoint for run {run_id}")

        document = read_document(input_path)
        if not document.strip():
            raise ValueError("input document contains no text")
        source_hash = hashlib.sha256(document.encode("utf-8")).hexdigest()
        db_state = None
        if db_state_path:
            loaded = yaml.safe_load(db_state_path.read_text(encoding="utf-8"))
            db_state = loaded if isinstance(loaded, dict) else {"tables": loaded}
            db_state = {"synthetic": True, "source": "supplied_synthetic_state", **db_state}
        existing_upper = (
            json.loads(existing_upper_path.read_text(encoding="utf-8"))
            if existing_upper_path
            else None
        )
        run_input = {
            "document": document,
            "document_name": input_path.name,
            "source_sha256": source_hash,
            "source_schema": read_csv_schema(csv_dir),
            "catalog_schema": read_catalog_schema(catalog_path),
            "existing_upper_ontology": existing_upper,
            "db_state": db_state,
        }

        events_path = output_dir / "events.jsonl"

        def jsonl_sink(event: StageEvent) -> None:
            with open(events_path, "a", encoding="utf-8") as handle:
                handle.write(event.model_dump_json() + "\n")

        sinks = [jsonl_sink] + ([event_sink] if event_sink else [])
        emitter = EventEmitter(sinks, run_id)
        trace_id = uuid.uuid4().hex
        now = lambda: datetime.now(UTC)  # noqa: E731
        emitter.emit(
            StageEvent(
                type=EventType.GRAPH_DEFINITION,
                run_id=run_id,
                trace_id=trace_id,
                ts=now(),
                steps=tuple(step.id for step in self.agent.steps),
                agent_name=self.agent.name,
                agent_version=self.agent.version,
            )
        )

        budget = min(self.design.run_token_budget, self.agent.limits.max_tokens)
        scope = RunScope(
            run_id=run_id,
            trace_id=trace_id,
            thread_id=run_id,
            registry=self.registry,
            gateway=self.design.gateway,
            audit=InMemoryAuditSink(),
            results=InMemoryResultStore(),
            meter=self.design.meter,
            deadline=MonotonicDeadline(time.monotonic, self.agent.limits.deadline_ms),
            emitter=emitter,
            principal=self.design.principal,
            app=self.design.app,
            limits=EffectiveLimits(
                max_refines=self.agent.limits.max_refines,
                max_tokens=budget,
                deadline_ms=self.agent.limits.deadline_ms,
            ),
            clock=time.monotonic,
            now=now,
            services=Services(),
        )
        checkpointer = sqlite_checkpointer(checkpoint_path)
        compiled = build_graph(self.agent, checkpointer=checkpointer)
        initial = None if resume else {
            "input": run_input,
            "steps": {},
            "exec_counts": {},
            "refine": {
                "attempt": 0,
                "max_refines": self.agent.limits.max_refines,
                "critique": None,
                "history": [],
                "exhausted": False,
                "tokens_used": 0,
            },
            "trace": [],
            "fanout": {},
            "failure": None,
        }
        limit = compute_recursion_limit(
            len(self.agent.steps),
            self.agent.limits.max_refines,
            map_steps=sum(1 for step in self.agent.steps if step.map is not None),
        )
        started = time.monotonic()
        try:
            outcome = compiled.execute(initial, scope, limit, resume=resume)
        finally:
            # Windows keeps the file locked while the connection is open; close it even on an
            # interrupt so the checkpoint can be deleted or resumed
            connection = getattr(checkpointer, "conn", None)
            if connection is not None:
                connection.close()
        state = outcome.state or {}
        failure = state.get("failure")
        if outcome.recursion_limit_hit:
            failure = {"reason": "recursion_limit", "step_id": None, "message": "superstep bound hit"}
        if outcome.error is not None:
            failure = {
                "reason": "internal",
                "step_id": None,
                "message": f"{type(outcome.error).__name__}: {outcome.error}",
            }

        report = self._write_artifacts(output_dir, state, run_id, source_hash, failure, started)
        emitter.emit(
            StageEvent(
                type=EventType.RUN_FINISHED,
                run_id=run_id,
                trace_id=trace_id,
                ts=now(),
                duration_ms=round((time.monotonic() - started) * 1000),
                outcome="completed" if report["completed"] else "failed",
                tokens=self.design.meter.total(),
            )
        )
        if report["completed"] and not failure:
            try:  # the checkpoint holds PRD content; a finished run does not need it
                checkpoint_path.unlink(missing_ok=True)
            except OSError:
                pass
        return report

    def _write_artifacts(
        self,
        output_dir: Path,
        state: dict[str, Any],
        run_id: str,
        source_hash: str,
        failure: dict[str, Any] | None,
        started: float,
    ) -> dict[str, Any]:
        steps = state.get("steps") or {}

        def output_of(step_id: str) -> dict[str, Any]:
            record = steps.get(step_id) or {}
            out = record.get("output") if isinstance(record, dict) else None
            return out if isinstance(out, dict) else {}

        requirements = output_of("requirements").get("requirements_ir")
        if isinstance(requirements, dict):
            _write_yaml(output_dir / "requirements-ir.yaml", requirements)
        registry = output_of("questions_reduce").get("question_registry")
        if isinstance(registry, dict):
            _write_yaml(output_dir / "question-registry.yaml", registry)
        entity_model = output_of("entities").get("entity_model")
        if isinstance(entity_model, dict):
            _write_yaml(output_dir / "entity-model.yaml", entity_model)
        datamap = output_of("datamap")
        if isinstance(datamap.get("lower_ontology"), dict):
            _write_json(output_dir / "lower-ontology.json", datamap["lower_ontology"])
        if isinstance(datamap.get("schema_audit"), dict):
            _write_json(output_dir / "schema-audit.json", datamap["schema_audit"])
        scenario = output_of("scenario").get("scenario")
        if isinstance(scenario, dict):
            _write_yaml(
                output_dir / "scenario.yaml",
                {"synthetic": True, "db_state_source": "generated_from_entity_model", **scenario},
            )
        reduce_out = output_of("ontology_reduce")
        if isinstance(reduce_out.get("upper_ontology"), dict):
            _write_json(output_dir / "upper-ontology.json", reduce_out["upper_ontology"])
        if isinstance(reduce_out.get("ontology_audit"), dict):
            _write_json(output_dir / "ontology-audit.json", reduce_out["ontology_audit"])

        run_report = output_of("finalize").get("run_report") or {}
        completed = bool(run_report.get("completed")) and failure is None
        report = {
            "run_id": run_id,
            "agent": {"name": self.agent.name, "version": self.agent.version},
            "source_sha256": source_hash,
            "completed": completed,
            "failure": failure,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "llm_usage": self.design.usage_report(),
            **run_report,
        }
        _write_json(output_dir / "run-report.json", report)
        return report
