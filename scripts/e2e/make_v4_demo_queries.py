"""Write doc/queries/RAIN_v4_demo_queries.md: 3 synthetic-data and 3 public-data queries per persona (14 personas),
taken from the verified query pack (doc/queries/rain_v4_persona_queries.sql), with the question to type in the
persona's Ask AI box, the tables each one reads, the rows it returns now, and its SQL.

    python scripts/e2e/make_v4_demo_queries.py          (row counts: artifacts/rain-v4-validation/pack_results.json)
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACK = (ROOT / "doc/queries/rain_v4_persona_queries.sql").read_text(encoding="utf-8")
RESULTS = {r["id"]: r for r in json.loads((ROOT / "artifacts/rain-v4-validation/pack_results.json").read_text(encoding="utf-8"))}
OUT = ROOT / "doc/queries/RAIN_v4_demo_queries.md"
PER_KIND = 3
UI_ID = {"patient_linda_garcia": "rain_linda", "patient_rosa_martinez": "rain_rosa", "payer_hannah_lee": "rain_hannah"}

# persona headers ("-- CEO - Gregory Haskins, MBA (Chief Executive Officer): ...") and query blocks, in file order
order, title, queries = [], {}, {}
current = None
for m in re.finditer(r"^-- (?P<head>[A-Z][A-Za-z ]* - [^\n]+)\n|^-- @id (?P<id>\S+)\n-- @persona (?P<persona>\S+)\n-- @data (?P<data>\S+)\n"
                     r"-- @question (?P<q>[^\n]+)\n(?P<sql>.*?;)\n", PACK, re.M | re.S):
    if m.group("head") and " - " in m.group("head") and not m.group("head").startswith(("RAIN v0.4", "Schemas")):
        current = m.group("head").split(":")[0]
        continue
    if not m.group("id"):
        continue
    p = m.group("persona")
    if p not in title:
        order.append(p)
        title[p] = current or p
    queries.setdefault(p, []).append({"id": m.group("id"), "data": m.group("data"), "question": m.group("q").strip(),
                                      "sql": m.group("sql").strip()})


def tables(sql):
    seen = []
    for s, t in re.findall(r"\b(synthetic|public_data)\.(\w+)", sql):
        if f"{s}.{t}" not in seen:
            seen.append(f"{s}.{t}")
    return seen


def block(q):
    r = RESULTS.get(q["id"], {})
    rows = r.get("rows")
    cols = ", ".join(f"`{c}`" for c in (r.get("columns") or [])[:8]) + (" …" if len(r.get("columns") or []) > 8 else "")
    return [f"**{q['id']}**: {q['question']}", "",
            f"- Type in Ask AI: `{q['question']}` (or just `{q['id']}`)",
            f"- Reads: {', '.join(f'`{t}`' for t in tables(q['sql']))}",
            f"- Returns now: {rows if rows is not None else '?'} row{'s' if rows != 1 else ''}" + (f"; columns {cols}" if cols else ""),
            "", "```sql", q["sql"], "```", ""]


total = sum(min(PER_KIND, sum(1 for q in queries[p] if q["data"] == kind)) for p in order for kind in ("synthetic", "public"))
w = ["# RAIN v0.4: demo queries, 3 synthetic-data and 3 public-data per persona", "",
     f"{len(order)} personas, {total} queries, taken from the verified query pack `doc/queries/rain_v4_persona_queries.sql` "
     "(140 queries, every one returning rows and rendering a live table in the browser chat). Database `rain_v4`:",
     "",
     "- **Synthetic data** (`synthetic`, 59 tables): row-level operational data for the Q3 checkpoint, the same rows every "
     "number in the UI is computed from.",
     "- **Public data** (`public_data`, 24 tables): real public datasets for Nevada and Tennessee (CDC PLACES, CDC/ATSDR SVI, "
     "HRSA HPSA and health center sites, Census ACS, CMS hospitals, County Health Rankings, OSRM drive times, ...).",
     "",
     "## How to run them", "",
     "| Where | How |", "|---|---|",
     "| The app (chat) | Sign in at http://localhost:8184/login/rain/?access=rain@9705, open the persona (`http://localhost:8184/ask?persona=<persona id>`), and type the question or the query id in the Ask AI box. The answer is a live table from Postgres. |",
     "| The API | `GET http://localhost:8003/api/v4/queries/<id>` runs one read-only and returns its rows; `GET http://localhost:8003/api/v4/queries?persona=<persona id>` lists a persona's queries. |",
     "| pgAdmin | http://localhost:5052 (`admin@rain.app` / `admin`): open `rain_v4_persona_queries.sql` from its file storage, select one query and press F5, or paste the SQL below into a Query Tool on `rain_v4`. |",
     "",
     "Row counts are from the last run of the pack against the current data; the write-back flow (bookings, readings, "
     "replies) can move the synthetic ones.", "",
     "## Personas", ""]
for p in order:
    ui = UI_ID.get(p, p)
    w.append(f"- [{title[p]}](#{re.sub(r'[^a-z0-9 -]', '', title[p].lower()).replace(' ', '-')}) (`{ui}`)")
w.append("")
for p in order:
    ui = UI_ID.get(p, p)
    w += [f"## {title[p]}", "", f"Persona id in the app: `{ui}` · open: http://localhost:8184/ask?persona={ui}"
          + (f" · query pack persona: `{p}`" if p != ui else ""), ""]
    for kind, label in (("synthetic", "Synthetic data"), ("public", "Public data")):
        w += [f"### {label}", ""]
        for q in [q for q in queries[p] if q["data"] == kind][:PER_KIND]:
            w += block(q)
OUT.write_text("\n".join(w), encoding="utf-8", newline="\n")
print(f"wrote {OUT.relative_to(ROOT)}: {len(order)} personas, {total} queries")
