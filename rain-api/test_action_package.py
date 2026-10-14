"""
Tests for the Tier 1 action package.   Run:  python test_action_package.py

No test framework needed. Numbers are checked against independent SQL (not the
module's own helpers), the route/hold gate is exercised end to end, and the
HTTP layer is tested against a real running server (pass --no-http to skip).
Every test uses its own audit scope, so nothing here touches the default action log.
"""

import ast
import json
import os
import pg_compat
import subprocess
import sys
import uuid
import threading
import time
import traceback
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import action_package as ap  # noqa: E402

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
    """Independent check against Postgres."""
    c = pg_compat.connect(DB)
    try:
        return c.execute(q, a).fetchall()
    finally:
        c.close()


def dataset_tables():
    audit = {"decisions", "routed_actions"}
    return [t for (t,) in sql(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
    ) if t not in audit]


def rows(log_path, table):
    """Rows in the Postgres audit log for this test's scope."""
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


ALL_PHARMACY = {p: f"Pharmacy for {p}" for p in ["PT-00127", "PT-00128", "PT-00129", "PT-00130", "PT-00131"]}

# ------------------------------------------------------------------ the package


@check("Tier 1 patients are exactly the rows of Sarah's risk-ranked outreach rule")
def _():
    from business_rules import BREAKDOWN_RULES
    rule = next(r for r in BREAKDOWN_RULES if r["term"] == ap.TIER1_RULE_TERM)
    expected = [r[0] for r in sql(rule["group_by_sql"])]
    got = [p["patient_id"] for p in ap.build_tier1_package(log_path=fresh_log())["patients"]]
    assert got == expected == ["PT-00127", "PT-00128", "PT-00129", "PT-00130", "PT-00131"], (got, expected)


@check("every figure in each care summary matches independent SQL")
def _():
    pkg = ap.build_tier1_package(log_path=fresh_log())
    for p in pkg["patients"]:
        pid, f = p["patient_id"], p["facts"]
        w = sql("SELECT value FROM RPMReading WHERE patient_id=? AND reading_type='weight' ORDER BY timestamp", pid)
        assert f["rpm"]["first"] == float(w[0][0]) and f["rpm"]["last"] == float(w[-1][0]), pid
        assert f["rpm"]["delta"] == round(float(w[-1][0]) - float(w[0][0]), 1), pid
        fill = sql("SELECT MAX(fill_date) FROM MedicationFill WHERE patient_id=?", pid)[0][0]
        assert f["medication"]["last_fill"] == fill and f["medication"]["days_since_fill"] == 45, pid
        claim = sql("SELECT MAX(date) FROM ClaimEncounter WHERE patient_id=?", pid)[0][0]
        assert f["last_contact"]["date"] == claim, pid
        has_flag = bool(sql("SELECT 1 FROM SDOHFlag WHERE patient_id=? AND flag_type='transportation'", pid))
        assert f["transport_barrier"] == has_flag, pid
        bb = sql("SELECT c.broadband_available FROM Patient p JOIN ConnectivityRegistry c ON c.zip_code=p.zip_code WHERE p.patient_id=?", pid)[0][0]
        # Postgres returns a real bool; SQLite returned the string 'True'/'False'.
        # True == "True" is always False, so this must be bool(), not a string compare.
        assert f["broadband"] == bool(bb), pid
        assert f"{f['rpm']['delta']:+.1f}" in p["care_summary"] and f"{f['rpm']['last']:.1f}" in p["care_summary"], pid


@check("the card's counts hold: 5 pharmacy, 4 NEMT, 5 visit+re-panel, 1 CHW = 15 actions; 4 of 5 have a transport barrier")
def _():
    s = ap.build_tier1_package(log_path=fresh_log())["summary"]
    assert (s["pharmacy_outreach"]["total"], s["nemt_request"]["total"], s["visit_and_repanel"]["total"], s["chw_home_visit"]["total"]) == (5, 4, 5, 1)
    assert s["actions_total"] == 15 and s["ready_total"] == 6 and s["routed_total"] == 0
    barrier = {r[0] for r in sql("SELECT DISTINCT patient_id FROM SDOHFlag WHERE flag_type='transportation' AND patient_id BETWEEN 'PT-00127' AND 'PT-00131'")}
    assert len(barrier) == 4


