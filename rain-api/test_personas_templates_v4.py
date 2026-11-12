"""The patient persona (linda): every number comes from data, and she sees only her own record.

Pure checks (no database):
  - no digit in their contract and copy templates sits outside a {{ ... }} placeholder, except an explicit
    allow-list of ids, rules and units (140/90, the 72/24/3 hour reminder plan, 270/271, per 1,000, CMS ids);
  - the patient's templates read only her computed record and datasets, never row-level records.
Database checks (rain_v4, skipped without it):
  - every template renders against the context metrics_v4 computes now;
  - every placeholder CHANGES when the values it reads change (each value it resolves is perturbed);
  - her datasets carry no other member's id or name.
Run from rain-api/:  python -m pytest test_personas_templates_v4.py -q
"""
import itertools
import json
import os
import re
from pathlib import Path

import pytest

import templating_v4 as T

HERE = Path(__file__).resolve().parent
TPL = json.loads((HERE / "seed" / "rain_v4_ui_templates.json").read_text(encoding="utf-8"))
KEYS = ("linda",)
OWN = {"linda": ("constants.PATIENTS.linda", "lg_")}

# Literal digits a template may keep: identifiers, rules and units, never a measured value.
ALLOW = [r"\b[A-Z]{3}-[SP]\d\b", r"\bCMS\d+\b", r"140/90", r"72, 24 and 3 hours", r"\b(?:72|24|3)-hour\b",
         r"270/271", r"\bper 1,000\b", r"\bper 100,000\b", r"December 31"]


