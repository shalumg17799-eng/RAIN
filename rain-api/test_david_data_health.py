"""
Tests for david_data_health.py (the Data Health board + Reconciliation
Breakdown, the first two Tier-1 static-to-live conversions).   Run:
    python test_david_data_health.py
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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import david_data_health as dh  # noqa: E402

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


# ------------------------------------------------------------- data health board


@check("source_count and the source list match DataSourceFeed exactly (12 rows, no silent drops)")
def _():
    board = dh.get_data_health_board()
    names = sql("SELECT source_name FROM DataSourceFeed")
    assert board["source_count"] == len(names) == 12
    assert len(board["sources"]) == 12
    assert {s["name"] for s in board["sources"]} == {dh.SOURCE_LABELS.get(n[0], n[0]) for n in names}


@check("every source's status is re-derivable from its own conformance% and lag status")
def _():
    board = dh.get_data_health_board()
    by_label = {s["name"]: s for s in board["sources"]}
    for name, pct, lag_h, lag_status in sql("SELECT source_name, fhir_conformance_pct, pipeline_freshness_hours, ingestion_lag_status FROM DataSourceFeed"):
        label = dh.SOURCE_LABELS.get(name, name)
        pct, lag_h = float(pct), float(lag_h)
        expect = "red" if (lag_status == "delayed" or pct < 90) else "yellow" if pct < 97 else "green"
        assert by_label[label]["status"] == expect, (label, by_label[label]["status"], expect)
    reds = {s["name"] for s in board["sources"] if s["status"] == "red"}
    assert reds == {"RPM Platform", "New Rural Clinic EHR"}  # the two verified delayed feeds


@check("avg FHIR conformance and avg pipeline lag match a hand-computed average over all 12 feeds")
def _():
    board = dh.get_data_health_board()
    rows = sql("SELECT fhir_conformance_pct, pipeline_freshness_hours FROM DataSourceFeed")
    avg_pct = sum(float(r[0]) for r in rows) / len(rows)
    avg_lag = sum(float(r[1]) for r in rows) / len(rows)
    assert board["stats"][0]["value"] == f"{avg_pct:.0f}%"
    assert board["stats"][1]["value"] == f"{avg_lag:.1f} hrs"


@check("the board's unresolved-refs stat equals the verified 1,240 figure, counted independently")
def _():
    board = dh.get_data_health_board()
    n = sql("SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status = 'unresolved'")[0][0]
    assert n == 1240
    assert board["stats"][2]["value"] == f"{n:,}"


@check("the board is deterministic across repeated calls")
def _():
    assert dh.get_data_health_board() == dh.get_data_health_board()


# ------------------------------------------------------------- reconciliation breakdown


@check("the three type counts sum to exactly 1,240, independently re-queried per type")
def _():
    recon = dh.get_reconciliation_breakdown()
    assert recon["total"] == 1240
    by_label = {t["label"]: t["count"] for t in recon["types"]}
    expect = {"Orders": 433, "Encounters": 419, "Pending claims": 388}
    assert by_label == expect, by_label
    for src, label in (("order", "Orders"), ("encounter", "Encounters"), ("pending_claim", "Pending claims")):
        n = sql("SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status='unresolved' AND source_table=?", src)[0][0]
        assert n == expect[label], (src, n, expect[label])


@check("types are sorted by count descending (matches the card's visual bar-chart ordering)")
def _():
    counts = [t["count"] for t in dh.get_reconciliation_breakdown()["types"]]
    assert counts == sorted(counts, reverse=True)


@check("crosswalk_mismatches equals the verified 180 figure, from the same table under a different status")
def _():
    recon = dh.get_reconciliation_breakdown()
    n = sql("SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status = 'mismatched'")[0][0]
    assert n == 180
    assert recon["crosswalk_mismatches"] == n


@check("deactivation_date matches the earliest deactivated provider in Provider, not a hand-typed date")
def _():
    recon = dh.get_reconciliation_breakdown()
    d = sql("SELECT MIN(deactivation_date) FROM Provider WHERE status='deactivated'")[0][0]
    assert recon["deactivation_date"] == d == "2026-03-01"


@check("the static card's invented 620/410/210 breakdown is NOT what this returns (confirms it's really computed, not copied)")
def _():
    counts = {t["count"] for t in dh.get_reconciliation_breakdown()["types"]}
    assert counts != {620, 410, 210}
    assert counts == {433, 419, 388}


# ------------------------------------------------------------- HTTP layer


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

        @check("HTTP: POST /api/v2/generic (DataHealthBoard) returns the live board")
        def _():
            status, body = generic("DataHealthBoard", "david")
            assert status == 200 and body["source_count"] == 12 and body["stats"][2]["value"] == "1,240"

        @check("HTTP: POST /api/v2/generic (ReconciliationBreakdown) returns the live breakdown")
        def _():
            status, body = generic("ReconciliationBreakdown", "david")
            assert status == 200 and body["total"] == 1240 and body["crosswalk_mismatches"] == 180

        @check("HTTP: the existing chat pipeline and action packages are unaffected")
        def _():
            req = urllib.request.Request(base + "/api/v2/ask", method="POST", headers={"Content-Type": "application/json"},
                                         data=json.dumps({"market": "healthcare", "product": "rain", "persona": "david", "query": "crosswalk mismatches"}).encode())
            with urllib.request.urlopen(req, timeout=20) as r:
                out = json.loads(r.read())
            assert r.status == 200 and "180" in json.dumps(out)
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
