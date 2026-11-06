"""Agent acceptance criteria, evaluated at the end of a run.

YAML (agent level):
    acceptance:
      schema: domain-model.v1.json             # JSON Schema file in DIF_CONTRACTS_DIR, validated against the run output
      min_confidence: {path: $.steps.validate.output.confidence, value: 0.8}
      required_outputs: [tables, lineage]      # output keys that must be present and non-empty
      required_true: [$.steps.validate.output.passed]   # "$." references that must resolve to boolean true
      required_artifacts: [domain_model]       # artifact kinds the run must have persisted (skipped on dry runs)
A failed acceptance fails the run (status failed, error "acceptance failed: ...") but keeps the output and the report
in run.state.acceptance so the result can be inspected."""
import json
from pathlib import Path

import jsonschema


def load_contract(contracts_dir: Path, name: str) -> dict:
    p = Path(contracts_dir) / name
    if not p.exists():
        raise FileNotFoundError(f"contract '{name}' not found in {contracts_dir}")
    return json.loads(p.read_text())


def validate_acceptance(cfg: dict, contracts_dir: Path):
    acc = cfg.get("acceptance")
    if acc is None:
        return
    if not isinstance(acc, dict):
        raise ValueError("acceptance must be a mapping")
    if "schema" in acc:
        jsonschema.Draft202012Validator.check_schema(load_contract(contracts_dir, acc["schema"]))
    mc = acc.get("min_confidence")
    if mc is not None and not (isinstance(mc, dict) and isinstance(mc.get("path"), str) and mc["path"].startswith("$.")
                               and isinstance(mc.get("value"), (int, float))):
        raise ValueError("acceptance.min_confidence needs {path: '$.…', value: <number>}")
    for k in ("required_outputs", "required_artifacts", "required_true"):
        if k in acc and not isinstance(acc[k], list):
            raise ValueError(f"acceptance.{k} must be a list")
    for ref in acc.get("required_true", []):
        if not (isinstance(ref, str) and ref.startswith("$.")):
            raise ValueError("acceptance.required_true entries must be \"$.\" references")


def _get(path, input_, steps, output):
    cur = {"input": input_, "steps": steps, "output": output}
    for p in path[2:].split("."):
        cur = cur.get(p) if isinstance(cur, dict) else None
    return cur


def check_acceptance(acc: dict, output: dict, published: list, input_: dict, steps: dict, contracts_dir: Path, dry_run=False) -> dict:
    checks = []
    if "schema" in acc:
        errors = sorted(jsonschema.Draft202012Validator(load_contract(contracts_dir, acc["schema"])).iter_errors(output or {}),
                        key=lambda e: list(e.path))
        checks.append({"name": f"schema:{acc['schema']}", "passed": not errors,
                       "detail": [f"{'/'.join(map(str, e.path)) or '$'}: {e.message}" for e in errors[:10]]})
    if acc.get("min_confidence"):
        mc = acc["min_confidence"]
        val = _get(mc["path"], input_, steps, output)
        ok = isinstance(val, (int, float)) and val >= mc["value"]
        checks.append({"name": "min_confidence", "passed": ok, "detail": f"{mc['path']} = {val!r}, required >= {mc['value']}"})
    for ref in acc.get("required_true", []):
        val = _get(ref, input_, steps, output)
        checks.append({"name": f"true:{ref}", "passed": val is True, "detail": f"{ref} = {val!r}"})
    for key in acc.get("required_outputs", []):
        v = (output or {}).get(key)
        checks.append({"name": f"output:{key}", "passed": v not in (None, "", [], {}), "detail": "present" if v else "missing or empty"})
    if not dry_run:
        for kind in acc.get("required_artifacts", []):
            checks.append({"name": f"artifact:{kind}", "passed": kind in published,
                           "detail": "persisted" if kind in published else f"not persisted (have {published})"})
    return {"passed": all(c["passed"] for c in checks), "checks": checks}
