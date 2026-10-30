import json
import re

from dif import llm

_KEY = re.compile(r"^[`'\"]?([a-z][a-z0-9_]*)[`'\"]?\b")
SEVERITIES = ("info", "warning", "error")
_EMPTY = (None, "", [], {})


def criteria(rubric):
    items = rubric if isinstance(rubric, list) else re.split(r"\n+|;\s+", str(rubric))
    return [re.sub(r"^[\s\-\*\d.)]+", "", str(c)).strip() for c in items if str(c).strip()]


def _has(subject, key):
    return subject.get(key) not in _EMPTY if isinstance(subject, dict) else key.lower() in str(subject).lower()


def heuristic(subject, crits, reason):
    non_empty = bool(subject) and (not isinstance(subject, str) or bool(subject.strip()))
    checks = [{"name": "subject:non_empty", "passed": non_empty}]
    findings = [{"severity": "info", "message": f"LLM unavailable: heuristic verdict ({reason})"}]
    if not non_empty:
        findings.append({"severity": "error", "message": "subject is empty"})
    keyed = 0
    for c in crits:
        m = _KEY.match(c)
        if not m:
            continue
        keyed += 1
        ok = _has(subject, m.group(1))
        checks.append({"name": f"key:{m.group(1)}", "passed": ok})
        if not ok:
            findings.append({"severity": "warning", "message": f"criterion '{c}': '{m.group(1)}' missing or empty"})
    score = round(sum(c["passed"] for c in checks) / len(checks), 3) if keyed else (0.5 if non_empty else 0.0)
    return {"passed": score >= 0.5, "score": score, "findings": findings, "method": "heuristic", "checks": checks}


def judge(subject, crits, context, threshold):
    body = subject if isinstance(subject, str) else json.dumps(subject, indent=1, default=str)
    reply = llm.complete_json(
        "You are a strict reviewer. Judge the SUBJECT against every RUBRIC criterion. Answer with one JSON object "
        '{"passed": true|false, "score": <0..1>, "findings": [{"severity": "info|warning|error", "message": "..."}]}.'
        "\n\nRUBRIC:\n- " + "\n- ".join(crits) + (f"\n\nCONTEXT:\n{context}" if context else "") + f"\n\nSUBJECT:\n{body[:12000]}",
        default={})
    if not isinstance(reply, dict) or not ({"passed", "score"} & set(reply)):
        raise llm.LLMUnavailable("model reply held no verdict")
    try:
        score = min(1.0, max(0.0, float(reply.get("score", 0))))
    except (TypeError, ValueError):
        score = 0.0
    findings = [{"severity": f.get("severity") if f.get("severity") in SEVERITIES else "info", "message": str(f.get("message", ""))}
                for f in reply.get("findings") or [] if isinstance(f, dict)]
    return {"passed": bool(reply.get("passed")) and score >= threshold, "score": round(score, 3), "findings": findings,
            "method": "llm", "threshold": threshold}


def run(inp, ctx):
    crits = criteria(inp["rubric"])
    if not crits:
        raise ValueError("rubric must contain at least one criterion")
    threshold = float(inp["threshold"]) if inp.get("threshold") is not None else 0.6
    subject = inp["subject"]
    if not llm.available():
        return heuristic(subject, crits, "DIF_LLM_PROVIDER=none")
    try:
        return judge(subject, crits, inp.get("context"), threshold)
    except Exception as e:  # fail soft: heuristic verdict, error recorded
        return {**heuristic(subject, crits, str(e)), "llm_error": str(e)}
