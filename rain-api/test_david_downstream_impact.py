"""
Tests for david_downstream_impact.py.   Run:  python test_david_downstream_impact.py
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
import david_downstream_impact as di  # noqa: E402

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


@check("maternal_affected is 0, NOT the static/scripted claim of 6 -- independently re-queried")
def _():
    r = di.get_downstream_impact()
    n = sql("SELECT COUNT(*) FROM PregnancyEpisode WHERE assigned_provider_id IN (SELECT provider_id FROM Provider WHERE status='deactivated')")[0][0]
    assert n == 0
    assert r["maternal_affected"] == 0
    assert "0 prenatal patients" in r["engines"][0]["detail"]
    assert "6" not in r["engines"][0]["detail"]


@check("chronic breakdown matches independent SQL exactly: CHF 5, diabetes 42, hypertension 2, total 49")
def _():
    r = di.get_downstream_impact()
    rows = sql("SELECT condition_type, COUNT(*) FROM ChronicConditionEnrollment WHERE assigned_provider_id IN "
              "(SELECT provider_id FROM Provider WHERE status='deactivated') GROUP BY 1")
    expect = {t: n for t, n in rows}
    assert expect == {"CHF": 5, "diabetes": 42, "hypertension": 2}
    assert r["chronic_by_condition"] == expect
    assert r["chronic_affected"] == 49
    assert "42 diabetes" in r["engines"][1]["detail"] and "2 hypertension" in r["engines"][1]["detail"]


@check("chronic total matches the already-verified 'Patients lost provider deactivated' business rule (49)")
def _():
    r = di.get_downstream_impact()
    from business_rules import BUSINESS_RULES
    rule = next(x for x in BUSINESS_RULES if x["term"] == "Patients lost provider deactivated")
    expect = sql(rule["sql"])[0][0]
    assert expect == 49
    assert r["chronic_affected"] == 49
    # and the codebase's own prior documentation of this figure (independent of this module) matches too
    doc_rule = next(x for x in BUSINESS_RULES if x["term"] == "Lost provider continuity")
    assert "5 CHF, 42 diabetes, 2 hypertension" in doc_rule["verified_result"]


@check("the 64% ED-attribution figure matches the already-verified avoidable-hospitalizations model exactly")
def _():
    r = di.get_downstream_impact()
    ed = sql("SELECT SUM(CASE WHEN date>='2026-03-01' AND rendering_provider_id IN (SELECT provider_id FROM Provider WHERE status='deactivated') THEN 1 ELSE 0 END), "
             "SUM(CASE WHEN date>='2026-03-01' THEN 1 ELSE 0 END) FROM ClaimEncounter WHERE avoidable_ed_flag='True' AND encounter_type != 'ED_delivery_or_BBA'")[0]
    assert ed == (76, 119)
    assert "76 of 119" in r["engines"][2]["detail"] and "64%" in r["engines"][2]["detail"]


@check("unresolved_refs matches the verified 1,240 figure")
def _():
    r = di.get_downstream_impact()
    assert r["unresolved_refs"] == sql("SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status='unresolved'")[0][0] == 1240


@check("no fabricated completeness-bar figures (86%, 99%) appear in any data field")
def _():
    r = di.get_downstream_impact()
    data_only = {k: v for k, v in r.items() if k != "note"}
    payload = json.dumps(data_only)
    assert "86" not in payload and "99" not in payload


@check("deterministic across repeated calls")
def _():
    assert di.get_downstream_impact() == di.get_downstream_impact()


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

        @check("HTTP: POST /api/v2/generic (DownstreamImpact) returns the live, corrected card")
        def _():
            status, body = generic("DownstreamImpact", "david")
            assert status == 200 and body["maternal_affected"] == 0 and body["chronic_affected"] == 49

        @check("HTTP: every prior live card remains unaffected")
        def _():
            for component, persona in (("DataHealthBoard", "david"), ("ReconciliationBreakdown", "david"),
                                       ("TransportQueueBreakdown", "james"), ("RiskTieredOutreach", "sarah"),
                                       ("MaternalRiskStratification", "maria")):
                assert generic(component, persona)[0] == 200, component
            for path in ("/ultra/rain/sarah/actionPackage", "/ultra/rain/maria/actionPackage"):
                with urllib.request.urlopen(base + path, timeout=10) as r:
                    assert r.status == 200, path
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
