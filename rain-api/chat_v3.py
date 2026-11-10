"""RAIN v0.3 chat, built from data: every briefing and answer is made at request time from the backend's data.

The persona contracts (steps: text, chips, sources, capability, bullet points and the visuals each step draws),
the chart datasets, the records and the master numbers all live in Postgres `rain_v3.ui_v3.dataset`
(ui_data_v3.load_sections, with live public figures). This module turns them into the Ultra API payloads:

  build_persona(sections, persona_id) -> {"context", "briefing", "turns", "match"}

It is a faithful port of the frontend builder (markets/sled/clients/rain: buildPersona.ts, flowKit.ts,
answers.ts; data/rain/_shared/context.ts; core/contract/aiTurn.ts, signal.ts; core/api/recorded.ts).
test_chat_v3_build.py proves it: built from the seed data, every persona's context, briefing, turns and
match tables equal the recordings the frontend exported (rain-api/fixtures/ultra_v3/*.json).
"""
import math
import re

PERSONA_KEYS = ("ceo", "cmo", "cio", "state", "chw", "access")
A_CAPABILITIES = ["Proactive Intelligence", "Converged Conversation", "Anomaly Detection", "Predictive Intelligence",
                  "Friction Observability", "Automated Action"]
B_CAPABILITIES = ["Converged Conversation", "Automated Action"]
NOTE = "Synthetic data for a demo; every person and organization is fictional."
DEFAULT_FLOW_KEY = "__default__"


# ─── JavaScript-compatible formatting (the answers must read exactly as the app writes them) ─────────────

def js(n) -> str:
    """`${n}` in JavaScript: 12 → "12", 12.0 → "12", 5.5 → "5.5"."""
    if isinstance(n, bool):
        return "true" if n else "false"
    if isinstance(n, float) and n.is_integer():
        return str(int(n))
    return str(n)


def js_round(x: float) -> int:
    """Math.round: halves round up."""
    return int(math.floor(x + 0.5))


def num(n) -> str:
    """n.toLocaleString('en-US') for the integers the answers format."""
    if isinstance(n, float) and not n.is_integer():
        whole, frac = f"{n:,.3f}".rstrip("0").split(".")
        return f"{whole}.{frac}" if frac else whole
    return f"{int(n):,}"


def usd_k(n) -> str:
    return f"${js_round(n / 1000):,}K"


