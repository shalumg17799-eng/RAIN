"""Parity: the backend's /api/v4/ui2 answers against the new UI's own scripted answers, on the same live data.

The new UI (frontend/ultra-rain-v2) builds its conversation from its persona contracts in `recorded` mode; in the
browser it runs in `http` mode against rain-api/ui2_v4.py, which builds the same payloads in Python (chat_v4). This
walks every persona's briefing and every chip reachable from it, asks both, and reports any difference.

  1. snapshot the live data:   cd frontend/ultra-rain-v2 && npm run fixtures:backend
  2. start the UI's mock API:  RAIN_DATA_SNAPSHOT=src/test/fixtures/rain_v4_ui2_live.json npm run mock-api
  3. run:                      python scripts/e2e/ui2_parity_check.py [--backend http://localhost:8003] [--mock http://localhost:5650]

Expected differences: a typed persona-pack question is answered live by the backend (`query:<id>` turns), which the
recorded mode cannot do; and the backend's context carries the v0.4 branding's `client.tagline`, which the UI does not
read (it takes its tagline from its own client manifest), so that one field is ignored here.
"""
import argparse
import json
import sys
import urllib.request

PERSONAS = ["rain_ceo", "rain_cmo", "rain_cio", "rain_state", "rain_chw", "rain_access", "rain_patient"]


def call(base: str, method: str, path: str, body=None):
    req = urllib.request.Request(base + path, method=method, headers={"Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None


def diff(a, b, path="", out=None, limit=6):
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    num = (int, float)
    if isinstance(a, num) and isinstance(b, num) and not isinstance(a, bool) and not isinstance(b, bool):
        if a != b:   # 7.0 from Python and 7 from JavaScript are the same JSON number
            out.append(f"{path}: {a!r} != {b!r}")
        return out
    if type(a) != type(b):
        out.append(f"{path}: {str(a)[:120]!r} != {str(b)[:120]!r}")
    elif isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}.{k}: only in {'backend' if k in a else 'ui'}")
            else:
                diff(a[k], b[k], f"{path}.{k}", out, limit)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append(f"{path}: {len(a)} items != {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}[{i}]", out, limit)
    elif a != b:
        out.append(f"{path}: {str(a)[:120]!r} != {str(b)[:120]!r}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="http://localhost:8003")
    ap.add_argument("--mock", default="http://localhost:5650")
    a = ap.parse_args()
    be, ui = a.backend.rstrip("/") + "/api/v4/ui2", a.mock.rstrip("/")
    total = same = 0
    problems: list[str] = []
    for pid in PERSONAS:
        q = f"?clientId=rain&personaId={pid}"
        for ep in ("/context", "/briefing"):
            total += 1
            s1, b1 = call(be, "GET", ep + q)
            s2, b2 = call(ui, "GET", ep + q)
            if ep == "/context" and b1 and b2 and "tagline" not in b2.get("client", {}):
                b1.get("client", {}).pop("tagline", None)
            d = diff(b1, b2) if s1 == s2 == 200 else [f"status {s1} vs {s2}"]
            if d:
                problems.append(f"{pid} {ep}: " + "; ".join(d))
            else:
                same += 1
        _, brief = call(ui, "GET", "/briefing" + q)
        seen, queue = set(), list((brief or {}).get("chips", []))
        while queue:
            chip = queue.pop(0)
            if chip in seen:
                continue
            seen.add(chip)
            body = {"clientId": "rain", "personaId": pid, "input": chip}
            s1, t1 = call(be, "POST", "/ask", body)
            s2, t2 = call(ui, "POST", "/ask", body)
            total += 1
            if s1 == 200 and str(t1.get("id", "")).startswith("query:"):
                problems.append(f"{pid} ask {chip!r}: backend ran persona query {t1['id']} (expected: live query)")
                continue
            d = diff(t1, t2) if s1 == s2 == 200 else [f"status {s1} vs {s2}"]
            if d:
                problems.append(f"{pid} ask {chip!r} ({(t2 or {}).get('id')}): " + "; ".join(d))
            else:
                same += 1
            queue.extend((t2 or {}).get("chips", []))
    print(f"{same} of {total} payloads identical (backend /api/v4/ui2 vs the UI's recorded answers on the same data)")
    for p in problems:
        print("  -", p)
    return 0 if same == total else 1


if __name__ == "__main__":
    sys.exit(main())
