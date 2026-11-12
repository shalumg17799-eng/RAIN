"""Port the v3 backend tests to v4 (renames plus v0.4 additions)."""
from pathlib import Path

API = Path(__file__).resolve().parents[2] / "rain-api"
SUBS = [("rain_v3", "rain_v4"), ("ui_v3", "ui_v4"), ("chat_v3", "chat_v4"), ("ultra_v3_api", "ultra_v4_api"),
        ("persona_queries_v3", "persona_queries_v4"), ("ui_data_v3", "ui_data_v4"), ("/api/v3/", "/api/v4/"),
        ("PG_DB_V3", "PG_DB_V4"), ("test_chat_v3", "test_chat_v4"), ("test_ui_data_v3", "test_ui_data_v4"),
        ("test_persona_queries_v3", "test_persona_queries_v4"), ("test_chat_queries_v3", "test_chat_queries_v4"),
        ("load_ui_data.py", "load_ui_data_v4.py")]


def port(src, dst, extra):
    s = (API / src).read_text(encoding="utf-8")
    for a, b in SUBS:
        s = s.replace(a, b)
    for a, b in extra:
        assert a in s, (dst, a[:70])
        s = s.replace(a, b, 1)
    (API / dst).write_text(s, encoding="utf-8", newline="\n")
    print("wrote", dst)


port("test_chat_v3_build.py", "test_chat_v4_build.py", [
    ('"""The chat built from data equals what the frontend recorded.',
     '"""The v0.4 chat built from data: the six v0.3 personas still equal what the frontend recorded, and all eleven build.'),
    ('''@pytest.mark.parametrize("pid", PERSONAS)
@pytest.mark.parametrize("part", ["context", "briefing", "match"])
def test_part_equals_recording(built, pid, part):
    recorded = json.loads((FIXTURES / f"{pid}.json").read_text(encoding="utf-8"))
    assert built[pid][part] == recorded[part]''',
     '''V4_PERSONAS = list(SEED["constants"]["PERSONAS"].values())


@pytest.mark.parametrize("pid", PERSONAS)
@pytest.mark.parametrize("part", ["context", "briefing", "match"])
def test_part_equals_recording(built, pid, part):
    recorded = json.loads((FIXTURES / f"{pid}.json").read_text(encoding="utf-8"))
    if part == "context":  # v0.4 lists eleven personas and a new tagline; the rest of the context is unchanged
        def keep(c):
            return {k: v for k, v in c.items() if k not in ("personas", "client")}
        assert keep(built[pid][part]) == keep(recorded[part])
        assert [p["id"] for p in built[pid][part]["personas"]] == V4_PERSONAS
        return
    assert built[pid][part] == recorded[part]


@pytest.mark.parametrize("pid", V4_PERSONAS)
def test_every_v04_persona_builds_and_routes(pid):
    """Every persona builds; every chip and scripted question routes to a turn that exists."""
    chat = chat_v4.build_persona(SEED, pid)
    turns, match = chat["turns"], chat["match"]
    assert chat["briefing"]["greeting"]["id"].endswith("_brief")
    assert "__default__" in turns
    for chip in chat["briefing"]["chips"]:
        assert match["chipToFlowKey"].get(chip) in turns, chip
    for t in turns.values():
        for chip in t["chips"]:
            assert match["chipToFlowKey"].get(chip) in turns, (t["id"], chip)
    use_case_a = bool(chat["briefing"]["signals"])
    assert use_case_a == (len(chat["context"]["persona"]["capabilities"]) == 6)'''),
])

port("test_chat_v3_live.py", "test_chat_v4_live.py", [
    ("Edits contracts.ceo (an answer's text) and datasets.lv_top5 (a table the CMO's answer draws) in",
     "Edits contracts.ceo (an answer's text), datasets.lv_top5 (a table an answer draws) and contracts.hargrove\n(a v0.2 persona brought into v0.4) in"),
    ('''def test_public_figures_in_answers_are_live():''', '''def test_v02_persona_answer_follows_the_database():
    original = _get("contracts", "hargrove")
    try:
        edited = json.loads(json.dumps(original))
        edited["steps"]["hg_mix"]["ai"] = "EDITED IN POSTGRES: this answer comes from the database."
        _put("contracts", "hargrove", edited)
        r = ask("rain_hargrove", "Walk me through the clinic risk mix")
        assert r.json()["id"] == "hg_mix" and r.json()["text"].startswith("EDITED IN POSTGRES")
    finally:
        _put("contracts", "hargrove", original)


def test_query_table_answers_are_live_public_rows():
    """Marcus Bell's 'public datasets' answer runs BEL-P1 live: its rows are the public_data tables right now."""
    turn = ask("rain_bell", "What public datasets back the county view?").json()
    assert turn["id"] == "mb_datasets"
    stack = next(c for c in turn["components"] if c["type"] == "stack")
    rows = next(ch for ch in stack["props"]["children"] if ch["type"] == "data_table")["props"]["rows"]
    names = {r["public_table"] for r in rows}
    assert {"acs_county", "osrm_nearest_site", "uds_health_center_cqm", "cdc_places"} <= names
    assert all(r["row_count"] > 0 for r in rows)


def test_public_figures_in_answers_are_live():'''),
])

