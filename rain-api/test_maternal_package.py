"""
Tests for Maria's maternal outreach package.   Run:  python test_maternal_package.py

Every figure is checked against independent SQL, the risk ranking is re-derived
from scratch, the route / hold gate is exercised end to end, and Sarah's and
Maria's packages are shown not to interfere with each other. The HTTP layer is
tested against a real running server (pass --no-http to skip). Every test uses a
throwaway audit scope, so nothing here touches the default action log.
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
import action_engine as eng            # noqa: E402
import action_package as sarah         # noqa: E402
import maria_action_package as m       # noqa: E402

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


COHORT = "SELECT patient_id FROM PregnancyEpisode WHERE trimester = 3 AND distance_to_delivery_miles = 115"

# ---------------------------------------------------------------- the package


@check("the cohort is the verified 'third-trimester within elevated-risk cohort' (14), and the ids match independent SQL")
def _():
    from business_rules import BUSINESS_RULES
    rule = next(r for r in BUSINESS_RULES if r["term"] == "Third-trimester within elevated-risk cohort")
    assert sql(rule["sql"])[0][0] == 14
    pkg = m.build_maternal_package(log_path=fresh_log())
    assert sorted(p["patient_id"] for p in pkg["patients"]) == sorted(r[0] for r in sql(COHORT)) and len(pkg["patients"]) == 14


@check("the recommended intervention split is 8 telehealth / 3 hybrid / 3 in-person, re-derived from TelehealthSession")
def _():
    pkg = m.build_maternal_package(log_path=fresh_log())
    expect = {"telehealth": 0, "hybrid_nemt": 0, "in_person": 0}
    for (pid,) in sql(COHORT):
        labels = [r[0] for r in sql("SELECT eligibility_status FROM TelehealthSession WHERE patient_id=?", pid)]
        expect["telehealth" if "eligible" in labels else "hybrid_nemt" if "hybrid" in labels else "in_person"] += 1
    assert pkg["summary"]["interventions"] == expect == {"telehealth": 8, "hybrid_nemt": 3, "in_person": 3}
    assert pkg["summary"]["telehealth_referral"]["total"] == 8


@check("NEMT drafts are exactly the 3 hybrid patients + the 22 verified no-scheduled-transport pregnancies (25, no overlap)")
def _():
    pkg = m.build_maternal_package(log_path=fresh_log())
    no_transport = {r[0] for r in sql("SELECT patient_id FROM PregnancyEpisode WHERE patient_id NOT IN (SELECT patient_id FROM TransportRequest WHERE scheduled='True')")}
    hybrid = {r[0] for r in sql(f"SELECT patient_id FROM TelehealthSession WHERE eligibility_status='hybrid' AND patient_id IN ({COHORT})")}
    got = {a["patient_id"] for a in pkg["actions"] if a["type"] == "nemt_request"}
    assert len(no_transport) == 22 and len(hybrid) == 3 and not (no_transport & hybrid)
    assert got == no_transport | hybrid and len(got) == 25 and pkg["summary"]["nemt"] == {"hybrid": 3, "no_transport": 22, "total": 25}


@check("each NEMT draft goes to that patient's own delivering facility (not one facility for everyone)")
def _():
    pkg = m.build_maternal_package(log_path=fresh_log())
    for a in pkg["actions"]:
        if a["type"] == "nemt_request":
            fac = sql("SELECT f.name FROM PregnancyEpisode p JOIN Facility f ON f.facility_id=p.delivering_facility_id WHERE p.patient_id=?", a["patient_id"])[0][0]
            assert a["draft"]["destination_facility"] == fac, a["patient_id"]
    assert len({a["draft"]["destination_facility"] for a in pkg["actions"] if a["type"] == "nemt_request"}) == 2


@check("the chronic-team handoff is the 3 patients in both the cohort and a chronic program, to their recorded coordinator")
def _():
    pkg = m.build_maternal_package(log_path=fresh_log())
    expect = {r[0]: r[1] for r in sql(f"SELECT patient_id, care_coordinator_id FROM ChronicConditionEnrollment WHERE patient_id IN ({COHORT})")}
    hand = {a["patient_id"]: a for a in pkg["actions"] if a["type"] == "chronic_handoff"}
    assert set(hand) == set(expect) and len(hand) == 3
    assert all(hand[p]["draft"]["coordinator"] == c for p, c in expect.items())
    assert all("was deactivated 2026-03-01" in a["draft"]["message"] for a in hand.values())        # all 3 are on a deactivated provider


@check("the risk ranking is re-derived from scratch and matches (5 explicit factors, soonest due date breaks ties)")
def _():
    pkg = m.build_maternal_package(log_path=fresh_log())
    expect = []
    for (pid,) in sql(COHORT):
        dx, last, edd = sql("SELECT risk_diagnoses, last_prenatal_visit_date, expected_delivery_date FROM PregnancyEpisode WHERE patient_id=?", pid)[0]
        labels = [r[0] for r in sql("SELECT eligibility_status FROM TelehealthSession WHERE patient_id=?", pid)]
        sched = sql("SELECT COUNT(*) FROM TransportRequest WHERE patient_id=? AND scheduled='True'", pid)[0][0]
        chronic = bool(sql("SELECT 1 FROM ChronicConditionEnrollment WHERE patient_id=?", pid))
        score = bool((dx or "").strip()) + (last < "2026-04-01") + (sched == 0) + ("eligible" not in labels) + chronic
        expect.append((-score, edd, pid))
    expect.sort()
    got = [(-p["risk_score"], p["edd"], p["patient_id"]) for p in pkg["patients"]]
    assert got == expect and [p["rank"] for p in pkg["patients"]] == list(range(1, 15))
    assert all(p["risk_factors_total"] == 5 and len(p["factors"]) == p["risk_score"] for p in pkg["patients"])


@check("every fact in each care summary matches independent SQL")
def _():
    pkg = m.build_maternal_package(log_path=fresh_log())
    for p in pkg["patients"]:
        dx, last = sql("SELECT risk_diagnoses, last_prenatal_visit_date FROM PregnancyEpisode WHERE patient_id=?", p["patient_id"])[0]
        assert last in p["care_summary"] and ((dx or "").strip() or "none on record") in p["care_summary"], p["patient_id"]
        assert "115 miles" in p["care_summary"]
    assert sum("missed since the closure" in p["care_summary"] for p in pkg["patients"]) == 6           # the verified missed-visit count


@check("data disagreements are flagged, not hidden: the 5 'eligible' patients with no broadband, and thin clinical history")
def _():
    pkg = m.build_maternal_package(log_path=fresh_log())
    expect = sql(f"SELECT COUNT(*) FROM TelehealthSession s JOIN Patient p ON p.patient_id=s.patient_id JOIN ConnectivityRegistry c ON c.zip_code=p.zip_code "
                 f"WHERE s.eligibility_status='eligible' AND c.broadband_available='False' AND s.patient_id IN ({COHORT}) GROUP BY s.patient_id")
    flagged = [a for a in pkg["actions"] if a["type"] == "telehealth_referral" and a["flags"]]
    assert len(flagged) == len(expect) == 5 and pkg["summary"]["connectivity_conflicts"] == 5
    assert all(f["flags"][0]["code"] == "connectivity_conflict" for f in flagged)
    assert any("disagree" in n for n in pkg["notes"]) and any("Claims are on file for 1 of the 14" in n for n in pkg["notes"])


@check("all 36 actions are fully drafted (nothing waits on input) and the card rows carry the real counts")
def _():
    pkg = m.build_maternal_package(log_path=fresh_log())
    s = pkg["summary"]
    assert s["actions_total"] == 36 and s["ready_total"] == 36 and s["routed_total"] == 0 and pkg["needs_input"] == []
    labels = {r["label"] for r in pkg["display"]["rows"]}
    assert labels == {"Ranked patient list", "Telehealth referrals (8)", "NEMT transport requests (25)", "Cross-team handoff (3)"}
    assert [t["n"] for t in pkg["display"]["tiles"]] == [8, 3, 3]


@check("the package is deterministic, and viewing it creates nothing on disk")
def _():
    lp = fresh_log()
    a, b = m.build_maternal_package(log_path=lp), m.build_maternal_package(log_path=fresh_log())
    assert a["package_id"] == b["package_id"] and json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert m.get_maternal_audit(lp)["decisions"] == [] and rows(lp, "decisions") == 0


@check("this package takes no inputs: anything supplied is refused")
def _():
    assert "takes no inputs" in raises(eng.ActionInputError, m.build_maternal_package, {"anything": 1}, fresh_log())
    assert "takes no inputs" in raises(eng.ActionInputError, m.decide_maternal, "route", "Maria", {"x": 1}, None, fresh_log())


# -------------------------------------------------------------- the route/hold gate


@check("hold routes nothing and the package stays a draft")
def _():
    r = m.decide_maternal("hold", "Dr. Maria Delgado-Reyes", log_path=fresh_log())
    assert r["routed"] == [] and r["package"]["state"] == "held" and r["package"]["summary"]["routed_total"] == 0


@check("route records all 36 ready actions as routed (simulated); a repeat click adds none and duplicates nothing")
def _():
    lp = fresh_log()
    r = m.decide_maternal("route", "Dr. Maria Delgado-Reyes", log_path=lp)
    assert len(r["routed"]) == 36 and r["held"] == [] and r["package"]["state"] == "routed" and r["delivery"] == "simulated"
    again = m.decide_maternal("route", "Dr. Maria Delgado-Reyes", log_path=lp)
    assert again["routed"] == [] and len(again["already_routed"]) == 36 and rows(lp, "routed_actions") == 36


@check("what was routed is preserved exactly as approved, even for later reads")
def _():
    lp = fresh_log()
    m.decide_maternal("route", "Maria", log_path=lp)
    later = m.build_maternal_package(log_path=lp)
    assert later["state"] == "routed" and all(a["status"] == "routed" and a["routed_at"] for a in later["actions"])


@check("every decision is attributable and validated; rejected calls leave no trace")
def _():
    lp = fresh_log()
    assert "decided_by" in raises(eng.ActionInputError, m.decide_maternal, "route", " ", log_path=lp)
    assert "decision must be" in raises(eng.ActionInputError, m.decide_maternal, "approve", "Maria", log_path=lp)
    assert rows(lp, "decisions") == 0 and rows(lp, "routed_actions") == 0


@check("the audit trail records who, when, what was routed and what was held")
def _():
    lp = fresh_log()
    m.decide_maternal("hold", "Maria", note="reviewing with the care team", log_path=lp)
    m.decide_maternal("route", "Maria", log_path=lp)
    a = m.get_maternal_audit(lp)
    assert [d["decision"] for d in a["decisions"]] == ["hold", "route"] and a["decisions"][0]["note"] == "reviewing with the care team"
    assert len(a["decisions"][1]["routed"]) == 36 and all(d["decided_by"] == "Maria" and d["delivery"] == "simulated" for d in a["decisions"])


@check("six simultaneous 'route' clicks route each of the 36 actions exactly once, with no error")
def _():
    lp, errors, results = fresh_log(), [], []

    def click():
        try:
            results.append(m.decide_maternal("route", "Maria", log_path=lp))
        except Exception as e:                                       # noqa: BLE001
            errors.append(e)
    ts = [threading.Thread(target=click) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors, errors
    assert rows(lp, "routed_actions") == 36 and sum(len(r["routed"]) for r in results) == 36


@check("Sarah's and Maria's packages share one audit log without interfering")
def _():
    lp = fresh_log()
    sarah.decide("route", "Sarah", log_path=lp)                       # Sarah routes her 6 ready actions
    before = sarah.build_tier1_package(log_path=lp)["summary"]["routed_total"]
    m.decide_maternal("route", "Maria", log_path=lp)                  # Maria routes her 36
    assert before == 6 and sarah.build_tier1_package(log_path=lp)["summary"]["routed_total"] == 6
    assert m.build_maternal_package(log_path=lp)["summary"]["routed_total"] == 36
    assert rows(lp, "routed_actions") == 42 and rows(lp, "decisions") == 2
    assert {d["decided_by"] for d in sarah.get_audit(lp)["decisions"]} == {"Sarah"} and {d["decided_by"] for d in m.get_maternal_audit(lp)["decisions"]} == {"Maria"}


# ------------------------------------------------------------------- safety


@check("nothing here can contact anything: no network or messaging imports in the engine or Maria's module")
def _():
    banned = {"socket", "requests", "urllib", "http", "httpx", "smtplib", "ftplib", "aiohttp", "twilio", "boto3", "subprocess", "anthropic"}
    for fn in ("action_engine.py", "maria_action_package.py"):
        tree = ast.parse(open(os.path.join(HERE, fn)).read())
        imported = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)} | \
                   {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        assert not (imported & banned), (fn, imported & banned)
    assert eng.DELIVERY == "simulated" and m.build_maternal_package(log_path=fresh_log())["delivery"] == "simulated"


@check("the shared dataset is untouched by routing")
def _():
    tables = dataset_tables()
    before = {t: sql(f'SELECT COUNT(*) FROM "{t}"')[0][0] for t in tables}
    m.decide_maternal("route", "Maria", log_path=fresh_log())
    assert before == {t: sql(f'SELECT COUNT(*) FROM "{t}"')[0][0] for t in tables}


# ----------------------------------------------------------------- HTTP layer


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
            except Exception:                                        # noqa: BLE001
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

        P = "/ultra/rain/maria/actionPackage"

        @check("HTTP: Maria's package is served (under the app's short id and Ultra's key); personas without one still get 404")
        def _():
            st, pkg = call("GET", P)
            assert st == 200 and pkg["summary"]["actions_total"] == 36 and pkg["display"]["title"] == "Priority Maternal Outreach Package" and pkg["delivery"] == "simulated"
            assert call("GET", "/ultra/rain/delgado-reyes/actionPackage")[0] == 200
            assert all(call("GET", f"/ultra/rain/{p}/actionPackage")[0] == 200 for p in ("tomley", "nair"))
            assert call("GET", "/ultra/rain/nobody/actionPackage")[0] == 404

        @check("HTTP: Sarah's package is unaffected (same endpoints, same 15 actions)")
        def _():
            st, pkg = call("GET", "/ultra/rain/sarah/actionPackage")
            assert st == 200 and pkg["summary"]["actions_total"] == 15 and pkg["persona"] == "sarah"

        @check("HTTP: inputs are refused with a reason; a plain preview records nothing")
        def _():
            st, err = call("POST", P + "/preview", {"inputs": {"x": 1}})
            assert st == 400 and "takes no inputs" in err["detail"]
            st, pkg = call("POST", P + "/preview", {})
            assert st == 200 and pkg["summary"]["ready_total"] == 36 and call("GET", P + "/audit")[1]["decisions"] == []

        @check("HTTP: decision validation leaves no trace; hold then route is attributed and persists")
        def _():
            assert call("POST", P + "/decision", {"decision": "route"})[0] == 422
            assert call("POST", P + "/decision", {"decision": "route", "decided_by": " "})[0] == 400
            assert call("GET", P + "/audit")[1]["decisions"] == []
            st, r = call("POST", P + "/decision", {"decision": "hold", "decided_by": "Dr. Maria Delgado-Reyes"})
            assert st == 200 and r["routed"] == [] and r["package"]["state"] == "held"
            st, r = call("POST", P + "/decision", {"decision": "route", "decided_by": "Dr. Maria Delgado-Reyes"})
            assert st == 200 and len(r["routed"]) == 36 and r["package"]["state"] == "routed" and r["delivery"] == "simulated"
            aud = call("GET", P + "/audit")[1]
            assert [d["decision"] for d in aud["decisions"]] == ["hold", "route"] and call("GET", P)[1]["state"] == "routed"
            assert call("GET", "/ultra/rain/sarah/actionPackage")[1]["state"] == "draft"                # Sarah's untouched
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