@check("telehealth only where the patient has broadband: 4 in-person via NEMT, 1 telehealth")
def _():
    s = ap.build_tier1_package(log_path=fresh_log())["summary"]["visit_and_repanel"]
    assert (s["telehealth"], s["in_person_via_nemt"]) == (1, 4)


@check("an OB target is not accepted for CHF patients: those actions need input, with fitting options offered")
def _():
    pkg = ap.build_tier1_package(log_path=fresh_log())
    for a in pkg["actions"]:
        if a["patient_id"] in ("PT-00127", "PT-00131") and a["type"] in ("visit_and_repanel", "nemt_request"):
            assert a["status"] == "needs_input" and a["needs"][0]["field"] == "repanel_to"
            assert {o["provider_id"] for o in a["needs"][0]["options"]} >= {"PRV-010", "PRV-012"}
            assert "PRV-011" not in {o["provider_id"] for o in a["needs"][0]["options"]}
    ready = {(a["patient_id"], a["type"]) for a in pkg["actions"] if a["status"] == "ready"}
    assert ready == {(p, t) for p in ("PT-00128", "PT-00129", "PT-00130") for t in ("nemt_request", "visit_and_repanel")}


@check("viewing the package (or its audit) writes no decision; only a decision writes the log")
def _():
    lp = fresh_log()
    ap.build_tier1_package(log_path=lp)
    assert ap.get_audit(lp)["decisions"] == [] and rows(lp, "decisions") == 0
    ap.decide("hold", "Sarah", log_path=lp)
    assert rows(lp, "decisions") == 1


@check("the package is deterministic: same id and content on every build")
def _():
    a, b = ap.build_tier1_package(log_path=fresh_log()), ap.build_tier1_package(log_path=fresh_log())
    assert a["package_id"] == b["package_id"] and json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


@check("the silent patient is NOT invented: the CHW action is unassigned and says why")
def _():
    a = [x for x in ap.build_tier1_package(log_path=fresh_log())["actions"] if x["type"] == "chw_home_visit"][0]
    assert a["patient_id"] is None and a["status"] == "needs_input" and a["needs"][0]["field"] == "chw_patient_id"


# --------------------------------------------------------------- input validation


@check("invalid inputs are rejected with a reason")
def _():
    lp = fresh_log()
    assert "unknown input" in raises(ap.ActionInputError, ap.build_tier1_package, {"bogus": 1}, lp)
    assert "not in this package" in raises(ap.ActionInputError, ap.build_tier1_package, {"pharmacy_of_record": {"PT-99999": "X"}}, lp)
    assert "not an active provider" in raises(ap.ActionInputError, ap.build_tier1_package, {"repanel_to": {"PT-00127": "PRV-001"}}, lp)      # deactivated
    assert "not an active provider" in raises(ap.ActionInputError, ap.build_tier1_package, {"repanel_to": {"PT-00127": "PRV-777"}}, lp)      # nonexistent
    assert "not a fitting choice" in raises(ap.ActionInputError, ap.build_tier1_package, {"repanel_to": {"PT-00127": "PRV-013"}}, lp)        # endocrinology for CHF
    assert "printable" in raises(ap.ActionInputError, ap.build_tier1_package, {"pharmacy_of_record": {"PT-00127": "Bad\x00Name"}}, lp)
    assert "1-100" in raises(ap.ActionInputError, ap.build_tier1_package, {"pharmacy_of_record": {"PT-00127": "x" * 101}}, lp)
    assert "not a patient" in raises(ap.ActionInputError, ap.build_tier1_package, {"chw_patient_id": "PT-99999"}, lp)
    assert "not a patient" in raises(ap.ActionInputError, ap.build_tier1_package, {"chw_patient_id": "'; DROP TABLE Patient;--"}, lp)


