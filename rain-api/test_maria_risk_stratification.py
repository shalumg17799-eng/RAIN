"""
Tests for maria_risk_stratification.py.   Run:  python test_maria_risk_stratification.py
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
import maria_risk_stratification as ms  # noqa: E402
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


@check("all 14 patients present, same cohort as the verified action package")
def _():
    r = ms.get_maternal_risk_stratification()
    pkg_ids = {p["patient_id"] for p in m.build_maternal_package()["patients"]}
    assert r["total"] == 14 and {p["id"] for p in r["patients"]} == pkg_ids


@check("dx breakdown matches independent SQL exactly: 4 preeclampsia, 3 gestational DM, 2 prior preterm, 9 total")
def _():
    r = ms.get_maternal_risk_stratification()
    counts = sql("SELECT risk_diagnoses, COUNT(*) FROM PregnancyEpisode WHERE trimester=3 AND distance_to_delivery_miles=115 "
                 "AND risk_diagnoses != '' GROUP BY 1")
    expect = {"preeclampsia": 4, "gestational diabetes": 3, "prior preterm birth": 2}
    assert {c[0]: c[1] for c in counts} == expect
    assert {d["label"]: d["count"] for d in r["dx_breakdown"]} == {"Preeclampsia": 4, "Gestational DM": 3, "Prior preterm": 2}
    assert r["dx_total"] == 9


@check("missed-visit total is the independently verified 6")
def _():
    r = ms.get_maternal_risk_stratification()
    n = sql("SELECT COUNT(*) FROM PregnancyEpisode WHERE trimester=3 AND distance_to_delivery_miles=115 AND last_prenatal_visit_date < '2026-04-01'")[0][0]
    assert n == 6 and r["missed_total"] == 6


@check("distance is the real constant 115 for every patient, NOT the static card's invented 109-132 variation")
def _():
    r = ms.get_maternal_risk_stratification()
    assert r["distance_miles"] == 115
    assert all(p["miles"] == 115 for p in r["patients"])
    distinct = sql("SELECT DISTINCT distance_to_delivery_miles FROM PregnancyEpisode WHERE trimester=3 AND distance_to_delivery_miles=115")
    assert len(distinct) == 1


@check("risk scores and ranking match the action package's own _factors()/risk_score exactly (same patient, same score)")
def _():
    r = ms.get_maternal_risk_stratification()
    pkg = m.build_maternal_package()
    pkg_scores = {p["patient_id"]: p["risk_score"] for p in pkg["patients"]}
    for p in r["patients"]:
        assert p["score"] == pkg_scores[p["id"]], p["id"]
        assert p["score_max"] == 5


@check("exactly 3 patients compound a chronic condition, matching the action package's chronic_handoff count")
def _():
    r = ms.get_maternal_risk_stratification()
    compounding = [p for p in r["patients"] if p["compound"]]
    assert len(compounding) == 3
    n = sql("SELECT COUNT(DISTINCT patient_id) FROM ChronicConditionEnrollment WHERE patient_id IN "
            "(SELECT patient_id FROM PregnancyEpisode WHERE trimester=3 AND distance_to_delivery_miles=115)")[0][0]
    assert n == 3


@check("bp_series has exactly 2 entries (not 3) -- the diabetes compounding patient has no RPM data and is excluded, not faked")
def _():
    r = ms.get_maternal_risk_stratification()
    assert len(r["bp_series"]) == 2
    assert r["no_rpm_compounding"] == ["PT-00003"]
    n = sql("SELECT COUNT(*) FROM RPMReading WHERE patient_id='PT-00003'")[0][0]
    assert n == 0


@check("each BP series' points come from that patient's real readings (first/last preserved)")
def _():
    r = ms.get_maternal_risk_stratification()
    for s in r["bp_series"]:
        readings = [float(x[0]) for x in sql("SELECT value FROM RPMReading WHERE patient_id=? AND reading_type='BP' ORDER BY timestamp", s["id"])]
        assert s["pts"][0] == readings[0] and s["pts"][-1] == readings[-1], s["id"]


@check("deterministic across repeated calls")
def _():
    assert ms.get_maternal_risk_stratification() == ms.get_maternal_risk_stratification()


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

        @check("HTTP: POST /api/v2/generic (MaternalRiskStratification) returns the live, corrected card")
        def _():
            status, body = generic("MaternalRiskStratification", "maria")
            assert status == 200 and body["total"] == 14 and body["distance_miles"] == 115 and len(body["bp_series"]) == 2

        @check("HTTP: all prior live cards and Maria's action package remain unaffected")
        def _():
            assert generic("RiskTieredOutreach", "sarah")[0] == 200
            assert generic("DeteriorationBoard", "sarah")[0] == 200
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
