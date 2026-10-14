"""
Tests for james_ops_live.py.   Run:  python test_james_ops_live.py
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
    """information_schema, not PRAGMA table_info -- PRAGMA does not exist on Postgres.
    column_name is the first column of this query (PRAGMA put the name in r[1])."""
    return [r[0] for r in sql(
        "SELECT column_name FROM information_schema.columns WHERE table_name = ? ORDER BY ordinal_position",
        table,
    )]


# --------------------------------------------------------------- ops tiles


@check("Transport Queue tile matches the verified 9-unscheduled-of-47 figure, independently re-queried")
def _():
    tiles = {t["label"]: t for t in jo.get_ops_traffic_tiles()["tiles"]}
    total = sql("SELECT COUNT(*) FROM TransportRequest WHERE date='2026-05-15'")[0][0]
    unsch = sql("SELECT COUNT(*) FROM TransportRequest WHERE date='2026-05-15' AND scheduled='False'")[0][0]
    assert total == 47 and unsch == 9
    assert tiles["Transport Queue"]["value"] == "+9 over" and tiles["Transport Queue"]["status"] == "red"
    assert "9 of 47" in tiles["Transport Queue"]["detail"]


@check("Telehealth Capacity tile shows the 31 requested visits with no slot (red), count matches independent SQL")
def _():
    tiles = {t["label"]: t for t in jo.get_ops_traffic_tiles()["tiles"]}
    n = sql("SELECT COUNT(*) FROM TelehealthSession WHERE scheduled_date IS NULL")[0][0]
    assert n == 31
    assert tiles["Telehealth Capacity"]["value"] == "31 unslotted"
    assert tiles["Telehealth Capacity"]["status"] == "red"


@check("EMS Response tile shows the real worst ZIP (89820, 74 min), not an invented system-wide figure")
def _():
    tiles = {t["label"]: t for t in jo.get_ops_traffic_tiles()["tiles"]}
    worst = sql("SELECT zip_code, avg_response_time_minutes FROM EMSCoverage ORDER BY CAST(avg_response_time_minutes AS FLOAT) DESC LIMIT 1")[0]
    # Postgres returns this numeric column as a number (74). SQLite stored it as the text "74.0".
    assert worst[0] == "89820" and float(worst[1]) == 74.0, worst
    assert tiles["EMS Response"]["value"] == "74 min (worst)"
    assert "89820" in tiles["EMS Response"]["detail"]
    no_cov = sql("SELECT COUNT(*) FROM EMSCoverage WHERE unit_available_within_60min='False'")[0][0]
    assert no_cov == 2 and "2 ZIP" in tiles["EMS Response"]["detail"]
    assert tiles["EMS Response"]["value"] != "47 min"  # the static card's unsupported figure


@check("Facility Status tile matches the real closure count (1 of 8, Battle Mountain)")
def _():
    tiles = {t["label"]: t for t in jo.get_ops_traffic_tiles()["tiles"]}
    closed = sql("SELECT COUNT(*) FROM Facility WHERE status='closed'")[0][0]
    total = sql("SELECT COUNT(*) FROM Facility")[0][0]
    assert (closed, total) == (1, 8)
    assert tiles["Facility Status"]["value"] == "1 of 8 closed"
    assert "Battle Mountain" in tiles["Facility Status"]["detail"]


@check("Mobile Clinic tile reads the real 98% utilization; Facility Beds stays omitted (no bed field exists)")
def _():
    result = jo.get_ops_traffic_tiles()
    tiles = {t["label"]: t for t in result["tiles"]}
    util = sql("SELECT utilization_pct FROM Facility WHERE name='Winnemucca Mobile Clinic'")[0][0]
    assert float(util) == 98
    assert tiles["Mobile Clinic"]["value"] == "98% util" and tiles["Mobile Clinic"]["status"] == "yellow"
    assert "Facility Beds" not in str(set(tiles))
    assert set(result["omitted"]) == {"Facility bed availability"}
    assert result["omitted_reason"]
    # and confirm no bed-count field exists anywhere in the schema
    cols = {t: columns_of(t) for t in ("Facility", "TransportRequest", "TelehealthSession")}
    assert not any("bed" in c.lower() for cols_ in cols.values() for c in cols_)


@check("tiles are deterministic across repeated calls")
def _():
    assert jo.get_ops_traffic_tiles() == jo.get_ops_traffic_tiles()


# ----------------------------------------------------------- trip/telehealth conversion


@check("proxy_convertible matches the verified 3-of-38 figure, independently re-derived")
def _():
    conv = jo.get_trip_telehealth_conversion()
    scheduled = sql("SELECT COUNT(*) FROM TransportRequest WHERE date='2026-05-15' AND scheduled='True'")[0][0]
    proxy = sql(
        "SELECT COUNT(*) FROM TransportRequest t WHERE t.date='2026-05-15' AND t.scheduled='True' "
        "AND t.patient_id IN (SELECT patient_id FROM TelehealthSession WHERE eligibility_status='eligible')"
    )[0][0]
    assert scheduled == 38 and proxy == 3
    assert conv["scheduled_today"] == 38 and conv["proxy_convertible"] == 3


@check("the method is disclosed as a proxy, and the unsupported 13/7/6 narrative is explicitly NOT reproduced")
def _():
    conv = jo.get_trip_telehealth_conversion()
    assert "proxy" in conv["method"].lower()
    assert "no field" in conv["method"].lower() or "no flag" in conv["method"].lower()
    assert "13/7/6" in conv["note"] or ("dialysis" in conv["note"].lower() and "no basis" in conv["note"].lower())
    assert conv["proxy_convertible"] != 13  # the static card's invented headline number


@check("no table in the dataset has a 'convertible', 'room_slot', or 'dialysis' column -- confirms the premise really is unsupported, not just unqueried")
def _():
    for (t,) in sql("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"):
        cols = [c.lower() for c in columns_of(t)]
        assert not any("convertible" in c or "room_slot" in c or "dialysis" in c for c in cols), (t, cols)


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

        @check("HTTP: POST /api/v2/generic (OpsTrafficTiles) returns 5 real tiles")
        def _():
            status, body = generic("OpsTrafficTiles", "james")
            assert status == 200 and len(body["tiles"]) == 5

        @check("HTTP: POST /api/v2/generic (TripTelehealthConversion) returns the proxy figure")
        def _():
            status, body = generic("TripTelehealthConversion", "james")
            assert status == 200 and body["proxy_convertible"] == 3

        @check("HTTP: the existing chat pipeline and prior live cards are unaffected")
        def _():
            req = urllib.request.Request(base + "/api/v2/ask", method="POST", headers={"Content-Type": "application/json"},
                                         data=json.dumps({"market": "healthcare", "product": "rain", "persona": "david", "query": "crosswalk mismatches"}).encode())
            with urllib.request.urlopen(req, timeout=20) as r:
                assert r.status == 200
            assert generic("DataHealthBoard", "david")[0] == 200
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
