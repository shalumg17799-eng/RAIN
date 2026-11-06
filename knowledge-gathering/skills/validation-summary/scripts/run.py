def run(inp, ctx):
    check, judge = inp["check"], inp.get("judge")
    if not isinstance(check, dict) or "passed" not in check:
        raise ValueError("check must be the output of acceptance-check")
    judge = judge if isinstance(judge, dict) else None  # a skipped judge step resolves to null
    scores = [float(check.get("score") or 0)] + ([float(judge.get("score") or 0)] if judge else [])
    return {"passed": bool(check["passed"]) and (bool(judge.get("passed")) if judge else True),
            "score": round(sum(scores) / len(scores), 3), "checks": list(check.get("checks") or []),
            "findings": list(check.get("findings") or []) + (list(judge.get("findings") or []) if judge else []), "judge": judge}