@check("blank inputs count as 'not supplied', not as an error")
def _():
    s = ap.build_tier1_package({"pharmacy_of_record": {"PT-00127": "  "}, "chw_patient_id": ""}, fresh_log())["summary"]
    assert s["pharmacy_outreach"]["ready"] == 0 and s["chw_home_visit"]["ready"] == 0


@check("a fitting provider choice unblocks the visit and moves the NEMT destination to that provider's facility")
def _():
    pkg = ap.build_tier1_package({"repanel_to": {"PT-00127": "PRV-012"}}, fresh_log())
    by = {(a["patient_id"], a["type"]): a for a in pkg["actions"]}
    assert by[("PT-00127", "visit_and_repanel")]["status"] == "ready" and by[("PT-00127", "nemt_request")]["status"] == "ready"
    fac = sql("SELECT f.name FROM Provider p JOIN Facility f ON f.facility_id=p.facility_id WHERE p.provider_id='PRV-012'")[0][0]
    assert by[("PT-00127", "nemt_request")]["draft"]["destination_facility"] == fac
    assert by[("PT-00127", "visit_and_repanel")]["draft"]["repanel"]["source"] == "coordinator"


@check("a CHW patient with recent contact is flagged, not silently dispatched")
def _():
    a = [x for x in ap.build_tier1_package({"chw_patient_id": "PT-00128"}, fresh_log())["actions"] if x["type"] == "chw_home_visit"][0]
    assert a["status"] == "ready" and a["flags"] and a["flags"][0]["code"] == "not_silent"


# -------------------------------------------------------------- the route/hold gate


@check("hold routes nothing and the package stays a draft that can be routed later")
def _():
    lp = fresh_log()
    r = ap.decide("hold", "Sarah Whitehorse, RN", log_path=lp)
    assert r["routed"] == [] and r["package"]["state"] == "held" and r["package"]["summary"]["routed_total"] == 0
    assert "Nothing was routed" in r["message"]


@check("route sends only READY actions (6 of 15); everything else is held with the reason")
def _():
    lp = fresh_log()
    r = ap.decide("route", "Sarah Whitehorse, RN", log_path=lp)
    assert len(r["routed"]) == 6 and len(r["held"]) == 9 and r["package"]["state"] == "partially_routed"
    assert all(h["needs"] for h in r["held"])
    assert {x["type"] for x in r["routed"]} == {"nemt_request", "visit_and_repanel"}


@check("nothing is ever routed twice, and a repeat click does not duplicate the log")
def _():
    lp = fresh_log()
    ap.decide("route", "A", log_path=lp)
    again = ap.decide("route", "A", log_path=lp)
    assert again["routed"] == [] and len(again["already_routed"]) == 6
    assert rows(lp, "routed_actions") == 6


@check("the coordinator can complete the package in steps; the final state is 'routed'")
def _():
    lp = fresh_log()
    ap.decide("route", "Sarah", log_path=lp)
    full = {"pharmacy_of_record": ALL_PHARMACY, "repanel_to": {"PT-00127": "PRV-012", "PT-00131": "PRV-016"}, "chw_patient_id": "PT-00131"}
    r = ap.decide("route", "Sarah", inputs=full, log_path=lp)
    assert len(r["routed"]) == 9 and r["held"] == [] and r["package"]["state"] == "routed"
    assert rows(lp, "routed_actions") == 15


@check("what was routed is preserved exactly as approved (e.g. the pharmacy name), even for later reads")
def _():
    lp = fresh_log()
    ap.decide("route", "Sarah", inputs={"pharmacy_of_record": {"PT-00128": "Lander Rx"}}, log_path=lp)
    later = ap.build_tier1_package(log_path=lp)              # no inputs on this read
    ph = [a for a in later["actions"] if a["type"] == "pharmacy_outreach" and a["patient_id"] == "PT-00128"][0]
    assert ph["status"] == "routed" and ph["draft"]["to"] == "Lander Rx"


