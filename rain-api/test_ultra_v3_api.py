"""Per-persona checks for the Ultra v3 API (/api/v3/ui) against the PRD v0.3 spec
(doc/prd/RAIN_Prototype_Spec_v2.docx). Every KPI value asserted here is the
spec's number for that persona; every ask is a scripted step whose turn and
capability tag the spec defines.

Run: .venv\\Scripts\\python.exe -m pytest rain-api/test_ultra_v3_api.py -q
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "rain-api")):
    if p not in sys.path:
        sys.path.insert(0, p)
os.chdir(ROOT / "rain-api")

from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402

client = TestClient(main.app)
BASE = "/api/v3/ui"


def briefing(pid):
    r = client.get(f"{BASE}/briefing", params={"clientId": "rain", "personaId": pid})
    assert r.status_code == 200, r.text
    return r.json()


def ask(pid, text):
    r = client.post(f"{BASE}/ask", json={"clientId": "rain", "personaId": pid, "input": text})
    assert r.status_code == 200, r.text
    return r.json()


def kpi_map(b):
    return {k["id"]: k["value"] for k in b["kpis"]}


# ---- the PRD's dashboard KPIs, persona by persona --------------------------------------------

PRD_KPIS = {
    "rain_ceo": {"members": "9,400", "pmpm": "$412 / $386", "above": "+6.7%", "gate": "2 of 5",
                 "lowValue": "$618K", "ed": "312", "days": "58"},
    "rain_cmo": {"gate": "2 of 5", "bp": "58%", "a1c": "34%", "crc": "33%", "lowValue": "2,140",
                 "coding": "73 members", "social": "38% of members"},
    "rain_cio": {"sources": "19 public + 6 synthetic", "claimsLag": "45 days", "adtLag": "Under 1 hour",
                 "subgroup": "Failed", "missing": "57", "social": "38%",
                 "freshness": "Q3 claims, ADT today"},
    "rain_state": {"networks": "4 (18 sites)", "members": "31,600", "counties": "6 rural",
                   "hpsa": "6 of 6", "ed": "298", "lowValue": "$2.4M",
                   "suppressed": "Counts under 11"},
    # Use Case B task briefings (counts from the spec's briefing + worklist screens)
    "rain_chw": {"top": "46", "campaign": "412", "noCallback": "5", "open": "200",
                 "booked": "62 of 412", "controlled": "18"},
    "rain_access": {"bookings": "23", "unconfirmed": "9", "rReplies": "4", "sites": "7 sites"},
}

# Guided steps: (input chip, expected capability tag, text the spec's answer carries)
PRD_STEPS = {
    "rain_ceo": [
        ("Break down the gap", "Converged Conversation", "$26 PMPM gap"),
        ("What can we still recover by December 31?", "Predictive Intelligence", "Three moves"),
        ("Generate the board brief", "Automated Action", "board brief"),
    ],
    "rain_cmo": [
        ("What is happening at Winnemucca?", "Anomaly Detection", "27%"),
        ("Which gaps can we close in 58 days?", "Predictive Intelligence", "Blood pressure is the one to win"),
        ("Launch the BP campaign", "Automated Action", "412 members ranked"),
    ],
    "rain_cio": [
        ("Show me the subgroup result", "Anomaly Detection", "frontier members are ranked lower"),
        ("What changes if we fix it?", "Predictive Intelligence", "18% to 3%"),
        ("Generate the governance packet", "Automated Action", "sign-off"),
    ],
    "rain_state": [
        ("Show me the county view", "Converged Conversation", "Lander and Pershing"),
        ("Where should Outcomes Accelerator funds go first?", "Predictive Intelligence", "fund A and C together"),
        ("Generate the CMS progress summary", "Automated Action", "suppressed"),
    ],
    # Use Case B: task-scoped, no capability tags (spec "Delineation")
    "rain_chw": [("Open my worklist", None, "46")],
    "rain_access": [("Start bookings", None, "booking")],
}

PERSONAS = list(PRD_KPIS)

IDENTITY = {
    "rain_ceo": ("Gregory Haskins, MBA", "Chief Executive Officer"),
    "rain_cmo": ("Dr. Naomi Castellanos", "Chief Medical Officer and Value-Based Care Quality Lead"),
    "rain_cio": ("Raj Malhotra", "Chief Information Officer and Data and AI Governance Lead"),
    "rain_state": ("Dr. Lauren Pike", "Program Lead, Rural Health Outcomes Accelerator"),
    "rain_chw": ("Teresa Lopez, CHW", "Community Health Worker and Care Coordinator"),
    "rain_access": ("Brandon Kee", "Patient Access Coordinator"),
}


@pytest.mark.parametrize("pid", PERSONAS)
def test_context_identity_and_switcher(pid):
    r = client.get(f"{BASE}/context", params={"clientId": "rain", "personaId": pid})
    assert r.status_code == 200, r.text
    ctx = r.json()
    name, role = IDENTITY[pid]
    assert ctx["persona"]["name"] == name
    assert ctx["persona"]["role"] == role
    assert ctx["client"]["id"] == "rain"
    # the switcher offers all six operator personas (the patient is /patient, not a persona)
    assert [p["id"] for p in ctx["personas"]] == PERSONAS
    assert ctx["dataSources"], "Data Sources page must not be empty"


@pytest.mark.parametrize("pid", PERSONAS)
def test_briefing_kpis_match_the_prd(pid):
    got = kpi_map(briefing(pid))
    for kpi_id, value in PRD_KPIS[pid].items():
        assert got.get(kpi_id) == value, f"{pid} KPI {kpi_id}: expected {value!r}, got {got.get(kpi_id)!r}"


@pytest.mark.parametrize("pid", PERSONAS)
def test_briefing_shape_per_use_case(pid):
    b = briefing(pid)
    assert b["greeting"]["text"].startswith("Good morning")
    if pid in ("rain_chw", "rain_access"):
        assert b["signals"] == [], f"{pid} is Use Case B: task briefing, no signal cards"
    else:
        assert len(b["signals"]) == 3, f"{pid} must carry the spec's three priority signals"
    assert b["chips"], "briefing must offer starter chips"


@pytest.mark.parametrize("pid", PERSONAS)
def test_guided_steps_answer_with_the_right_turn(pid):
    for text, capability, must_contain in PRD_STEPS[pid]:
        turn = ask(pid, text)
        assert turn["id"] != "__default__", f"{pid}: {text!r} fell through to the default turn"
        assert must_contain.lower() in turn["text"].lower(), \
            f"{pid}: {text!r} answered by {turn['id']} without {must_contain!r}"
        if capability:
            assert turn.get("capability") == capability, \
                f"{pid}: {text!r} expected capability {capability!r}, got {turn.get('capability')!r}"
        else:
            assert "capability" not in turn, f"{pid} is Use Case B: no capability tags"
        assert turn["components"], f"{pid}: {text!r} must carry the spec's visualization components"


@pytest.mark.parametrize("pid", PERSONAS)
def test_loose_matching_variants_hit_the_same_turn(pid):
    text = PRD_STEPS[pid][0][0]
    reference = ask(pid, text)["id"]
    assert ask(pid, text.lower())["id"] == reference
    assert ask(pid, text.rstrip("?").upper())["id"] == reference


@pytest.mark.parametrize("pid", PERSONAS)
def test_unknown_input_returns_the_default_turn(pid):
    turn = ask(pid, "xyzzy blorp unrelated gibberish")
    assert turn["id"] == "__default__"
    assert turn["text"]


def test_unknown_persona_and_client_404():
    assert client.get(f"{BASE}/briefing", params={"clientId": "rain", "personaId": "nope"}).status_code == 404
    assert client.get(f"{BASE}/briefing", params={"clientId": "acme", "personaId": "rain_ceo"}).status_code == 404


def test_catalog_served():
    # The same file the app's mock API serves: docs/catalog/catalog.json.
    r = client.get(f"{BASE}/catalog")
    assert r.status_code == 200
    catalog = r.json()
    assert catalog.get("contractVersion")
    assert catalog.get("components"), "catalog must list the component types"
