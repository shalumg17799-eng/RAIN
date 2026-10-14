"""
Tests for sarah_risk_tiers.py.   Run:  python test_sarah_risk_tiers.py
"""

import json
import os
import subprocess
import sys
import pg_compat
import time
import traceback
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sarah_risk_tiers as rt  # noqa: E402

DB = os.path.join(HERE, "rain.db")
_results = []


def check(name):
    def deco(fn):
        try:
            fn()
            _results.append((name, True, ""))
        except Exception:
            _results.append((name, False, traceback.format_exc(limit=3)))
        return fn
    return deco


def sql(q, *a):
    c = pg_compat.connect(DB)
    try:
        return c.execute(q, a).fetchall()
    finally:
        c.close()


@check("all 17 patients are scored, tiers sum to 17")
def _():
    result = rt.get_risk_tiered_outreach()
    assert result["total"] == 17
    assert sum(t["count"] for t in result["tiers"]) == 17


@check("Tier 1 is exactly PT-00127..131 (5 patients), matching Sarah's already-verified action-package cohort")
def _():
    result = rt.get_risk_tiered_outreach()
    t1 = next(t for t in result["tiers"] if t["tier"] == "Tier 1")
    assert t1["count"] == 5
    assert sorted(t1["patient_ids"]) == ["PT-00127", "PT-00128", "PT-00129", "PT-00130", "PT-00131"]


@check("Tier 1's transport-barrier note matches the independently verified 4-of-5 figure")
def _():
    result = rt.get_risk_tiered_outreach()
    t1 = next(t for t in result["tiers"] if t["tier"] == "Tier 1")
    n = sql("SELECT COUNT(*) FROM SDOHFlag WHERE flag_type='transportation' AND patient_id IN "
            "('PT-00127','PT-00128','PT-00129','PT-00130','PT-00131')")[0][0]
    assert n == 4
    assert "4" in t1["note"]


@check("the full tier distribution is 5/7/5, matching the PRD")
def _():
    result = rt.get_risk_tiered_outreach()
    counts = {t["tier"]: t["count"] for t in result["tiers"]}
    assert counts == {"Tier 1": 5, "Tier 2": 7, "Tier 3": 5}


@check("tier membership is independently re-derivable from the same scoring logic")
def _():
    result = rt.get_risk_tiered_outreach()
    rows = sql(rt.SCORE_SQL.replace("?", "'2026-05-15'"))
    expect = {}
    for pid, score in rows:
        key = "Tier 1" if score >= 3 else "Tier 2" if score == 2 else "Tier 3"
        expect.setdefault(key, []).append(pid)
    for t in result["tiers"]:
        assert sorted(t["patient_ids"]) == sorted(expect[t["tier"]]), t["tier"]


@check("avoidable-ED figures match the already-verified model exactly: 100 before, 119 after, 76 tied (64%)")
def _():
    result = rt.get_risk_tiered_outreach()
    from business_rules import BUSINESS_RULES
    rule = next(r for r in BUSINESS_RULES if r["term"] == "Avoidable hospitalizations elevated risk cohort")
    b, a, t, rise, tied = sql(rule["sql"])[0]
    assert (b, a, t) == (100, 119, 76)
    ed = result["avoidable_ed"]
    assert (ed["before"], ed["after"], ed["tied_to_deactivated"]) == (100, 119, 76)
    assert ed["rise_pct"] == 19 and ed["pct_tied"] == 64


@check("no probability-band or cost-model figures are present; the limitation is disclosed")
def _():
    result = rt.get_risk_tiered_outreach()
    payload = json.dumps(result)
    assert "60%" not in payload and "30–60%" not in payload and "$1.0M" not in payload and "-45%" not in payload
    assert "no basis" not in result["note"].lower() or "invented" in result["note"].lower()
    assert "probability" in result["note"].lower() or "cost" in result["note"].lower()


@check("deterministic across repeated calls")
def _():
    assert rt.get_risk_tiered_outreach() == rt.get_risk_tiered_outreach()


def http_tests():
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--port", str(port), "--log-level", "warning"], cwd=HERE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/health", timeout=1); break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("server did not start")

        def generic(component, persona):
            body = {"market": "healthcare", "product": "rain", "persona": persona, "category": [{"component": component}]}
            req = urllib.request.Request(base + "/api/v2/generic", method="POST", headers={"Content-Type": "application/json"}, data=json.dumps(body).encode())
            with urllib.request.urlopen(req, timeout=15) as r:
                out = json.loads(r.read())
            return r.status, out["visualization"][0]["data"]

        @check("HTTP: POST /api/v2/generic (RiskTieredOutreach) returns the live, corrected tiers")
        def _():
            status, body = generic("RiskTieredOutreach", "sarah")
            assert status == 200 and body["total"] == 17
            assert {t["tier"]: t["count"] for t in body["tiers"]} == {"Tier 1": 5, "Tier 2": 7, "Tier 3": 5}

        @check("HTTP: all prior live cards remain unaffected")
        def _():
            assert generic("DeteriorationBoard", "sarah")[0] == 200
            assert generic("DataHealthBoard", "david")[0] == 200
            assert generic("OpsTrafficTiles", "james")[0] == 200
            with urllib.request.urlopen(base + "/ultra/rain/sarah/actionPackage", timeout=10) as r:
                assert r.status == 200
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    if "--no-http" not in sys.argv:
        http_tests()
    failed = [r for r in _results if not r[1]]
    for name, ok, err in _results:
        print(("  PASS  " if ok else "  FAIL  ") + name)
        if not ok:
            print("        " + err.strip().replace("\n", "\n        "))
    print(f"\n{len(_results) - len(failed)} of {len(_results)} passed")
    sys.exit(1 if failed else 0)
