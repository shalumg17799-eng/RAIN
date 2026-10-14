"""
Tests for priya_intervention_comparison.py.   Run:
    python test_priya_intervention_comparison.py
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
import priya_intervention_comparison as ic  # noqa: E402

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


@check("Option A reach matches the already-verified 48-patient figure, NOT the static card's unsupported 84%")
def _():
    r = ic.get_intervention_comparison()
    n = sql("SELECT COUNT(*) FROM PregnancyEpisode p JOIN Patient pt ON pt.patient_id=p.patient_id "
            "JOIN ConnectivityRegistry cr ON cr.zip_code=pt.zip_code WHERE cr.broadband_available='False'")[0][0]
    assert n == 48
    a = next(o for o in r["options"] if o["id"] == "A")
    assert "48" in a["reach"] and "84%" not in a["reach"]


@check("Option B reach matches independent SQL: 3 dead-zone sessions, 574 total in no-broadband ZIPs -- NOT the static card's 240")
def _():
    r = ic.get_intervention_comparison()
    dz = sql("SELECT COUNT(DISTINCT patient_id) FROM TelehealthSession WHERE eligibility_status='dead-zone'")[0][0]
    total = sql("SELECT COUNT(*) FROM Patient pt JOIN ConnectivityRegistry cr ON cr.zip_code=pt.zip_code WHERE cr.broadband_available='False'")[0][0]
    assert (dz, total) == (3, 574)
    b = next(o for o in r["options"] if o["id"] == "B")
    assert "3" in b["reach"] and "574" in b["reach"] and "240" not in b["reach"]


@check("Option C reach matches the verified 64% avoidable-ED figure (76 of 119) exactly")
def _():
    r = ic.get_intervention_comparison()
    ed = sql("SELECT SUM(CASE WHEN date>='2026-03-01' AND rendering_provider_id IN (SELECT provider_id FROM Provider WHERE status='deactivated') THEN 1 ELSE 0 END), "
             "SUM(CASE WHEN date>='2026-03-01' THEN 1 ELSE 0 END) FROM ClaimEncounter WHERE avoidable_ed_flag='True' AND encounter_type != 'ED_delivery_or_BBA'")[0]
    assert ed == (76, 119)
    c_opt = next(o for o in r["options"] if o["id"] == "C")
    assert "76 of 119" in c_opt["reach"] and "64%" in c_opt["reach"]


@check("no fabricated cost figure appears in any option's actual fields (name/reach/timeline/funding/priority); note may reference it to explain the drop")
def _():
    r = ic.get_intervention_comparison()
    fields_only = json.dumps([{k: v for k, v in o.items() if k != "recommended"} for o in r["options"]])
    # the dollar figure must not appear as a live data value anywhere in the options themselves
    import re
    assert not re.search(r"\$1\.0M(?!' is dropped)", fields_only)
    c_opt = next(o for o in r["options"] if o["id"] == "C")
    assert "no cost" in c_opt["funding"].lower() and "$" not in c_opt["funding"]


@check("deterministic across repeated calls")
def _():
    assert ic.get_intervention_comparison() == ic.get_intervention_comparison()


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

        @check("HTTP: POST /api/v2/generic (InterventionComparison) returns the live, corrected card")
        def _():
            status, body = generic("InterventionComparison", "priya")
            assert status == 200 and len(body["options"]) == 3

        @check("HTTP: every other prior live card remains unaffected")
        def _():
            for path in ("/ultra/rain/james/actionPackage", "/ultra/rain/david/actionPackage",
                        "/ultra/rain/sarah/actionPackage", "/ultra/rain/maria/actionPackage"):
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