def strings(obj, path=""):
    """Every string value in a template, with its path (dict keys are structure, not text)."""
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from strings(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from strings(v, f"{path}/{i}")


def placeholders(key):
    for sec in ("contracts", "personas"):
        for path, text in strings(TPL[sec][key], f"{sec}.{key}"):
            for m in T.PLACEHOLDER.finditer(text):
                yield path, m.group(1).strip()


@pytest.mark.parametrize("key", KEYS)
def test_no_digit_outside_a_placeholder(key):
    bad = []
    for sec in ("contracts", "personas"):
        for path, text in strings(TPL[sec][key], f"{sec}.{key}"):
            if path.endswith("/id"):          # signal, KPI and notification ids
                continue
            rest = T.PLACEHOLDER.sub(" ", text)
            for pattern in ALLOW:
                rest = re.sub(pattern, " ", rest)
            if re.search(r"\d", rest):
                bad.append(f"{path}: {text!r}")
    assert not bad, "literal numbers outside placeholders:\n" + "\n".join(bad)


@pytest.mark.parametrize("key", KEYS)
def test_no_em_dash_and_every_template_has_placeholders(key):
    text = json.dumps([TPL["contracts"][key], TPL["personas"][key]], ensure_ascii=False)
    assert "—" not in text
    assert len(list(placeholders(key))) >= 20


@pytest.mark.parametrize("key", KEYS)
def test_each_persona_reads_only_its_own_scope(key):
    own_path, own_prefix = OWN[key]
    for path, body in placeholders(key):
        assert "records." not in body, f"{path} reads row-level records: {body}"
        for m in re.finditer(r"constants\.(PATIENTS\.\w+)", body):
            assert f"constants.{m.group(1)}" == own_path, f"{path} reads another persona's data: {body}"
        for m in re.finditer(r"datasets\.(\w+)", body):
            assert m.group(1).startswith(own_prefix), f"{path} reads dataset {m.group(1)}"
        for m in re.finditer(r"SCOPES\.(\w+)", body):
            assert m.group(1) == key, f"{path} reads another scope: {body}"
    for vid, v in TPL["contracts"][key]["viz"].items():
        ds = v["props"].get("dataset")
        assert ds is None or ds.startswith(own_prefix), f"{key}.{vid} draws {ds}"
        assert v["type"] != "query_table", f"{key}.{vid} runs a pack query"
        if v["type"] == "rain.task_briefing":
            assert v["props"]["role"] == key


def test_the_patient_opens_only_her_own_view():
    assert TPL["contracts"]["linda"]["workbenches"] == [{"id": "patientView", "access": "full", "scope": "self"}]
    assert not TPL["contracts"]["linda"]["signals"]          # a task briefing, no insight signals


def test_only_the_seven_personas_have_templates():
    keys = ["ceo", "cmo", "cio", "state", "chw", "access", "linda"]
    assert list(TPL["contracts"]) == keys and list(TPL["personas"]) == keys
    assert {m["persona"] for m in TPL["mapping"]} <= set(keys)


# ─── against the computed context ─────────────────────────────────────────────────────────────────────────
def _ctx():
    import psycopg2
    import metrics_v4
    try:
        conn = psycopg2.connect(host=os.getenv("PG_HOST", "127.0.0.1"), port=os.getenv("PG_PORT", "5432"),
                                dbname=os.getenv("PG_DB_V4", "rain_v4"), user=os.getenv("PG_USER", "rain_app"),
                                password=os.getenv("PG_PASSWORD", "rain_dev_pw"), connect_timeout=3)
    except Exception:
        return None
    with conn, conn.cursor() as cur:
        ctx = metrics_v4.compute(cur)
    conn.close()
    return json.loads(json.dumps(ctx, default=str))


CTX = _ctx()
needs_db = pytest.mark.skipif(CTX is None, reason="rain_v4 database not reachable")


@needs_db
@pytest.mark.parametrize("key", KEYS)
def test_templates_render_against_the_computed_context(key):
    for sec in ("contracts", "personas"):
        out = T.render_obj(TPL[sec][key], CTX)
        assert "{{" not in json.dumps(out, ensure_ascii=False)
    for s in TPL["contracts"][key]["signals"]:
        assert len(T.render(s["description"], CTX)) <= 100, s["id"]


def _perturb(v, i):
    """A different value of the same kind: numbers scaled and shifted, text marked, lists grown."""
    factor, shift = 1.37 + 0.29 * i, 3 + 2 * i
    if isinstance(v, bool):
        return not v
    if isinstance(v, int):
        return int(v * factor) + shift + 1
    if isinstance(v, float):
        return v * factor + shift + 0.5
    if isinstance(v, str):
        return v + f" (changed {i})"
    if isinstance(v, list):
        if v and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
            out = [_perturb(x, i) for x in v]
        else:
            out = list(v) + [v[0] if v else {}]
        return T._Sel(out) if isinstance(v, T._Sel) else out
    return v


def _evaluate_perturbed(body, ctx):
    original, calls = T._resolve, itertools.count()

    def resolve(segments, sections, c):
        value, where = original(segments, sections, c)
        if isinstance(value, T._Sel) and len(value) == 1 and not isinstance(value[0], (dict, list)):
            return T._Sel([_perturb(value[0], next(calls))]), where     # a single selected scalar
        return _perturb(value, next(calls)), where
    T._resolve = resolve
    try:
        return T.evaluate(body, ctx)
    finally:
        T._resolve = original


@needs_db
@pytest.mark.parametrize("key", KEYS)
def test_every_placeholder_changes_when_its_source_changes(key):
    unchanged = []
    for path, body in placeholders(key):
        before = T._to_text(T.evaluate(body, CTX), body)
        after = T._to_text(_evaluate_perturbed(body, CTX), body)
        if before == after:
            unchanged.append(f"{path}: {{{{ {body} }}}} -> {before!r}")
    assert not unchanged, "placeholders that do not follow their data:\n" + "\n".join(unchanged)


@needs_db
def test_the_patients_datasets_are_only_hers():
    me = CTX["constants"]["PATIENTS"]["linda"]
    assert list(CTX["constants"]["PATIENTS"]) == ["linda"]
    mine = json.dumps({k: v for k, v in CTX["datasets"].items() if k.startswith("lg_")}, ensure_ascii=False)
    others = [m for m in CTX["records"]["campaignMembers"] if m["id"] != me["memberId"]]
    assert not [m["id"] for m in others if m["id"] in mine]
    assert not [m["name"] for m in others if m["name"] in mine]
