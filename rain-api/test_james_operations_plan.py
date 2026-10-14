"""
Tests for james_operations_plan.py.   Run:  python test_james_operations_plan.py
"""

import json
import os
import subprocess
import sys
import pg_compat
import uuid
import time
import traceback
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import action_engine as eng  # noqa: E402
import james_operations_plan as op  # noqa: E402

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


def fresh_log():
    """A fresh, unique Postgres audit scope for one test -- log_path is a
    scope key now (see action_engine.log_scope), not a SQLite file path.
    uuid4 gives a clean, purpose-built unique string instead of the old
    tempfile.mkdtemp() leftover, which worked only by the accident of
    temp-dir names being unique, and wasted a real empty directory on
    disk for every call."""
    return f"test-{uuid.uuid4().hex}"


def sql(q, *a):
    c = pg_compat.connect(DB)
    try:
        return c.execute(q, a).fetchall()
    finally:
        c.close()


def raises(exc, fn, *a, **k):
    try:
        fn(*a, **k)
    except exc as e:
        return str(e)
    raise AssertionError(f"expected {exc.__name__}")


@check("transport schedule action matches the verified 9-unscheduled-of-73 figure exactly")
def _():
    pkg = op.build_operations_plan(log_path=fresh_log())
    a = next(x for x in pkg["actions"] if x["type"] == "transport_schedule")
    total = sql("SELECT COUNT(*) FROM TransportRequest WHERE date='2026-05-15'")[0][0]
    unsch = sql("SELECT COUNT(*) FROM TransportRequest WHERE date='2026-05-15' AND scheduled='False'")[0][0]
    assert (total, unsch) == (73, 9)
    assert (a["draft"]["total"], a["draft"]["unscheduled"]) == (73, 9)
    assert "no hour-of-day field exists" in json.dumps(a["draft"]).lower()  # the real disclosure, not a double-booking count claim
    assert "3 double-bookings" not in json.dumps(a["draft"]) and "shifts 5" not in json.dumps(a["draft"])  # the static card's fabricated claim


@check("telehealth overlap matches the verified 3-of-64 proxy figure exactly, NOT the static card's wrong 13")
def _():
    pkg = op.build_operations_plan(log_path=fresh_log())
    a = next(x for x in pkg["actions"] if x["type"] == "telehealth_conversion")
    proxy = sql("SELECT COUNT(*) FROM TransportRequest t WHERE t.date='2026-05-15' AND t.scheduled='True' AND t.patient_id IN "
               "(SELECT patient_id FROM TelehealthSession WHERE eligibility_status='eligible')")[0][0]
    assert proxy == 3
    assert a["draft"]["proxy_convertible"] == 3
    assert a["draft"]["proxy_convertible"] != 13


@check("EMS reassignment lists exactly the 2 verified coverage-gap ZIPs (89820, 89821), worst first")
def _():
    pkg = op.build_operations_plan(log_path=fresh_log())
    a = next(x for x in pkg["actions"] if x["type"] == "ems_reassignment")
    gaps = sql("SELECT zip_code, avg_response_time_minutes FROM EMSCoverage WHERE unit_available_within_60min='False' ORDER BY CAST(avg_response_time_minutes AS FLOAT) DESC")
    assert [(g[0], float(g[1])) for g in gaps] == [("89820", 74.0), ("89821", 71.0)]
    assert [(z["zip"], z["minutes"]) for z in a["draft"]["gap_zips"]] == [("89820", 74.0), ("89821", 71.0)]


@check("risk panel matches the verified finding exactly: 9 unscheduled, 0 elevated-pregnancy, 0 worsening-RPM, 9 chronic -- NOT the static card's '16 elevated-risk'")
def _():
    pkg = op.build_operations_plan(log_path=fresh_log())
    a = next(x for x in pkg["actions"] if x["type"] == "risk_panel")
    ids = [r[0] for r in sql("SELECT patient_id FROM TransportRequest WHERE date='2026-05-15' AND scheduled='False'")]
    ph = ",".join("?" * len(ids))
    preg = sql(f"SELECT COUNT(DISTINCT patient_id) FROM PregnancyEpisode WHERE trimester=3 AND distance_to_delivery_miles=115 AND patient_id IN ({ph})", *ids)[0][0]
    rpm = sql(f"SELECT COUNT(DISTINCT patient_id) FROM RPMReading WHERE condition_type IN ('CHF','COPD') AND patient_id IN ({ph})", *ids)[0][0]
    chronic = sql(f"SELECT COUNT(DISTINCT patient_id) FROM ChronicConditionEnrollment WHERE patient_id IN ({ph})", *ids)[0][0]
    assert (preg, rpm, chronic) == (0, 0, 9)
    d = a["draft"]
    assert (d["elevated_pregnancy"], d["worsening_rpm"], d["chronic"]) == (0, 0, 9)
    assert d["unscheduled"] == 9
    payload = json.dumps(pkg)
    assert '"16' not in payload  # the fabricated headline number never appears


