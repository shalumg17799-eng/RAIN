"""The v0.4 chat built from data: the six v0.3 operators still equal what the frontend recorded, and all seven build.

chat_v4 builds every persona's context, briefing, answers and matching tables from the backend's data
(here the seed file, the same data loaded into rain_v4.ui_v4.dataset, before the live public overlay).
Each must equal the fixtures the frontend exported (rain-api/fixtures/ultra_v3/*.json), which proves the
backend reproduces the designed conversation exactly. No database needed.
Run from rain-api/:  python -m pytest test_chat_v4_build.py -q
"""
import json
from pathlib import Path

import pytest

import chat_v4

HERE = Path(__file__).resolve().parent
SEED = json.loads((HERE / "seed" / "rain_v4_ui_data.json").read_text(encoding="utf-8"))["sections"]
FIXTURES = HERE / "fixtures" / "ultra_v3"
PERSONAS = ["rain_ceo", "rain_cmo", "rain_cio", "rain_state", "rain_chw", "rain_access"]


@pytest.fixture(scope="module")
def built():
    return {pid: chat_v4.build_persona(SEED, pid) for pid in PERSONAS}


V4_PERSONAS = list(SEED["constants"]["PERSONAS"].values())


@pytest.mark.parametrize("pid", PERSONAS)
@pytest.mark.parametrize("part", ["context", "briefing", "match"])
def test_part_equals_recording(built, pid, part):
    recorded = json.loads((FIXTURES / f"{pid}.json").read_text(encoding="utf-8"))
    if part == "context":  # v0.4 lists seven personas (the patient joins the switcher) and a new tagline; the rest is unchanged
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
    assert use_case_a == (len(chat["context"]["persona"]["capabilities"]) == 6)


@pytest.mark.parametrize("pid", PERSONAS)
def test_every_answer_equals_recording(built, pid):
    recorded = json.loads((FIXTURES / f"{pid}.json").read_text(encoding="utf-8"))["turns"]
    assert set(built[pid]["turns"]) == set(recorded)
    for key, turn in recorded.items():
        assert built[pid]["turns"][key] == turn, key
