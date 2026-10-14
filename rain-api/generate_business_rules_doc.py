"""
Generates BUSINESS_RULES.md -- an open, human-readable data dictionary,
straight from business_rules.py (the same source the SQL-generation
prompt actually reads). One source of truth, two outputs: this doc for
people, the raw dict for the LLM prompt. They can't drift apart because
they're the same data.
"""

from business_rules import BUSINESS_RULES, BREAKDOWN_RULES


def _cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def generate():
    lines = [
        "# RAIN Business Rules — Verified Term Definitions",
        "",
        "Every entry here was individually tested against `rain.db` and confirmed",
        "to produce the exact known-correct number before being recorded here.",
        "This is the real, open source of truth for what each business term means",
        "in RAIN's actual schema — not something living only in a conversation.",
        "",
        "This same data feeds the live SQL-generation pipeline directly",
        "(`business_rules.py` → `sql_generator.py`), so this document can never",
        "drift out of sync with what the system actually does.",
        "",
        "| Term | Table | Rule | Verified Result |",
        "|---|---|---|---|",
    ]
    for r in BUSINESS_RULES:
        lines.append(f"| {_cell(r['term'])} | `{r['table']}` | `{_cell(r['rule'])}` | {_cell(r['verified_result'])} |")

    lines += [
        "",
        "## List and breakdown rules",
        "",
        "Answers that are lists or breakdowns rather than one number. Each is a verified query;",
        "where several rows tie for a place, the answer states the tie instead of naming one.",
        "",
        "| Term | Table | Applies when | Limited to | Verified Result |",
        "|---|---|---|---|---|",
    ]
    for r in BREAKDOWN_RULES:
        applies = f"`{_cell(r['gate'])}`, or any \"by X\" question" if r.get("gate") else "any \"by X\" question"
        who = ", ".join(r["personas"]) if r.get("personas") else "all personas"
        lines.append(f"| {_cell(r['term'])} | `{r['table']}` | {applies} | {who} | {_cell(r['verified_result'])} |")

    lines += [
        "",
        "## Where the data differs from the original spec narrative",
        "",
        "Figures and claims in the original RAIN spec text that do not reproduce from the real dataset.",
        "The right-hand column is what the data supports -- treat it as the corrected, verified version.",
        "",
        "| Question | Spec said | Real data shows |",
        "|---|---|---|",
        "| Prenatal completion rate | 61% | **84%** |",
        "| Hypertension RPM compliance | 58% | **61%** |",
        "| Priya Q2: avoidable ED by ZIP, \"after the closure\" | 89828: 37, 89823: 25, 89821: 19 | Those are all-time counts. Since 2026-03-01: 89828 (26), 89823 (16), 89821 (15) -- same ZIPs, same order |",
        "| Priya Q4/Q5: \"574 elevated-risk patients\" | 574 elevated-risk | 574 is every patient in a no-broadband ZIP; no risk filter reproduces it |",
        "| Priya Q6: obstetric outreach population | 574 | 48 active pregnancies (15 elevated-risk) live in a no-broadband ZIP; 574 is all patients in those ZIPs |",
        "| Maria Q5: telehealth eligibility | 9 eligible / 3 hybrid / 3 dead-zone patients | Session counts across 14 patients (one has two sessions). By ZIP broadband, 9 of the 14 live in a no-broadband ZIP |",
        "| Maria Q7: ZIPs by elevated-risk pregnancies | 89828: 7, 89810: 6, 89825: 4 | Third place is a three-way tie at 4 (89816, 89818, 89825) |",
        "| David Q3: RPM completeness by ZIP | 89825 42%, 89823 45%, 89820 49% | 89820 and 89821 tie at 49% |",
        "| Sarah Q7: risk-ranked outreach list | PT-00131 hits two of three factors (RPM, medication gap, lost provider) | All five patients hit those three; PT-00131 lacks the transportation barrier that PT-00127 to 130 have |",
        "| Sarah Q4: lost provider | 5 + 41 + 3 = 49 | The same 49 by condition: 5 CHF, 42 diabetes, 2 hypertension (the 3 pregnant patients are 1 diabetes + 2 hypertension) |",
        "| Sarah Q2: medication gap over 30 days | 10 | 94 patients overall; 10 is the subset among the 17 worsening patients that have a fill record |",
        "| James Q3: transports convertible to telehealth | 13 | No such flag exists and no definition yields 13; the answer gives a labelled proxy |",
        "| James Q4: telehealth demand | 65 virtual visits today (13 + 52) | 17 sessions today; the 52 prenatal sessions are across all dates; no capacity data exists |",
        "| James Q6: transport demand since the closure | 5 to 18 trips a day, +210% | Transport records begin 2026-05-15; there is no pre-closure baseline |",
        "| David Q5: pregnancies on deactivated providers | every pregnancy episode still assigned | None -- all pregnancy episodes are assigned to PRV-010 to 019 |",
        "| David Q7: what degraded after the closure | 1,240 references and 180 mismatches both appeared after March 1 | Only the 1,240 can be dated (2026-03-06); mismatches carry no date |",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    doc = generate()
    with open("BUSINESS_RULES.md", "w") as f:
        f.write(doc)
    print(f"Wrote BUSINESS_RULES.md ({len(BUSINESS_RULES)} rules)")
