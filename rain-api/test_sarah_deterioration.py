"""
Tests for sarah_deterioration_live.py.   Run:  python test_sarah_deterioration.py
"""

import json
import os
import subprocess
import sys
import pg_compat
import time
import traceback
import urllib.error
import urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sarah_deterioration_live as sd  # noqa: E402

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


# ----------------------------------------------------------------- cohort


@check("the 17-patient cohort matches the verified 'CHF COPD worsening' rule exactly, same ids")
def _():
    from business_rules import BUSINESS_RULES
    rule = next(r for r in BUSINESS_RULES if r["term"] == "CHF COPD worsening RPM deterioration cluster")
    expect = sql(rule["sql"])[0][0]
    board = sd.get_deterioration_board()
    assert expect == 17 and board["total"] == 17
    ids = {p["id"] for p in board["patients"]}
    real_ids = {r[0] for r in sql("SELECT DISTINCT patient_id FROM RPMReading WHERE condition_type IN ('CHF','COPD')")}
    assert ids == real_ids and len(ids) == 17


@check("the 11 weight-up / 6 SpO2-down split matches the static card's header exactly, re-derived independently")
def _():
    board = sd.get_deterioration_board()
    chf = sql("SELECT COUNT(DISTINCT patient_id) FROM RPMReading WHERE condition_type='CHF'")[0][0]
    copd = sql("SELECT COUNT(DISTINCT patient_id) FROM RPMReading WHERE condition_type='COPD'")[0][0]
    assert (chf, copd) == (11, 6)
    assert (board["weight_up"], board["spo2_down"]) == (11, 6)
    for p in board["patients"]:
        assert (p["cond"] == "CHF") == (p["marker"] == "weight")
        assert (p["cond"] == "COPD") == (p["marker"] == "spo2")


# -------------------------------------------------------- per-patient flags


@check("med_gap is independently re-derived per patient (>30 days since last fill)")
def _():
    board = sd.get_deterioration_board()
    by_id = {p["id"]: p for p in board["patients"]}
    for pid, fill_date in sql("SELECT patient_id, MAX(fill_date) FROM MedicationFill WHERE patient_id IN "
                              "(SELECT DISTINCT patient_id FROM RPMReading WHERE condition_type IN ('CHF','COPD')) GROUP BY patient_id"):
        gap = (date(2026, 5, 15) - date.fromisoformat(fill_date)).days
        assert by_id[pid]["med_gap"] == (gap > 30), (pid, gap, by_id[pid]["med_gap"])


@check("reassigned is independently re-derived per patient (assigned provider is deactivated)")
def _():
    board = sd.get_deterioration_board()
    by_id = {p["id"]: p for p in board["patients"]}
    for pid in by_id:
        enr = sql("SELECT assigned_provider_id FROM ChronicConditionEnrollment WHERE patient_id=? LIMIT 1", pid)
        expect = False
        if enr:
            prov = sql("SELECT status FROM Provider WHERE provider_id=?", enr[0][0])
            expect = bool(prov) and prov[0][0] == "deactivated"
        assert by_id[pid]["reassigned"] == expect, pid


@check("transport is independently re-derived per patient (SDOH transportation flag)")
def _():
    board = sd.get_deterioration_board()
    by_id = {p["id"]: p for p in board["patients"]}
    flagged = {r[0] for r in sql("SELECT DISTINCT patient_id FROM SDOHFlag WHERE flag_type='transportation' AND patient_id IN "
                                 "(SELECT DISTINCT patient_id FROM RPMReading WHERE condition_type IN ('CHF','COPD'))")}
    for pid, p in by_id.items():
        assert p["transport"] == (pid in flagged), pid


@check("sparkline points come from each patient's own real RPM readings, first and last values preserved")
def _():
    board = sd.get_deterioration_board()
    for p in board["patients"]:
        readings = [float(r[0]) for r in sql("SELECT value FROM RPMReading WHERE patient_id=? AND reading_type=? ORDER BY timestamp", p["id"], p["marker"])]
        assert p["pts"][0] == readings[0] and p["pts"][-1] == readings[-1], p["id"]
        assert len(p["pts"]) <= 6


# -------------------------------------------------- the two corrected figures


@check("med_gap_count is 9, matching the PRD's 9 of 17")
def _():
    board = sd.get_deterioration_board()
    n = sql("SELECT COUNT(*) FROM MedicationFill m WHERE m.patient_id IN "
            "(SELECT DISTINCT patient_id FROM RPMReading WHERE condition_type IN ('CHF','COPD')) "
            "AND julianday('2026-05-15') - julianday(m.fill_date) > 30")[0][0]
    assert n == 9
    assert board["med_gap_count"] == 9


@check("reassigned_count is the verified 5 -- the one static-card figure that was actually correct")
def _():
    board = sd.get_deterioration_board()
    assert board["reassigned_count"] == 5


@check("silent_count is 0 -- NOT the static card's fictional 'PT with 24d silence' badge")
def _():
    board = sd.get_deterioration_board()
    assert board["silent_count"] == 0
    assert all(p["silent"] is False for p in board["patients"])
    # independently confirm every one of the 17 has an RPM reading dated today
    for pid in [p["id"] for p in board["patients"]]:
        last = sql("SELECT MAX(timestamp) FROM RPMReading WHERE patient_id=?", pid)[0][0]
        assert last[:10] == "2026-05-15", pid


@check("the board is deterministic across repeated calls")
def _():
    assert sd.get_deterioration_board() == sd.get_deterioration_board()


# ------------------------------------------------------------------- HTTP layer


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

        @check("HTTP: POST /api/v2/generic (DeteriorationBoard) returns the live, corrected board")
        def _():
            status, body = generic("DeteriorationBoard", "sarah")
            assert status == 200 and body["total"] == 17 and body["med_gap_count"] == 9 and body["silent_count"] == 0

        @check("HTTP: the existing chat pipeline and all prior live cards are unaffected")
        def _():
            req = urllib.request.Request(base + "/api/v2/ask", method="POST", headers={"Content-Type": "application/json"},
                                         data=json.dumps({"market": "healthcare", "product": "rain", "persona": "sarah", "query": "chronic disease patients worsening RPM"}).encode())
            with urllib.request.urlopen(req, timeout=20) as r:
                assert r.status == 200
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
