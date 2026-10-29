"""Evaluation framework: dry-run, test execution against expectations, confidence scoring, acceptance reports."""
from dif.runtime.engine import Runtime


def _subset(expected, actual) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and _subset(v, actual[k]) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and all(any(_subset(e, a) for a in actual) for e in expected)
    return expected == actual


def evaluate(runtime: Runtime, agent: str, cases: list[dict], dry_run: bool = True, enterprise: str | None = None) -> dict:
    """cases: [{name, input, expect}] - `expect` is a partial structure that must be contained in the output.
    A case passes when the run succeeded, the expectation matches and (if the agent declares one) acceptance passed."""
    results = []
    for i, case in enumerate(cases):
        run = runtime.start(agent, case["input"], dry_run=dry_run, enterprise=enterprise)
        out = run["output"] or {}
        acceptance = (run.get("state") or {}).get("acceptance")
        passed = run["status"] == "succeeded" and _subset(case.get("expect", {}), out)
        conf = (out.get("validation") or {}).get("confidence", out.get("confidence"))
        results.append({"case": case.get("name", f"case-{i + 1}"), "run_id": run["id"], "status": run["status"],
                        "passed": passed, "confidence": conf if isinstance(conf, (int, float)) else None,
                        "error": run["error"], "acceptance": acceptance,
                        "issues": (out.get("validation") or {}).get("issues", [])})
    scored = [r["confidence"] for r in results if r["confidence"] is not None]
    pass_rate = sum(r["passed"] for r in results) / len(results) if results else 0.0
    with_acc = [r for r in results if r["acceptance"] is not None]
    return {"agent": agent, "dry_run": dry_run, "cases": len(results), "pass_rate": round(pass_rate, 3),
            "mean_confidence": round(sum(scored) / len(scored), 3) if scored else None,
            "acceptance_pass_rate": round(sum(r["acceptance"]["passed"] for r in with_acc) / len(with_acc), 3) if with_acc else None,
            "verdict": "PASS" if results and pass_rate == 1.0 else "FAIL", "results": results}