@check("every decision is attributable and validated")
def _():
    lp = fresh_log()
    assert "decided_by" in raises(ap.ActionInputError, ap.decide, "route", "  ", log_path=lp)
    assert "decided_by" in raises(ap.ActionInputError, ap.decide, "route", "x" * 81, log_path=lp)
    assert "decision must be" in raises(ap.ActionInputError, ap.decide, "approve", "Sarah", log_path=lp)
    assert rows(lp, "decisions") == 0 and rows(lp, "routed_actions") == 0                      # rejected calls leave no trace


@check("an invalid input aborts the whole decision: nothing is recorded")
def _():
    lp = fresh_log()
    raises(ap.ActionInputError, ap.decide, "route", "Sarah", {"repanel_to": {"PT-00127": "PRV-013"}}, None, lp)
    assert rows(lp, "decisions") == 0 and rows(lp, "routed_actions") == 0


@check("the audit trail records who, when, what was routed and what was held")
def _():
    lp = fresh_log()
    ap.decide("hold", "Sarah", note="checking with Dr. D-R first", log_path=lp)
    ap.decide("route", "Sarah", log_path=lp)
    a = ap.get_audit(lp)
    assert [d["decision"] for d in a["decisions"]] == ["hold", "route"] and all(d["decided_by"] == "Sarah" and d["decided_at"] for d in a["decisions"])
    assert a["decisions"][0]["note"] == "checking with Dr. D-R first" and len(a["decisions"][1]["routed"]) == 6 and len(a["decisions"][1]["held"]) == 9
    assert a["delivery"] == "simulated" and all(d["delivery"] == "simulated" for d in a["decisions"])


