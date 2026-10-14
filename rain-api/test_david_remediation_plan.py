"""
Tests for david_remediation_plan.py.   Run:  python test_david_remediation_plan.py
"""

import json
import os
import subprocess
import sys
import pg_compat
import uuid
import time
import traceback
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import action_engine as eng  # noqa: E402
import david_remediation_plan as rp  # noqa: E402

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


def rows(log_path, table):
    c = pg_compat.connect()
    try:
        return c.execute(f"SELECT COUNT(*) FROM {table} WHERE scope = ?", (log_path,)).fetchone()[0]
    finally:
        c.close()


def raises(exc, fn, *a, **k):
    try:
        fn(*a, **k)
    except exc as e:
        return str(e)
    raise AssertionError(f"expected {exc.__name__}")


@check("reconciliation action matches the verified 1,240/180 figures exactly")
def _():
    pkg = rp.build_remediation_plan(log_path=fresh_log())
    a = next(x for x in pkg["actions"] if x["type"] == "provider_reconciliation")
    assert a["draft"]["resolves"] == sql("SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status='unresolved'")[0][0] == 1240
    assert a["draft"]["crosswalk_fixes"] == sql("SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status='mismatched'")[0][0] == 180


@check("RPM completeness action shows the real 61%, NOT the static card's wrong 78% starting point")
def _():
    pkg = rp.build_remediation_plan(log_path=fresh_log())
    a = next(x for x in pkg["actions"] if x["type"] == "rpm_completeness")
    total, received = sql("SELECT COUNT(*), SUM(transmission_status='received') FROM RPMReading WHERE condition_type='hypertension'")[0]
    expect_pct = round(100 * received / total)
    assert expect_pct == 61
    assert a["draft"]["current_pct"] == 61
    assert "78" not in json.dumps(a["draft"])


@check("weakest ZIPs match independent SQL, 89825 among them (the already-verified weakest ZIP)")
def _():
    pkg = rp.build_remediation_plan(log_path=fresh_log())
    a = next(x for x in pkg["actions"] if x["type"] == "rpm_completeness")
    rows_ = sql("SELECT p.zip_code, ROUND(100.0*SUM(r.transmission_status='received')/COUNT(*)) FROM RPMReading r "
               "JOIN Patient p ON p.patient_id=r.patient_id WHERE r.condition_type='hypertension' GROUP BY p.zip_code ORDER BY 2 ASC LIMIT 3")
    expect = [z for z, _ in rows_]
    assert [z["zip"] for z in a["draft"]["weakest_zips"]] == expect
    assert "89825" in expect


@check("FHIR mapping action ties to the real weakest feed (New Rural Clinic EHR Connector, 88%), no fabricated 'clears X/Y' numbers")
def _():
    pkg = rp.build_remediation_plan(log_path=fresh_log())
    a = next(x for x in pkg["actions"] if x["type"] == "fhir_mapping")
    feed = sql("SELECT source_name, fhir_conformance_pct FROM DataSourceFeed ORDER BY CAST(fhir_conformance_pct AS FLOAT) ASC LIMIT 1")[0]
    # Postgres returns this percentage as a number (88). SQLite stored it as the text "88".
    assert feed[0] == "New Rural Clinic EHR Connector" and float(feed[1]) == 88.0, feed
    assert a["draft"]["weakest_feed"] == "New Rural Clinic EHR Connector" and a["draft"]["weakest_pct"] == 88.0


@check("all 3 actions are ready, the package is deterministic, and this package takes no inputs")
def _():
    lp = fresh_log()
    a = rp.build_remediation_plan(log_path=lp)
    assert a["summary"]["actions_total"] == 3 and a["summary"]["ready_total"] == 3
    assert rp.build_remediation_plan(log_path=fresh_log()) == rp.build_remediation_plan(log_path=fresh_log())
    assert "takes no inputs" in raises(eng.ActionInputError, rp.build_remediation_plan, {"x": 1}, fresh_log())


@check("hold routes nothing; route records all 3 ready actions as routed (simulated), attributed, no duplicate on repeat")
def _():
    lp = fresh_log()
    h = rp.decide_remediation("hold", "David Yazzie", log_path=lp)
    assert h["routed"] == [] and h["package"]["state"] == "held"
    r = rp.decide_remediation("route", "David Yazzie", log_path=lp)
    assert len(r["routed"]) == 3 and r["package"]["state"] == "routed" and r["delivery"] == "simulated"
    again = rp.decide_remediation("route", "David Yazzie", log_path=lp)
    assert again["routed"] == [] and rows(lp, "routed_actions") == 3
    aud = rp.get_remediation_audit(lp)
    # three recorded decisions: hold, route, and the repeat route (correctly logged as an attempt even though it routed nothing new)
    assert [d["decision"] for d in aud["decisions"]] == ["hold", "route", "route"]
    assert all(d["decided_by"] == "David Yazzie" for d in aud["decisions"])
    assert len(aud["decisions"][1]["routed"]) == 3 and aud["decisions"][2]["routed"] == []


@check("nothing here can contact anything: no network imports, delivery is always simulated")
def _():
    import ast
    tree = ast.parse(open(os.path.join(HERE, "david_remediation_plan.py")).read())
    imported = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)} | \
               {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    banned = {"socket", "requests", "urllib", "http", "httpx", "smtplib", "ftplib", "aiohttp", "subprocess", "anthropic"}
    assert not (imported & banned), imported & banned
    assert rp.build_remediation_plan(log_path=fresh_log())["delivery"] == "simulated"


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

        P = "/ultra/rain/david/actionPackage"

        @check("HTTP: David's package is served under the shared /actionPackage registry alongside Sarah's and Maria's")
        def _():
            st, pkg = call("GET", P)
            assert st == 200 and pkg["summary"]["actions_total"] == 3 and pkg["display"]["title"] == "Data Remediation Plan"
            for p in ("sarah", "maria"):
                assert call("GET", f"/ultra/rain/{p}/actionPackage")[0] == 200

        @check("HTTP: route then audit, attributed and persisted")
        def _():
            st, r = call("POST", P + "/decision", {"decision": "route", "decided_by": "David Yazzie"})
            assert st == 200 and len(r["routed"]) == 3 and r["package"]["state"] == "routed"
            aud = call("GET", P + "/audit")[1]
            assert aud["decisions"][0]["decided_by"] == "David Yazzie"

        @check("HTTP: downstream impact and all other prior live cards remain unaffected")
        def _():
            import urllib.error  # noqa: F401 (used in call())
            for component, persona in (("DownstreamImpact", "david"), ("DataHealthBoard", "david"),
                                       ("RiskTieredOutreach", "sarah"), ("MaternalRiskStratification", "maria")):
                st, body = call("POST", "/api/v2/generic", {"market": "healthcare", "product": "rain", "persona": persona, "category": [{"component": component}]})
                assert st == 200 and body["visualization"][0]["data"], component
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    import urllib.error  # noqa: E402
    if "--no-http" not in sys.argv:
        http_tests()
    failed = [r for r in _results if not r[1]]
    for name, ok, err in _results:
        print(("  PASS  " if ok else "  FAIL  ") + name)
        if not ok:
            print("        " + err.strip().replace("\n", "\n        "))
    print(f"\n{len(_results) - len(failed)} of {len(_results)} passed")
    sys.exit(1 if failed else 0)
