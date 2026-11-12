"""End-to-end check of the v0.4 write-back flow against the running API: each action changes rows, and the
next GET /api/v4/ui/data shows the change (computed, not stored). Ends with /reset and checks that every
value is back. Writes doc/queries/RAIN_v4_flow_check.md.

    python scripts/e2e/flow_check_v4.py [http://localhost:8003]
"""
import json
import sys
import urllib.request
from pathlib import Path

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8003").rstrip("/")
ROOT = Path(__file__).resolve().parents[2]


def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def ui():
    status, d = call("GET", "/api/v4/ui/data?clientId=rain")
    assert status == 200, status
    return d["sections"]


def pick(s):
    c, r = s["constants"], s["records"]
    linda = next(m for m in r["campaignMembers"] if m["id"] == c["LINDA"]["memberId"])
    return {"CARE.booked": c["CARE"]["booked"], "CARE.controlled": c["CARE"]["controlled"],
            "CARE.brandonBookings": c["CARE"]["brandonBookings"], "CARE.brandonUnconfirmed": c["CARE"]["brandonUnconfirmed"],
            "CARE.brandonRReplies": c["CARE"]["brandonRReplies"], "CARE.teresaNoCallback": c["CARE"]["teresaNoCallback"],
            "open slots": sum(1 for x in r["slots"] if x.get("status") == "open"),
            "reminders": len(r["reminders"]), "LINDA.readingRecorded": c["LINDA"].get("readingRecorded"),
            "Linda status": linda["status"], "MODEL.version": c["MODEL"]["version"]}


lines, ok = [], True


def step(title, method, path, body, expect):
    global ok
    before = pick(ui())
    status, res = call(method, path, body)
    after = pick(ui())
    changed = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
    good = status == 200 and all(changed.get(k, (None, None))[1] == v for k, v in expect.items())
    ok &= good
    lines.append(f"| {title} | `{method} {path}` | {status} | " + "; ".join(f"{k}: {a} → {b}" for k, (a, b) in changed.items())
                 + f" | {'PASS' if good else 'FAIL'} |")
    print(("PASS" if good else "FAIL"), title, status, changed, "" if good else json.dumps(res)[:300])
    return res


call("POST", "/api/v4/flow/reset")
s0 = ui()
start = pick(s0)
c, r = s0["constants"], s0["records"]
linda = c["LINDA"]["memberId"]
pending = next(b for b in r["pendingBookings"] if b["memberId"] != linda and b["eligibility"] == "Active")
slot = next(x for x in r["slots"] if x.get("status") == "open")
noreply = next(x for x in r["reminders"] if x["status"] == "No reply yet")
pending_ids = {b["memberId"] for b in r["pendingBookings"]}
not_contacted = next(m for m in r["campaignMembers"] if m["status"] == "Not contacted" and m["id"] != linda and m["id"] not in pending_ids)
sys_, dia = map(int, c["LINDA"]["reading"].split("/"))

step("Linda sends her home reading", "POST", "/api/v4/flow/reading", {"memberId": linda, "systolic": sys_, "diastolic": dia},
     {"CARE.controlled": start["CARE.controlled"] + 1, "LINDA.readingRecorded": True})
step(f"Brandon books {pending['name']} into {slot['id']}", "POST", "/api/v4/flow/book",
     {"memberId": pending["memberId"], "slotId": slot["id"], "by": "Brandon Kee"},
     {"CARE.brandonBookings": start["CARE.brandonBookings"] - 1, "open slots": start["open slots"] - 1})
step(f"{noreply['name']} replies C", "POST", "/api/v4/flow/reply", {"memberId": noreply["memberId"], "reply": "C"},
     {"CARE.brandonUnconfirmed": start["CARE.brandonUnconfirmed"] - 1})
step(f"Teresa reaches {not_contacted['name']}", "POST", "/api/v4/flow/contact",
     {"memberId": not_contacted["memberId"] if "memberId" in not_contacted else not_contacted["id"], "outcome": "Reached and booked", "by": "Teresa Lopez, CHW"},
     {"CARE.brandonBookings": start["CARE.brandonBookings"]})   # one booked, one new hand-off: net zero
step("Raj signs off the candidate model", "POST", "/api/v4/flow/signoff", {"who": "cio"}, {})
step("Dr. Castellanos co-signs: the candidate is released", "POST", "/api/v4/flow/signoff", {"who": "cmo"},
     {"MODEL.version": "v1.4"})
st, ev = call("GET", "/api/v4/flow/events")
st, res = call("POST", "/api/v4/flow/reset")
back = pick(ui())
restored = back == start
ok &= restored
print("reset:", res, "restored" if restored else {k: (start[k], back[k]) for k in start if start[k] != back[k]})
out = ROOT / "doc/queries/RAIN_v4_flow_check.md"
out.write_text("\n".join([
    "# RAIN v0.4: write-back flow, end to end", "",
    f"Run against `{BASE}` by `scripts/e2e/flow_check_v4.py`. Each action writes rows in `rain_v4.synthetic` (and one "
    "`synthetic.flow_event` with its undo); the values in the last column are read back from `GET /api/v4/ui/data`, which "
    "computes them from those rows on the next request.", "",
    "| Action | Call | HTTP | What the UI data shows next (before → after) | Check |", "|---|---|---|---|---|", *lines, "",
    f"Flow events logged before the reset: {len(ev)}. `POST /api/v4/flow/reset` undid {res.get('eventsUndone')} events "
    f"({res.get('steps')} steps); every value checked is back to the start: **{'yes' if restored else 'no'}**.", "",
    f"Result: **{'PASS' if ok else 'FAIL'}**", ""]), encoding="utf-8", newline="\n")
sys.exit(0 if ok else 1)
