"""The chat built from data equals what the frontend recorded.

chat_v3 builds every persona's context, briefing, answers and matching tables from the backend's data
(here the seed file, the same data loaded into rain_v3.ui_v3.dataset, before the live public overlay).
Each must equal the fixtures the frontend exported (rain-api/fixtures/ultra_v3/*.json), which proves the
backend reproduces the designed conversation exactly. No database needed.
Run from rain-api/:  python -m pytest test_chat_v3_build.py -q
"""
import json
from pathlib import Path

import pytest

import chat_v3

HERE = Path(__file__).resolve().parent
SEED = json.loads((HERE / "seed" / "rain_v3_ui_data.json").read_text(encoding="utf-8"))["sections"]
FIXTURES = HERE / "fixtures" / "ultra_v3"
PERSONAS = ["rain_ceo", "rain_cmo", "rain_cio", "rain_state", "rain_chw", "rain_access"]


@pytest.fixture(scope="module")
def built():
    return {pid: chat_v3.build_persona(SEED, pid) for pid in PERSONAS}


@pytest.mark.parametrize("pid", PERSONAS)
@pytest.mark.parametrize("part", ["context", "briefing", "match"])
def test_part_equals_recording(built, pid, part):
    recorded = json.loads((FIXTURES / f"{pid}.json").read_text(encoding="utf-8"))
    assert built[pid][part] == recorded[part]


@pytest.mark.parametrize("pid", PERSONAS)
def test_every_answer_equals_recording(built, pid):
    recorded = json.loads((FIXTURES / f"{pid}.json").read_text(encoding="utf-8"))["turns"]
    assert set(built[pid]["turns"]) == set(recorded)
    for key, turn in recorded.items():
        assert built[pid]["turns"][key] == turn, key
