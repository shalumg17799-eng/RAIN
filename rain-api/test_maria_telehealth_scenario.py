"""
Tests for maria_telehealth_scenario.py.   Run:  python test_maria_telehealth_scenario.py
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
import maria_telehealth_scenario as ts  # noqa: E402
import maria_action_package as m  # noqa: E402

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


@check("assignment split (8/3/3) matches the action package's own intervention summary exactly")
def _():
    r = ts.get_telehealth_scenario()
    pkg_s = m.build_maternal_package()["summary"]["interventions"]
    by_label = {a["label"]: a["count"] for a in r["assignments"]}
    assert by_label == {"Telehealth": 8, "Hybrid + NEMT": 3, "In-person only": 3}
    assert by_label == {"Telehealth": pkg_s["telehealth"], "Hybrid + NEMT": pkg_s["hybrid_nemt"], "In-person only": pkg_s["in_person"]}
    assert sum(a["count"] for a in r["assignments"]) == r["total"] == 14


@check("documented_trend matches MetricTrend exactly, independently re-queried")
def _():
    r = ts.get_telehealth_scenario()
    row = sql("SELECT before_value, after_value, before_date, after_date FROM MetricTrend WHERE metric_id='prenatal_completion_rate'")[0]
    assert (int(row[0]), int(row[1]), row[2], row[3]) == (84, 61, "2026-01-30", "2026-05-15")
    dt = r["documented_trend"]
    assert (dt["before"], dt["after"], dt["before_date"], dt["after_date"]) == (84, 61, "2026-01-30", "2026-05-15")


@check("live_snapshot matches the already-verified 'Prenatal completion rate current' business rule exactly")
def _():
    r = ts.get_telehealth_scenario()
    from business_rules import BUSINESS_RULES
    rule = next(x for x in BUSINESS_RULES if x["term"] == "Prenatal completion rate current")
    expect = sql(rule["sql"])[0][0]
    assert expect == 84
    assert r["live_snapshot"]["value"] == 84


@check("the discrepancy between the documented trend (61%) and the live snapshot (84%) is flagged true, not hidden")
def _():
    r = ts.get_telehealth_scenario()
    assert r["discrepancy"] is True
    assert "84" in r["note"] and "61" in r["note"]


@check("no fabricated 30-day forecast figures appear in any numeric data field")
def _():
    r = ts.get_telehealth_scenario()
    numbers = {a["count"] for a in r["assignments"]} | {r["documented_trend"]["before"], r["documented_trend"]["after"], r["live_snapshot"]["value"]}
    assert numbers.isdisjoint({72, 82, 88, 59, 57, 55}), numbers
    assert numbers == {8, 3, 84, 61}


@check("deterministic across repeated calls")
def _():
    assert ts.get_telehealth_scenario() == ts.get_telehealth_scenario()


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

        @check("HTTP: POST /api/v2/generic (TelehealthScenario) returns the live card with both figures and the flag")
        def _():
            status, body = generic("TelehealthScenario", "maria")
            assert status == 200 and body["documented_trend"]["after"] == 61 and body["live_snapshot"]["value"] == 84 and body["discrepancy"] is True

        @check("HTTP: all prior live cards remain unaffected")
        def _():
            assert generic("MaternalRiskStratification", "maria")[0] == 200
            assert generic("RiskTieredOutreach", "sarah")[0] == 200
            with urllib.request.urlopen(base + "/ultra/rain/maria/actionPackage", timeout=10) as r:
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
