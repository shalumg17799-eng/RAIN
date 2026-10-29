import re

import jsonschema

from dif.config import settings
from dif.runtime.acceptance import load_contract

_TOK = re.compile(r"([^\[\]]*)((?:\[(?:\*|\d+)\])*)")
_EMPTY = (None, "", [], {})


def walk(obj, path):
    """All values at a "$.a.b[*].c" path; `[*]` expands lists (and dict values), `[n]` indexes a list."""
    vals = [obj]
    for tok in [t for t in str(path).removeprefix("$").strip(".").split(".") if t]:
        key, idx = _TOK.fullmatch(tok).groups()
        if key:
            vals = [v[key] for v in vals if isinstance(v, dict) and key in v]
        for i in re.findall(r"\[(\*|\d+)\]", idx):
            if i == "*":
                vals = [x for v in vals for x in (v if isinstance(v, list) else list(v.values()) if isinstance(v, dict) else [])]
            else:
                vals = [v[int(i)] for v in vals if isinstance(v, list) and int(i) < len(v)]
    return vals


def _check(name, ok, detail):
    return {"name": name, "passed": bool(ok), "detail": detail}


def run(inp, ctx):
    subject = inp["subject"]
    if not isinstance(subject, dict):
        raise ValueError("subject must be an object")
    checks = [_check("subject:non_empty", subject, f"{len(subject)} top-level key(s)")]
    if inp.get("contract"):
        name = f"schema:{inp['contract']}"
        try:
            errors = sorted(jsonschema.Draft202012Validator(load_contract(settings.contracts_dir, inp["contract"])).iter_errors(subject),
                            key=lambda e: list(e.path))
            checks.append(_check(name, not errors, [f"{'/'.join(map(str, e.path)) or '$'}: {e.message}" for e in errors[:10]]))
        except FileNotFoundError as e:
            checks.append(_check(name, False, str(e)))
    for path, minimum in (inp.get("thresholds") or {}).items():
        vals = walk(subject, path)
        nums = [v for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
        ok = bool(nums) and len(nums) == len(vals) and all(v >= minimum for v in nums)
        checks.append(_check(f"threshold:{path}", ok, f"values {vals[:10]!r}, required >= {minimum}" if vals else f"{path} not found"))
    for key in inp.get("required_keys") or []:
        present = subject.get(key) not in _EMPTY
        checks.append(_check(f"key:{key}", present, "present" if present else "missing or empty"))
    for ref in inp.get("cross_refs") or []:
        src, dst = ref.get("from"), ref.get("in")
        targets = {str(v) for v in walk(subject, dst)}
        missing = sorted({str(v) for v in walk(subject, src)} - targets)
        checks.append(_check(f"cross_ref:{src}->{dst}", not missing, f"missing {missing[:10]}" if missing else f"{len(targets)} target(s)"))
    findings = [{"severity": "error", "message": f"{c['name']}: {c['detail']}"} for c in checks if not c["passed"]]
    if len(checks) == 1:
        findings.append({"severity": "info", "message": "no contract, thresholds, required keys or cross references configured"})
    return {"passed": all(c["passed"] for c in checks), "score": round(sum(c["passed"] for c in checks) / len(checks), 3),
            "checks": checks, "findings": findings, "judge": None}