@check("two simultaneous 'route' clicks route each action exactly once, with no error")
def _():
    lp, errors, results = fresh_log(), [], []

    def click():
        try:
            results.append(ap.decide("route", "Sarah", log_path=lp))
        except Exception as e:                                       # noqa: BLE001
            errors.append(e)
    ts = [threading.Thread(target=click) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors, errors
    assert rows(lp, "routed_actions") == 6
    assert sum(len(r["routed"]) for r in results) == 6                 # 6 actions, split across the clicks, none twice


# ------------------------------------------------------------------- safety


@check("this module cannot contact anything: no network or messaging imports, delivery is always 'simulated'")
def _():
    tree = ast.parse(open(os.path.join(HERE, "action_package.py")).read())
    imported = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)} | \
               {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    banned = {"socket", "requests", "urllib", "http", "httpx", "smtplib", "ftplib", "aiohttp", "twilio", "boto3", "subprocess", "anthropic"}
    assert not (imported & banned), imported & banned
    pkg = ap.build_tier1_package(log_path=fresh_log())
    assert pkg["delivery"] == "simulated" and ap.DELIVERY == "simulated"


@check("the shared dataset is untouched: rain.db is opened read-only in effect (row counts unchanged by routing)")
def _():
    before = {t: sql(f'SELECT COUNT(*) FROM "{t}"')[0][0] for t in dataset_tables()}
    ap.decide("route", "Sarah", inputs={"pharmacy_of_record": ALL_PHARMACY}, log_path=fresh_log())
    after = {t: sql(f'SELECT COUNT(*) FROM "{t}"')[0][0] for t in dataset_tables()}
    assert before == after


# ----------------------------------------------------------------- HTTP layer


def http_tests():
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    log = fresh_log()
    env = dict(os.environ, RAIN_ACTION_LOG=log)
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--port", str(port), "--log-level", "warning"], cwd=HERE, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/health", timeout=1); break
            except Exception:                                        # noqa: BLE001
                time.sleep(0.5)
        else:
            raise RuntimeError("server did not start")

        def call(method, path, body=None, headers=None):
            req = urllib.request.Request(base + path, method=method, headers={"Content-Type": "application/json", **(headers or {})},
                                         data=None if body is None else json.dumps(body).encode())
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    return r.status, json.loads(r.read() or b"null"), dict(r.headers)
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read() or b"null"), dict(e.headers)

        P = "/ultra/rain/whitehorse/actionPackage"

        @check("HTTP: GET returns the package; personas without one get 404; the app's own persona key and 'sarah' both work")
        def _():
            st, pkg, _h = call("GET", P)
            assert st == 200 and pkg["summary"]["actions_total"] == 15 and pkg["delivery"] == "simulated"
            assert all(call("GET", f"/ultra/rain/{p}/actionPackage")[0] == 200 for p in ("tomley", "nair", "yazzie"))
            assert call("GET", "/ultra/rain/nobody/actionPackage")[0] == 404
            assert call("GET", "/ultra/rain/sarah/actionPackage")[0] == 200

        @check("HTTP: preview applies inputs but records nothing")
        def _():
            st, pkg, _h = call("POST", P + "/preview", {"inputs": {"pharmacy_of_record": ALL_PHARMACY}})
            assert st == 200 and pkg["summary"]["pharmacy_outreach"]["ready"] == 5
            assert call("GET", P + "/audit")[1]["decisions"] == []
            st, err, _h = call("POST", P + "/preview", {"inputs": {"repanel_to": {"PT-00127": "PRV-013"}}})
            assert st == 400 and "not a fitting choice" in err["detail"]

        @check("HTTP: decision validation (missing field 422, blank name 400, bad decision 400) leaves no trace")
        def _():
            assert call("POST", P + "/decision", {"decision": "route"})[0] == 422
            assert call("POST", P + "/decision", {"decision": "route", "decided_by": " "})[0] == 400
            assert call("POST", P + "/decision", {"decision": "approve", "decided_by": "Sarah"})[0] == 400
            assert call("GET", P + "/audit")[1]["decisions"] == []

        @check("HTTP: route -> partial; complete with inputs -> routed; audit shows both, attributed")
        def _():
            st, r, _h = call("POST", P + "/decision", {"decision": "route", "decided_by": "Sarah Whitehorse, RN"})
            assert st == 200 and len(r["routed"]) == 6 and r["package"]["state"] == "partially_routed" and r["delivery"] == "simulated"
            full = {"pharmacy_of_record": ALL_PHARMACY, "repanel_to": {"PT-00127": "PRV-012", "PT-00131": "PRV-016"}, "chw_patient_id": "PT-00131"}
            st, r, _h = call("POST", P + "/decision", {"decision": "route", "decided_by": "Sarah Whitehorse, RN", "inputs": full})
            assert st == 200 and len(r["routed"]) == 9 and r["package"]["state"] == "routed"
            aud = call("GET", P + "/audit")[1]
            assert [d["decided_by"] for d in aud["decisions"]] == ["Sarah Whitehorse, RN"] * 2
            assert call("GET", P)[1]["state"] == "routed"

        @check("HTTP: the browser can POST from another origin (CORS preflight allowed)")
        def _():
            req = urllib.request.Request(base + P + "/decision", method="OPTIONS", headers={
                "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
            with urllib.request.urlopen(req, timeout=10) as r:
                h = {k.lower(): v for k, v in r.headers.items()}
                assert r.status == 200
                assert "POST" in h.get("access-control-allow-methods", "").upper()
                assert h.get("access-control-allow-origin") in ("*", "http://localhost:5173")

        @check("HTTP: the existing chat pipeline is unaffected (a verified-rule answer still comes back)")
        def _():
            st, r, _h = call("POST", "/api/v2/ask", {"market": "healthcare", "persona": "david", "product": "rain", "query": "crosswalk mismatches"})
            assert st == 200 and "180" in json.dumps(r)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    if "--no-http" not in sys.argv:
        http_tests()
    width = max(len(n) for n, _, _ in _results)
    failed = [r for r in _results if not r[1]]
    for name, ok, err in _results:
        print(("  PASS  " if ok else "  FAIL  ") + name)
        if not ok:
            print("        " + err.strip().replace("\n", "\n        "))
    print(f"\n{len(_results) - len(failed)} of {len(_results)} passed")
    sys.exit(1 if failed else 0)
