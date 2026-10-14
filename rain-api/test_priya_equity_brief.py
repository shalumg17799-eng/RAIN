"""
Tests for priya_equity_brief.py.   Run:  python test_priya_equity_brief.py
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
import priya_equity_brief as eb  # noqa: E402

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


@check("documented_trend matches MetricTrend exactly (31% -> 58%, childbearing-age women, >60mi)")
def _():
    pkg = eb.build_equity_brief(log_path=fresh_log())
    row = sql("SELECT before_value, after_value, before_date, after_date FROM MetricTrend WHERE metric_id='maternal_care_desert_pct'")[0]
    assert (int(row[0]), int(row[1])) == (31, 58)
    a = next(x for x in pkg["actions"] if x["type"] == "situation")
    dt = a["draft"]["documented_trend"]
    assert (dt["before"], dt["after"]) == (31, 58)


@check("live_snapshot matches the already-verified 'Maternal care desert current' rule exactly (30%, 38 of 126)")
def _():
    pkg = eb.build_equity_brief(log_path=fresh_log())
    from business_rules import BUSINESS_RULES
    rule = next(x for x in BUSINESS_RULES if x["term"] == "Maternal care desert rate percentage")
    expect = sql(rule["sql"])[0][0]
    assert expect == 30
    a = next(x for x in pkg["actions"] if x["type"] == "situation")
    live = a["draft"]["live_snapshot"]
    assert live["affected"] == 38 and live["total"] == 126 and live["value"] == 30


@check("the two maternal-desert sources (31->58 documented, 30 live) both appear and are labelled with different scopes, not merged")
def _():
    pkg = eb.build_equity_brief(log_path=fresh_log())
    a = next(x for x in pkg["actions"] if x["type"] == "situation")
    assert a["draft"]["documented_trend"]["scope"] != a["draft"]["live_snapshot"]["scope"]
    assert "58" in a["draft"]["message"] and "30" in a["draft"]["message"]


@check("evidence action matches the verified 64% avoidable-ED figure (76 of 119) exactly")
def _():
    pkg = eb.build_equity_brief(log_path=fresh_log())
    ed = sql("SELECT SUM(CASE WHEN date>='2026-03-01' AND rendering_provider_id IN (SELECT provider_id FROM Provider WHERE status='deactivated') THEN 1 ELSE 0 END), "
             "SUM(CASE WHEN date>='2026-03-01' THEN 1 ELSE 0 END) FROM ClaimEncounter WHERE avoidable_ed_flag='True' AND encounter_type != 'ED_delivery_or_BBA'")[0]
    assert ed == (76, 119)
    a = next(x for x in pkg["actions"] if x["type"] == "evidence")
    assert (a["draft"]["tied"], a["draft"]["total"], a["draft"]["tied_pct"]) == (76, 119, 64)


@check("interventions action reuses priya_intervention_comparison's real options exactly (never diverges)")
def _():
    from priya_intervention_comparison import get_intervention_comparison
    pkg = eb.build_equity_brief(log_path=fresh_log())
    a = next(x for x in pkg["actions"] if x["type"] == "interventions")
    assert a["draft"]["options"] == get_intervention_comparison()["options"]


@check("no fabricated 12-month projection figures appear; measurement plan is disclosed as the real limitation")
def _():
    pkg = eb.build_equity_brief(log_path=fresh_log())
    a = next(x for x in pkg["actions"] if x["type"] == "measurement_plan")
    assert "no outcomes-projection model" in a["draft"]["message"].lower()
    # no action's draft carries actual projection VALUES (percentages/figures for a future outcome) -- only the
    # measurement_plan action may reference the dropped section's name to explain why it's absent
    for act in pkg["actions"]:
        if act["type"] != "measurement_plan":
            assert "12-month" not in json.dumps(act["draft"])


@check("all 4 actions ready, deterministic, and this package takes no inputs")
def _():
    pkg = eb.build_equity_brief(log_path=fresh_log())
    assert pkg["summary"]["actions_total"] == 4 and pkg["summary"]["ready_total"] == 4
    assert eb.build_equity_brief(log_path=fresh_log()) == eb.build_equity_brief(log_path=fresh_log())
    assert "takes no inputs" in raises(eng.ActionInputError, eb.build_equity_brief, {"x": 1}, fresh_log())


@check("hold routes nothing; route records all 4 actions as routed (simulated), attributed, no duplicate on repeat")
def _():
    lp = fresh_log()
    h = eb.decide_equity_brief("hold", "Dr. Priya Nair", log_path=lp)
    assert h["routed"] == [] and h["package"]["state"] == "held"
    r = eb.decide_equity_brief("route", "Dr. Priya Nair", log_path=lp)
    assert len(r["routed"]) == 4 and r["package"]["state"] == "routed" and r["delivery"] == "simulated"
    again = eb.decide_equity_brief("route", "Dr. Priya Nair", log_path=lp)
    assert again["routed"] == []
    aud = eb.get_equity_brief_audit(lp)
    assert [d["decision"] for d in aud["decisions"]] == ["hold", "route", "route"]


@check("nothing here can contact anything: no network imports, delivery is always simulated")
def _():
    import ast
    tree = ast.parse(open(os.path.join(HERE, "priya_equity_brief.py")).read())
    imported = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)} | \
               {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    banned = {"socket", "requests", "urllib", "http", "httpx", "smtplib", "ftplib", "aiohttp", "subprocess", "anthropic"}
    assert not (imported & banned), imported & banned
    assert eb.build_equity_brief(log_path=fresh_log())["delivery"] == "simulated"


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

        P = "/ultra/rain/priya/actionPackage"

        @check("HTTP: all 5 personas now have a package -- the registry is complete")
        def _():
            st, pkg = call("GET", P)
            assert st == 200 and pkg["summary"]["actions_total"] == 4 and pkg["display"]["title"] == "NVHA Rural Health Access & Equity Brief"
            for p in ("sarah", "maria", "david", "james", "priya"):
                assert call("GET", f"/ultra/rain/{p}/actionPackage")[0] == 200, p

        @check("HTTP: route then audit, attributed and persisted")
        def _():
            st, r = call("POST", P + "/decision", {"decision": "route", "decided_by": "Dr. Priya Nair"})
            assert st == 200 and len(r["routed"]) == 4 and r["package"]["state"] == "routed"
            aud = call("GET", P + "/audit")[1]
            assert aud["decisions"][0]["decided_by"] == "Dr. Priya Nair"

        @check("HTTP: every other prior live card remains unaffected")
        def _():
            for component, persona in (("InterventionComparison", "priya"), ("OpsTrafficTiles", "james"),
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