port("test_chat_queries_v3.py", "test_chat_queries_v4.py", [
    ('QUERIES = sorted(pq._pack().values(), key=lambda q: q["id"])',
     '# Patients have no chat (they use SMS); their queries run through GET /api/v4/queries instead.\n'
     'QUERIES = sorted((q for q in pq._pack().values() if q["persona"].startswith("rain_")), key=lambda q: q["id"])'),
    ('''    assert_query_turn(ask("rain_state", "households without internet by county for broadband"), "STATE-P4")''',
     '''    assert_query_turn(ask("rain_state", "households without internet by county for broadband"), "STATE-P4")
    assert_query_turn(ask("rain_okafor", "OKA-P2"), "OKA-P2")
    assert_query_turn(ask("rain_brooks", "how long is the drive from battle mountain zip 89820 to the nearest health center sites"), "BRK-P1")'''),
    ('''    assert ask("rain_state", "Show me the county view").json()["id"] == "st_county"''',
     '''    assert ask("rain_state", "Show me the county view").json()["id"] == "st_county"
    assert ask("rain_brooks", "Open the front-desk inbox").json()["id"] == "kb_inbox"
    assert ask("rain_okafor", "Walk me through this week's schedule").json()["id"] == "so_week"'''),
])

port("test_persona_queries_v3.py", "test_persona_queries_v4.py", [
    ('    assert body["count"] == 60', '    assert body["count"] == 130'),
])

port("test_ui_data_v3.py", "test_ui_data_v4.py", [
    ('    assert set(body["sections"]["contracts"]) == {"ceo", "cmo", "cio", "state", "chw", "access"}',
     '    assert set(body["sections"]["contracts"]) == {"ceo", "cmo", "hargrove", "cio", "state", "bell", "chw", "holloway",\n'
     '                                                 "access", "brooks", "okafor"}\n'
     '    assert len(body["sections"]["records"]["previsitSummaries"]) == 8\n'
     '    assert len(body["sections"]["records"]["inboxItems"]) == 8'),
    ('''    assert {s["id"] for s in live} == {"rain-places", "rain-svi", "rain-hpsa", "rain-rucc", "rain-zcta",
                                       "rain-hrsaSites", "rain-nppes"}''',
     '''    assert {s["id"] for s in live} == {"rain-places", "rain-svi", "rain-hpsa", "rain-rucc", "rain-zcta",
                                       "rain-hrsaSites", "rain-nppes", "rain-acs", "rain-forhp", "rain-boundaries",
                                       "rain-cmsHospital", "rain-cmsPos", "rain-uds", "rain-ecqm", "rain-osm"}'''),
    ('''def test_unknown_client_is_404():''', '''def test_blocked_sources_say_so_instead_of_illustrative_counts(response):
    by_id = {s["id"]: s for s in response.json()["sections"]["sources"]["PUBLIC_SOURCES"]}
    for sid in ("rain-fcc", "rain-geovar", "rain-chr"):
        assert by_id[sid]["recordCount"] == 0 and by_id[sid]["freshness"].startswith("Not loaded yet"), sid


def test_live_kpis_are_counted_from_public_data(response):
    kpis = {k["id"]: k for k in response.json()["sections"]["contracts"]["bell"]["kpis"]}
    with ui_data_v4._conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM public_data.health_center_sites WHERE site_state_abbreviation = 'NV'")
        sites = cur.fetchone()[0]
    assert kpis["hcSites"]["value"] == f"{sites:,}"
    assert kpis["hcSites"]["liveSource"] == "public_data.health_center_sites"
    assert kpis["ruralFacilities"]["value"] not in ("live", "Not loaded")


def test_unknown_client_is_404():'''),
])
