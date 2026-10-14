"""
Tests for james_ops_live.get_transport_queue_breakdown.   Run:
    python test_james_transport_breakdown.py
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
import james_ops_live as jo  # noqa: E402

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


def columns_of(table):
    return [r[0] for r in sql(
        "SELECT column_name FROM information_schema.columns WHERE table_name = ? ORDER BY ordinal_position",
        table,
    )]


@check("total/scheduled/unscheduled match the verified 73/64/9 figures, independently re-queried")
def _():
    r = jo.get_transport_queue_breakdown()
    total = sql("SELECT COUNT(*) FROM TransportRequest WHERE date='2026-05-15'")[0][0]
    sched = sql("SELECT COUNT(*) FROM TransportRequest WHERE date='2026-05-15' AND scheduled='True'")[0][0]
    assert (total, sched, total - sched) == (73, 64, 9)
    assert (r["total"], r["scheduled"], r["unscheduled"]) == (73, 64, 9)


@check("by_type matches independent SQL exactly: EMS 10, NEMT 63")
def _():
    r = jo.get_transport_queue_breakdown()
    rows = sql("SELECT request_type, COUNT(*) FROM TransportRequest WHERE date='2026-05-15' GROUP BY request_type")
    expect = {t: n for t, n in rows}
    assert expect == {"EMS": 10, "NEMT": 63}
    by_label = {x["label"]: x["count"] for x in r["by_type"]}
    assert by_label == expect
    assert sum(by_label.values()) == r["total"]


@check("no fabricated hourly/capacity/dialysis figures appear in any data field")
def _():
    r = jo.get_transport_queue_breakdown()
    data_only = {k: v for k, v in r.items() if k != "note"}
    payload = json.dumps(data_only)
    for bad in ("dialysis", "8a", "9a", "10a", "11a", "capacity", "double-book"):
        assert bad.lower() not in payload.lower(), bad
    assert set(data_only.keys()) == {"as_of", "total", "scheduled", "unscheduled", "by_type"}


@check("TransportRequest specifically has no hour-of-day, vehicle, or capacity column -- confirms the premise is genuinely unsupported")
def _():
    cols = [c.lower() for c in columns_of("TransportRequest")]
    assert cols == ["request_id", "patient_id", "request_type", "origin_zip", "destination_facility_id", "scheduled", "date"]
    assert not any(w in c for c in cols for w in ("hour", "time", "vehicle", "capacity"))
    # and confirm no table anywhere in the dataset models vehicles or fleet capacity
    for (t,) in sql("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"):
        cols2 = [c.lower() for c in columns_of(t)]
        assert not any("vehicle" in c or "fleet" in c for c in cols2), (t, cols2)


@check("deterministic across repeated calls")
def _():
    assert jo.get_transport_queue_breakdown() == jo.get_transport_queue_breakdown()


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

        @check("HTTP: POST /api/v2/generic (TransportQueueBreakdown) returns the live, real breakdown")
        def _():
            status, body = generic("TransportQueueBreakdown", "james")
            assert status == 200 and body["total"] == 73 and body["scheduled"] == 64

        @check("HTTP: every prior live card across all five modules remains unaffected")
        def _():
            for component, persona in (("OpsTrafficTiles", "james"), ("TripTelehealthConversion", "james"),
                                       ("RiskTieredOutreach", "sarah"), ("DeteriorationBoard", "sarah"),
                                       ("MaternalRiskStratification", "maria"), ("TelehealthScenario", "maria"),
                                       ("DataHealthBoard", "david")):
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