@check("all 4 actions ready, deterministic, and this package takes no inputs")
def _():
    lp = fresh_log()
    pkg = op.build_operations_plan(log_path=lp)
    assert pkg["summary"]["actions_total"] == 4 and pkg["summary"]["ready_total"] == 4
    assert op.build_operations_plan(log_path=fresh_log()) == op.build_operations_plan(log_path=fresh_log())
    assert "takes no inputs" in raises(eng.ActionInputError, op.build_operations_plan, {"x": 1}, fresh_log())


@check("hold routes nothing; route records all 4 actions as routed (simulated), attributed, no duplicate on repeat")
def _():
    lp = fresh_log()
    h = op.decide_operations("hold", "James Tomley", log_path=lp)
    assert h["routed"] == [] and h["package"]["state"] == "held"
    r = op.decide_operations("route", "James Tomley", log_path=lp)
    assert len(r["routed"]) == 4 and r["package"]["state"] == "routed" and r["delivery"] == "simulated"
    again = op.decide_operations("route", "James Tomley", log_path=lp)
    assert again["routed"] == []
    aud = op.get_operations_audit(lp)
    assert [d["decision"] for d in aud["decisions"]] == ["hold", "route", "route"]
    assert all(d["decided_by"] == "James Tomley" for d in aud["decisions"])


@check("nothing here can contact anything: no network imports, delivery is always simulated")
def _():
    import ast
    tree = ast.parse(open(os.path.join(HERE, "james_operations_plan.py")).read())
    imported = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)} | \
               {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    banned = {"socket", "requests", "urllib", "http", "httpx", "smtplib", "ftplib", "aiohttp", "subprocess", "anthropic"}
    assert not (imported & banned), imported & banned
    assert op.build_operations_plan(log_path=fresh_log())["delivery"] == "simulated"


def http_tests():
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    env = dict(os.environ, RAIN_ACTION_LOG=fresh_log())
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--port", str(port), "--log-level", "warning"], cwd=HERE, env=env,
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

        def call(method, path, body=None):
            req = urllib.request.Request(base + path, method=method, headers={"Content-Type": "application/json"},
                                         data=None if body is None else json.dumps(body).encode())
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    return r.status, json.loads(r.read() or b"null")
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read() or b"null")

        P = "/ultra/rain/james/actionPackage"

        @check("HTTP: James's package is served under the shared registry, alongside all 5 personas")
        def _():
            st, pkg = call("GET", P)
            assert st == 200 and pkg["summary"]["actions_total"] == 4 and pkg["display"]["title"] == "Today's Operations Plan"
            for p in ("sarah", "maria", "david"):
                assert call("GET", f"/ultra/rain/{p}/actionPackage")[0] == 200
            assert call("GET", "/ultra/rain/nair/actionPackage")[0] == 200   # priya now has a package too
            assert call("GET", "/ultra/rain/not-a-real-persona/actionPackage")[0] == 404   # an unknown persona still 404s

        @check("HTTP: route then audit, attributed and persisted")
        def _():
            st, r = call("POST", P + "/decision", {"decision": "route", "decided_by": "James Tomley"})
            assert st == 200 and len(r["routed"]) == 4 and r["package"]["state"] == "routed"
            aud = call("GET", P + "/audit")[1]
            assert aud["decisions"][0]["decided_by"] == "James Tomley"

        @check("HTTP: every other prior live card remains unaffected")
        def _():
            for component, persona in (("OpsTrafficTiles", "james"), ("TransportQueueBreakdown", "james"),
                                       ("DownstreamImpact", "david"), ("RiskTieredOutreach", "sarah"), ("MaternalRiskStratification", "maria")):
                st, body = call("POST", "/api/v2/generic", {"market": "healthcare", "product": "rain", "persona": persona, "category": [{"component": component}]})
                assert st == 200 and body["visualization"][0]["data"], component
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