def loose(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[?.!,':]", "", t.lower())).strip()


def spec(type_: str, props: dict | None = None, version: int = 1) -> dict:
    return {"type": type_, "version": version, "props": props or {}}


def stat(label, value, caption=None, status=None) -> dict:
    return spec("stat", {"label": label, "value": value, **({"caption": caption} if caption else {}),
                         **({"status": status} if status else {})})


def grid(columns: int, children: list) -> dict:
    return spec("grid", {"columns": columns, "children": children})


# ─── Context answers (data/rain/_shared/context.ts), built for "no selection" like the API ───────────────

class _Data:
    def __init__(self, s: dict):
        c, r, g, src = s["constants"], s["records"], s["governance"], s["sources"]
        self.BP, self.CONTRACT, self.COUNTIES, self.GAP = c["BP"], c["CONTRACT"], c["COUNTIES"], c["GAP"]
        self.LINDA, self.LV_MEASURES, self.MEASURES, self.ORG = c["LINDA"], c["LV_MEASURES"], c["MEASURES"], c["ORG"]
        self.SEGMENTS, self.SITES = c["SEGMENTS"], c["SITES"]
        self.members, self.slots, self.FEATURES = r["campaignMembers"], r["slots"], g["FEATURES"]
        self.ALL_SOURCES = [*src["PUBLIC_SOURCES"], *src["SYNTHETIC_SOURCES"], *src["ENGINES"]]
        self.datasets = s["datasets"]


def _talk(d: _Data, m: dict) -> list:
    video = m["mode"] == "Telehealth"
    net = d.ORG["networkShort"]
    rows = [{"es": f"Hola, soy Teresa de {net}. Llamo por su presión arterial.",
             "en": f"Hi, this is Teresa from {net}. I am calling about your blood pressure."},
            {"es": "Podemos hacer una cita por video, sin manejar a la clínica.",
             "en": "We can do a video visit, with no drive to the clinic."} if video else
            {"es": f"Podemos darle una cita en {m['site']}.", "en": f"We can book you a visit at {m['site']}."}]
    if video and m["cuff"] == "Ship first":
        rows.append({"es": "Le enviamos un monitor de presión a su casa antes de la cita.",
                     "en": "We will mail you a blood pressure monitor before the visit."})
    if video and m["cuff"] == "On file":
        rows.append({"es": "Tenga a mano su monitor de presión para la cita.",
                     "en": "Have your blood pressure monitor ready for the visit."})
    rows.append({"es": "Le mandamos un texto para confirmar. Responda C o R.",
                 "en": "We will text you to confirm. Reply C or R."})
    return rows


def _mode_reason(d: _Data, m: dict) -> str:
    if m["mode"] != "Telehealth":
        return f"In person recommended: {js(m['driveMin'])}-minute drive to {m['site']}."
    if m["id"] == d.LINDA["memberId"]:
        return f"Telehealth recommended: {js(m['driveMin'])}-minute drive, broadband available, visit type eligible."
    return (f"Telehealth recommended: {js(m['driveMin'])}-minute drive and visit type eligible; "
            "a phone visit if video is not possible.")


def _reminder_plan(d: _Data, m: dict) -> dict:
    article = "an" if re.match(r"^(8|11|18)", js(m["driveMin"])) else "a"
    why = [x for x in (
        f"{js(d.LINDA['missedVisits'])} missed visits" if m["id"] == d.LINDA["memberId"] else "",
        f"{article} {js(m['driveMin'])}-minute drive" if m["driveMin"] > 60 else "",
        f"no visit in {js(m['monthsSinceVisit'])} months" if m["monthsSinceVisit"] >= 6 else "") if x]
    because = f"{', '.join(why[:-1])} and {why[-1]}" if len(why) > 1 else (why[0] if why else "")
    return {"early": bool(why), "why": why, "because": because}


def _context_specs(d: _Data, kind: str, selected_id, county) -> list:
    if kind in ("rank", "talk", "mode", "slots", "plan"):
        m = next((x for x in d.members if x["id"] == selected_id), d.members[0])
        if kind == "rank":
            return [
                spec("callout", {"title": f"{m['name']}: rank {js(m['rank'])} of {js(d.BP['nearControl'])}",
                                 "body": f"{', '.join(m['reasons'])}. Ranked by the impactability score: near control, "
                                         "still changeable, and held back mostly by access.", "status": "info"}),
                grid(2, [stat("Likely to reach control", f"{js(m['likelihood'])}%", "With one recheck"),
                         stat("Visit mode", m["mode"], f"{js(m['driveMin'])}-minute drive"),
                         stat("Cuff", "Not needed" if m["cuff"] == "Not needed" else m["cuff"],
                              "Home reading counts for CMS165" if m["mode"] == "Telehealth" else "In-person reading")]),
            ]
        if kind == "talk":
            pref = "prefers Spanish" if m["language"] == "Spanish" else "Spanish version"
            return [
                spec("data_table", {"caption": f"Talking points for {m['name']} ({pref})",
                                    "columns": [{"key": "es", "label": "Español"}, {"key": "en", "label": "English"}],
                                    "rows": _talk(d, m)}),
                spec("callout", {"title": "No clinical advice by phone script",
                                 "body": "Clinical questions go to the care team.", "status": "neutral"}),
            ]
        if kind == "mode":
            tele = m["mode"] == "Telehealth"
            return [spec("callout", {"title": "Telehealth recommended" if tele else "In person recommended",
                                     "body": f"{_mode_reason(d, m)} Home cuff readings count for CMS165." if tele
                                     else _mode_reason(d, m), "status": "info"})]
        if kind == "slots":
            slots = []
            for s in d.slots:
                if s["mode"] == "In person":
                    s = {**s, "driveMin": m["driveMin"]}
                elif s["mode"] == "Mobile clinic" and m["id"] != d.LINDA["memberId"]:
                    s = {**s, "where": f"Mobile clinic, {m['site']}"}
                slots.append(s)
            slots.sort(key=lambda s: s["driveMin"])
            return [spec("data_table", {
                "caption": f"Other slots for {m['name']}, sorted by drive time",
                "columns": [{"key": "mode", "label": "Mode"}, {"key": "when", "label": "When"},
                            {"key": "drive", "label": "Drive", "align": "right"}],
                "rows": [{"mode": s["mode"], "when": f"{s['day']}, {s['time']}",
                          "drive": f"{js(s['driveMin'])} min" if s["driveMin"] else "None"} for s in slots]})]
        plan = _reminder_plan(d, m)
        video = m["mode"] == "Telehealth"
        rows = ([{"when": "72 hours before", "what": "Date, time and clinic only; reply C or R"}] if plan["early"] else []) + [
            {"when": "24 hours before", "what": "Confirmation and the video link" if video else "Confirmation, date, time and clinic"},
            {"when": "3 hours before", "what": "Link resent" if video else "Short reminder"},
            {"when": "Quiet hours", "what": "No texts 8 PM to 8 AM"}]
        return [
            spec("data_table", {"caption": f"Reminder plan for {m['name']}: {m['language']} "
                                           f"{'voice' if m['channel'] == 'Voice' else 'SMS'}",
                                "columns": [{"key": "when", "label": "When"}, {"key": "what", "label": "What"}],
                                "rows": rows}),
            spec("callout", {"title": "Why three reminders" if plan["early"] else "Two reminders",
                             "body": f"{'Because of ' + plan['because'] + '. ' if plan['early'] else ''}No reply by 24 "
                                     "hours before the visit creates a call task on Teresa’s worklist.",
                             "status": "info"}),
        ]
    if kind == "site":
        s = next((x for x in d.SITES if x["id"] == (selected_id or "")), d.SITES[2])
        net = d.CONTRACT["actualPmpm"]
        return [grid(2, [stat(f"{s['name']} PMPM", f"${js(s['pmpm'])}", f"Network ${js(net)}",
                              "warning" if s["pmpm"] > net else "good"),
                         stat("Members", num(s["members"])), stat("Low-value care", usd_k(s["lowValue"]), "A year"),
                         stat("LBP imaging", f"{js(s['imagingPct'])}%", "Network 9%",
                              "critical" if s["imagingPct"] > 9 else "good")]),
                spec("text", {"text": "Covered by rotating locum clinicians." if s["locum"] else "Stable clinician staffing."})]
    if kind == "gap":
        g = next((x for x in d.GAP if x["id"] == selected_id), d.GAP[0])
        value = f"{g['value']:.2f}" if g["value"] % 1 else js(g["value"])
        return [spec("callout", {"title": f"{g['label']}: ${value} of the $26 PMPM gap", "body": f"{g['note']}.",
                                 "status": "info" if g["id"] == "coding" else "warning"})]
    if kind == "segment":
        s = next((x for x in d.SEGMENTS if x["id"] == selected_id), d.SEGMENTS[1])
        return [grid(2, [stat(s["label"], num(s["members"]), f"{js(s['sharePct'])}% of members"),
                         stat("Share of spend", f"{js(s['spendPct'])}%"), stat("Plan", s["action"])])]
    if kind == "measure":
        m = next((x for x in d.MEASURES if x["id"] == selected_id), d.MEASURES[2])
        met = m["current"] >= m["target"] if m["higherIsBetter"] else m["current"] <= m["target"]
        return [grid(2, [stat(f"{m['id']} now", f"{js(m['current'])}%", m["name"], "good" if met else "critical"),
                         stat("Target", f"{js(m['target'])}% or higher" if m["higherIsBetter"] else f"{js(m['target'])}% or lower"),
                         stat("Projected Dec 31", f"{js(m['projected'])}%")])]
    if kind == "lvMeasure":
        m = next((x for x in d.LV_MEASURES if x["id"] == selected_id), d.LV_MEASURES[0])
        return [grid(2, [stat("Services", num(m["services"]), m["name"]), stat("Annual spend", usd_k(m["dollars"])),
                         stat("Basis", m["basis"])]),
                spec("text", {"text": "Counted when a service is likely wasteful or wasteful; necessary services are excluded."})]
    if kind == "feature":
        f = next((x for x in d.FEATURES if x["id"] == selected_id), d.FEATURES[0])
        warn = f["kind"] == "Current" and f["id"] in ("cost", "pcVisits")
        return [spec("callout", {"title": f"{f['name']} · weight {js_round(f['weight'] * 100)}% · {f['kind']}",
                                 "body": f["note"], "status": "warning" if warn else "info"})]
    if kind == "source":
        s = next((x for x in d.ALL_SOURCES if x["id"] == selected_id), d.ALL_SOURCES[19])
        return [grid(2, [stat("Label", s["kind"], s["name"]), stat("Records", num(s["recordCount"])),
                         stat("Freshness", s["freshness"])]),
                spec("text", {"text": f"{s['provides']}. Used for: {s['usedFor']}."})]
    c = (next((x for x in d.COUNTIES if x["id"] == county), None)
         or next((x for x in d.COUNTIES if x["id"] == selected_id), None) or d.COUNTIES[2])
    return [grid(2, [
        stat("Primary care visits", f"{js(c['pcVisitChangePct'])}%", "Since January",
             "critical" if c["pcVisitChangePct"] <= -10 else "warning"),
        stat("Avoidable ED", js(c["edPer1000"]), "Per 1,000", "critical" if c["edPer1000"] >= 330 else "neutral"),
        stat("Broadband for video", f"{js(c['broadbandPct'])}%", "Of locations"),
        stat("Shortage area", c["hpsa"], "HRSA HPSA"),
    ])]


# ─── Answers (answers.ts) ─────────────────────────────────────────────────────────────────────────────────

def _to_spec(d: _Data, v: dict) -> dict:
    props_in = dict(v.get("props") or {})
    dataset = props_in.pop("dataset", None)
    props = {**(d.datasets[dataset] if dataset else {}), **props_in}
    if isinstance(props.get("children"), list):
        props["children"] = [c if "version" in c else _to_spec(d, c) for c in props["children"]]
    return spec(v["type"], props)


def _titled(sp: dict) -> dict:
    props = sp["props"]
    if sp["type"] == "data_table" and isinstance(props.get("caption"), str):
        rest = {k: v for k, v in props.items() if k != "caption"}
        return spec("stack", {"children": [spec("text", {"text": props["caption"], "size": "sm", "tone": "muted"}),
                                           spec("data_table", {**rest, "stack": True})]})
    if isinstance(props.get("children"), list):
        return {**sp, "props": {**props, "children": [_titled(c) for c in props["children"]]}}
    return sp


def _answers(d: _Data, contract: dict, flow_key: str) -> list | None:
    step = contract["steps"].get(flow_key)
    if not step or not step.get("viz"):
        return None
    county = flow_key[len("st_ctx_"):] if flow_key.startswith("st_ctx_") else None
    specs = []
    for vid in step["viz"]:
        v = contract["viz"].get(vid)
        if not v:
            continue
        specs.extend(_context_specs(d, v["props"]["kind"], None, county) if v["type"] == "context" else [_to_spec(d, v)])
    specs = [_titled(s) for s in specs]
    if any(not s["type"].startswith("rain.") for s in specs):
        specs.append(spec("illustrative_note", {"note": NOTE}))
    if step.get("points"):
        first = specs[0] if specs else None
        if first and first["type"].startswith("rain.") and first["type"] != "rain.launch_card":
            first["props"] = {**first["props"], "points": step["points"]}
        else:
            specs.insert(0, spec("rain.key_points", {"points": step["points"]}))
    return specs


# ─── Flows, turns, briefing, context (flowKit.ts, aiTurn.ts, buildPersona.ts, recorded.ts) ─────────────

def _flow(contract: dict, key: str, step: dict, use_case: str) -> dict:
    return {"user_query": (step.get("asks") or [None])[0], "ai_message": step.get("ai"),
            "data_sources_used": step.get("sources"), "suggested_chips": step.get("chips"),
            "confidence": 60 if key == DEFAULT_FLOW_KEY else 92,
            **({"capability": step["capability"]} if use_case == "A" and step.get("capability") else {})}


def _turn(d: _Data, contract: dict, key: str, flow: dict) -> dict:
    turn = {"id": key, "text": str(flow.get("ai_message") or ""),
            "citations": [str(x) for x in flow["data_sources_used"]] if isinstance(flow.get("data_sources_used"), list) else [],
            "components": [],
            "chips": [str(x) for x in flow["suggested_chips"]] if isinstance(flow.get("suggested_chips"), list) else []}
    if flow.get("capability"):
        turn["capability"] = str(flow["capability"])
    turn["confidence"] = flow["confidence"]
    answer = _answers(d, contract, key)
    if answer:
        turn["components"] = [*turn["components"], *answer]
    return turn


def _signal(s: dict) -> dict:
    out = {"id": str(s.get("id", "")), "title": str(s.get("title", "")), "description": s.get("description") or None,
           "status": s.get("severity") if s.get("severity") in ("good", "warning", "critical", "info", "neutral") else "info",
           "metricText": s.get("metric") or None, "sources": list(s.get("sources") or []),
           "primary": s["primary"] if isinstance(s.get("primary"), bool) else None}
    return {k: v for k, v in out.items() if v is not None}


def build_persona(sections: dict, persona_id: str) -> dict:
    """The Ultra API payloads for one persona, built from the backend's data sections."""
    personas = sections["constants"]["PERSONAS"]
    key = next((k for k, v in personas.items() if v == persona_id), None)
    if key is None:
        raise KeyError(persona_id)
    d = _Data(sections)
    contract = sections["contracts"][key]
    ui = sections["personas"][key]
    use_case = "A" if contract["signals"] else "B"
    steps = contract["steps"]

    flows = {k: _flow(contract, k, s, use_case) for k, s in steps.items()}
    routes: dict = {}
    for k, s in steps.items():
        for label in s.get("asks") or []:
            routes[label] = k
    chip_to_flow: dict = {}
    for label, k in routes.items():
        chip_to_flow[label] = k
        chip_to_flow[label.lower()] = k
        chip_to_flow[loose(label)] = k
    greeting = next(k for k in steps if k.endswith("_brief"))
    turns = {k: _turn(d, contract, k, f) for k, f in flows.items()}

    initial_chips = list(dict.fromkeys([*steps[greeting].get("chips", []), *contract.get("queries", [])]))
    kpis = []
    for k in contract["kpis"]:
        trend = " · ".join(x for x in (k.get("detail"), k.get("source")) if x)
        kpis.append({"id": k["id"], "label": k["label"], "value": k["value"],
                     **({"trendText": trend} if trend else {}), **({"icon": k["icon"]} if k.get("icon") else {}),
                     **({"chip": k["chip"]} if k.get("chip") else {})})
    nav_slots = ["ask", *[w["id"] for w in contract["workbenches"]]]
    identity = ui["identity"]
    context = {
        "client": sections["client"]["branding"],
        "persona": {"id": persona_id, "name": identity["name"], "initials": identity["initials"],
                    "role": identity["role"], "layout": "inline",
                    "capabilities": A_CAPABILITIES if use_case == "A" else B_CAPABILITIES, "navSlots": nav_slots},
        "personas": [{"id": personas[k], "name": sections["personas"][k]["identity"]["name"],
                      "role": sections["personas"][k]["identity"]["role"]} for k in PERSONA_KEYS],
        "dataSources": d.ALL_SOURCES,
    }
    briefing = {"greeting": turns[greeting], "signals": [_signal(s) for s in contract["signals"]],
                "kpis": kpis, "chips": initial_chips}
    match = {"chipToFlowKey": chip_to_flow, "strictMatch": True, "signalSequence": [],
             "flows": {k: {"user_query": str(f.get("user_query") or ""),
                           "corpus": f"{f.get('user_query') or ''} {f.get('ai_message') or ''} ".lower()}
                       for k, f in flows.items()}}
    return {"context": context, "briefing": briefing, "turns": turns, "match": match}
