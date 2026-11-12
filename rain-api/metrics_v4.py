"""Compute the RAIN v0.4 UI context from rows: constants, records, governance and datasets.

Every number the UI shows is computed here, at request time, by SQL over rain_v4.synthetic (row-level
synthetic operational data: patients, encounters, claims, quality results, readings, appointments...) and
rain_v4.public_data (CDC PLACES, SVI, HRSA HPSA, ACS, CMS...). Nothing in this module is a stored result:
change a row (book a visit, record a reading, edit a claim) and the next request shows the change.

What is configuration rather than data lives in CONFIG below (the persona map, a few display labels, which
member is the patient persona). Planning assumptions (reach rates, option costs, thresholds) are rows in
synthetic.assumption, so they are data too and can be edited.

The output has the same shape and keys as the seed's sections (constants / records / governance / datasets),
so the persona contract templates (templating_v4) render against it unchanged.
"""
from __future__ import annotations

import math
import re
import statistics
import threading
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

# ─── configuration (not data) ────────────────────────────────────────────────────────────────────────────
CONFIG = {
    "network": "sbch",                       # the network the operator personas work in
    "top_n": 300,                            # size of the ranked outreach list
    "bp_campaign": "BP2026", "fit_campaign": "FIT2026",
    "linda": "M-40107",                      # the patient persona (Use Case C)
    "chw": "Teresa Lopez", "access": "Brandon Kee",
    "imaging_site": "winnemucca",            # the low back pain imaging outlier site
    # the seven personas, in switcher order
    "personas": {"ceo": "rain_ceo", "cmo": "rain_cmo", "cio": "rain_cio", "state": "rain_state",
                 "chw": "rain_chw", "access": "rain_access", "linda": "rain_linda"},
    "illustrative": "Synthetic data for a demo. Sierra Basin Community Health, High Desert Health Plan and every person shown are fictional.",
    "product": "Ask AI",
    "segments": {"highNeed": ("High-need, high-cost", "Care plan intensity, risk-coding recapture"),
                 "impactable": ("Impactable, rising risk", "Ranked outreach, top 300 first"),
                 "stable": ("Low risk, stable", "Light-touch reminders")},
    "options": {"A": ("Care coordinators and telehealth rechecks in Lander and Pershing", "Within a year", "Largest health impact"),
                "B": ("Shared low-value care feedback, all four networks", "3 to 6 months", "Fastest cost return"),
                "C": ("Mobile clinic days in the six low-broadband ZIP areas", "6 months", "Access floor")},
    "focus_counties": ["lander", "pershing"],
}
GROUPS = {"I10": "Hypertension", "E11.9": "Diabetes", "J44.9": "COPD or asthma", "I50.9": "Heart failure", "F32.9": "Depression"}
COND_NAME = {"I10": "Hypertension", "E11.9": "Type 2 diabetes", "J44.9": "COPD or asthma", "I50.9": "Heart failure",
             "F32.9": "Depression", "N18.4": "Chronic kidney disease"}
GAP_LABEL = {"CMS165": "BP control (CMS165)", "CMS122": "HbA1c >9% (CMS122)", "CMS130": "Colorectal screening (CMS130)",
             "CMS125": "Breast cancer screening (CMS125)", "CMS2": "Depression screening (CMS2)"}
MONTH = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
MON = [m[:3] for m in MONTH]
DAY = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
ES_DAY = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
ES_MON = ["", "ene.", "feb.", "mar.", "abr.", "may.", "jun.", "jul.", "ago.", "sep.", "oct.", "nov.", "dic."]
ROUTE = {"Clinical question": "Nurse line (no automated clinical advice)", "Coverage flag": "Enrollment assister",
         "Undeliverable number": "Front desk: update the number", "Free-text reply": "Front desk"}
TEMPLATE_TEXT = {"reminder": "Reminder sent: reply C to confirm or R to change.",
                 "reminder_offer_telehealth": "Reminder sent: reply C to keep it, T for video or R to change it.",
                 "booking_confirmation": "Visit booked: reply C to confirm or R to change."}


# ─── small helpers ───────────────────────────────────────────────────────────────────────────────────────
def rows(cur, sql, args=None) -> list[dict]:
    cur.execute(sql, args or {})
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def one(cur, sql, args=None):
    cur.execute(sql, args or {})
    r = cur.fetchone()
    return r[0] if r else None


def rnd(x, n=0):
    if x is None:
        return None
    v = float(x)
    q = math.floor(abs(v) * 10 ** n + 0.5) / 10 ** n
    q = math.copysign(q, v)
    return int(q) if n == 0 else q


def pct(a, b, n=0):
    return rnd(100 * a / b, n) if b else 0


def camel(name: str) -> str:
    w = name.replace(" County", "").split()
    return w[0].lower() + "".join(x.capitalize() for x in w[1:])


def hm(t: datetime) -> str:
    return f"{t.hour % 12 or 12}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"


def short_day(d) -> str:
    return f"{DAY[d.weekday()][:3]}, {MON[d.month]} {d.day}"


def rel_day(d: date, as_of: date, full=False) -> str:
    if d == as_of:
        return "Today"
    if d == as_of + timedelta(days=1):
        return "Tomorrow"
    if d == as_of - timedelta(days=1):
        return "Yesterday"
    return f"{DAY[d.weekday()]}, {MON[d.month]} {d.day}" if full else short_day(d)


def months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + b.month - a.month


def age_on(birth: date, d: date) -> int:
    return d.year - birth.year - ((d.month, d.day) < (birth.month, birth.day))


def bp_text(s, d):
    return f"{int(s)}/{int(d)}"


def table(caption, columns, rows_):
    return {"caption": caption, "columns": columns, "rows": rows_}


def col(key, label, **kw):
    return {"key": key, "label": label, **kw}


def bar(title, series, unit=None, kind="bar"):
    out = {"kind": kind, "title": title, "series": series}
    if unit:
        out = {"kind": kind, "unit": unit, "title": title, "series": series}
    return out


def usd_k(n):
    return f"${rnd(n / 1000):,}K"


def usd_m(n, d=1):
    v = rnd(n / 1e6, d)
    return f"${v:g}M"


# ─── the computation ─────────────────────────────────────────────────────────────────────────────────────
class _Calc:
    def __init__(self, cur):
        self.cur = cur
        self.C, self.REC, self.GOV, self.DS = {}, {}, {}, {}

    # time frame -------------------------------------------------------------------------------------------
    def frame(self):
        cur = self.cur
        self.as_of = one(cur, "SELECT max(last_refreshed)::date FROM synthetic.data_source")
        self.lag = one(cur, "SELECT lag_days FROM synthetic.data_source WHERE data_source_id = 'SYN-claim'") or 45
        cb = rows(cur, "SELECT * FROM synthetic.contract_benchmark WHERE network_id = %(n)s AND contract_year = %(y)s",
                  {"n": CONFIG["network"], "y": self.as_of.year})[0]
        self.cb = cb
        self.start, self.end = cb["contract_start"], cb["contract_end"]
        through = self.as_of - timedelta(days=self.lag)
        q = (through.month - 1) // 3 + 1
        qe_month = q * 3
        self.period_end = date(through.year, qe_month, 1) + timedelta(days=31)
        self.period_end = date(self.period_end.year, self.period_end.month, 1) - timedelta(days=1)
        self.quarter = q
        self.months = months_between(self.start, self.period_end) + 1
        self.lv_start = date(self.period_end.year - 1, self.period_end.month, 1) + timedelta(days=31)
        self.lv_start = date(self.lv_start.year, self.lv_start.month, 1)
        self.annualize = 12 / self.months
        self.A = {r["assumption_code"]: float(r["value"]) for r in rows(cur, "SELECT assumption_code, value FROM synthetic.assumption")}
        self.campaign_start = one(cur, "SELECT created_at::date FROM synthetic.campaign WHERE campaign_id = %(c)s",
                                  {"c": CONFIG["bp_campaign"]})
        self.P = dict(start=self.start, end=self.period_end, lv_start=self.lv_start, net=CONFIG["network"], as_of=self.as_of,
                      cs=self.campaign_start, bp=CONFIG["bp_campaign"], fit=CONFIG["fit_campaign"])

    # reference rows ---------------------------------------------------------------------------------------
    def reference(self):
        cur, P = self.cur, self.P
        self.sites = rows(cur, """SELECT s.*, (SELECT count(*) FROM synthetic.provider p WHERE p.clinic_site_id = s.clinic_site_id AND p.locum_flag) AS locums
                                  FROM synthetic.clinic_site s ORDER BY s.clinic_site_id""")
        self.site = {s["clinic_site_id"]: s for s in self.sites}
        self.sb_sites = [s for s in self.sites if s["grantee_id"] == P["net"] and s["site_type"] != "Mobile clinic"]
        order = ["elko", "wells", "winnemucca", "battleMountain", "lovelock", "ely", "fallon"]
        self.sb_sites.sort(key=lambda s: order.index(s["clinic_site_id"]) if s["clinic_site_id"] in order else 99)
        self.grantees = rows(cur, "SELECT * FROM synthetic.grantee ORDER BY start_date, grantee_id")
        self.counties = rows(cur, """SELECT b.geoid::text AS fips, b.name FROM public_data.county_boundaries b
                                     WHERE b.geoid::text IN (SELECT DISTINCT county_fips FROM synthetic.patient) ORDER BY b.name""")
        corder = ["elko", "humboldt", "lander", "pershing", "whitePine", "churchill"]
        for c in self.counties:
            c["id"] = camel(c["name"])
        self.counties.sort(key=lambda c: corder.index(c["id"]) if c["id"] in corder else 99)
        self.cid = {c["fips"]: c["id"] for c in self.counties}
        self.zip = {z["zcta"]: z for z in rows(cur, "SELECT * FROM synthetic.zip_place")}
        self.pat = {p["patient_id"]: p for p in rows(cur, """
            SELECT p.patient_id, p.first_name, p.last_name, p.birth_date, p.language, p.zip_code, p.county_fips, p.phone,
                   p.home_site_id, p.network_id, i.segment, i.score AS score13, i.outreach_rank AS rank13,
                   (SELECT t.drive_minutes FROM synthetic.travel_time t WHERE t.patient_id = p.patient_id
                      AND t.clinic_site_id = p.home_site_id ORDER BY t.travel_time_id LIMIT 1) AS drive
            FROM synthetic.patient p
            LEFT JOIN synthetic.impactability_score i ON i.patient_id = p.patient_id AND i.model_version = 'v1.3'
            WHERE p.network_id = %(net)s""", P)}
        for p in self.pat.values():
            p["name"] = f"{p['first_name']} {p['last_name']}"
            p["frontier"] = bool(self.zip.get(p["zip_code"], {}).get("frontier_flag"))
            p["drive"] = int(p["drive"]) if p["drive"] is not None else None
        self.members = len(self.pat)
        self.all_members = one(cur, "SELECT count(*) FROM synthetic.attributed_member WHERE contract_year = %(y)s", {"y": self.as_of.year})
        self.mem_by_net = dict(rows_to_pairs(rows(cur, "SELECT network_id, count(*) n FROM synthetic.patient GROUP BY 1")))
        self.mem_by_county = dict(rows_to_pairs(rows(cur, "SELECT county_fips, count(*) n FROM synthetic.patient GROUP BY 1")))
        self.mem_by_site = Counter(p["home_site_id"] for p in self.pat.values())

    # cost ---------------------------------------------------------------------------------------------------
    def cost(self):
        cur, P = self.cur, self.P
        spend = rows(cur, """SELECT p.home_site_id site, coalesce(i.segment, 'stable') seg, extract(month FROM c.service_date)::int m,
                                    sum(c.allowed_amount) usd
                             FROM synthetic.claim c JOIN synthetic.patient p ON p.patient_id = c.patient_id
                             LEFT JOIN synthetic.impactability_score i ON i.patient_id = p.patient_id AND i.model_version = 'v1.3'
                             WHERE p.network_id = %(net)s AND c.service_date BETWEEN %(start)s AND %(end)s GROUP BY 1, 2, 3""", P)
        total = sum(float(r["usd"]) for r in spend)
        self.actual = total / (self.members * self.months)
        self.expected = float(self.cb["expected_pmpm"])
        by_site, by_seg, by_month = defaultdict(float), defaultdict(float), defaultdict(float)
        for r in spend:
            by_site[r["site"]] += float(r["usd"])
            by_seg[r["seg"]] += float(r["usd"])
            by_month[r["m"]] += float(r["usd"])
        self.site_pmpm = {s: v / (self.mem_by_site[s] * self.months) for s, v in by_site.items()}
        self.seg_spend = {k: v / total for k, v in by_seg.items()}
        self.pmpm_trend = [{"month": MON[m], "actual": rnd(by_month[m] / self.members)} for m in sorted(by_month)]
        # avoidable ED (annualized per 1,000) by network and county, the benchmark, the average cost
        ed = rows(cur, """SELECT p.network_id net, p.county_fips cf, count(*) n, sum(c.allowed_amount) usd
                          FROM synthetic.claim c JOIN synthetic.patient p ON p.patient_id = c.patient_id
                          WHERE c.avoidable_ed_flag AND c.service_date BETWEEN %(start)s AND %(end)s GROUP BY 1, 2""", P)
        self.ed_rows = ed
        sb_ed = [r for r in ed if r["net"] == P["net"]]
        n_sb = sum(r["n"] for r in sb_ed)
        self.ed_rate = n_sb / self.members * 1000 * self.annualize
        self.ed_avg = sum(float(r["usd"]) for r in sb_ed) / n_sb if n_sb else 0
        self.ed_bench = float(one(cur, "SELECT benchmark_value FROM synthetic.utilization_benchmark WHERE metric_code = 'avoidable_ed_per_1000'"))
        self.ed_gap_pmpm = max(0.0, (self.ed_rate - self.ed_bench) / 1000 * self.ed_avg / 12)
        # coding recapture: high-need members with a chronic condition documented last year, not yet this year
        cod = rows(cur, """SELECT c.patient_id, c.icd10_code, h.annual_expected_cost cost FROM synthetic.condition c
                           JOIN synthetic.patient p ON p.patient_id = c.patient_id
                           JOIN synthetic.impactability_score i ON i.patient_id = c.patient_id AND i.model_version = 'v1.3'
                           JOIN synthetic.hcc_reference h ON h.icd10_code = c.icd10_code
                           WHERE p.network_id = %(net)s AND i.segment = 'highNeed' AND c.documented_year = extract(year FROM %(as_of)s::date) - 1
                             AND c.recaptured_year IS NULL""", P)
        self.coding_members = len({r["patient_id"] for r in cod})
        self.coding_pmpm = sum(float(r["cost"]) for r in cod) / (self.members * 12)
        self.high_need = sum(1 for p in self.pat.values() if p["segment"] == "highNeed")
        # low-value care, trailing 12 months
        lv = rows(cur, """SELECT f.measure_id, m.measure_name, m.basis, f.clinic_site_id site, p.network_id net, p.county_fips cf,
                                 f.ordering_provider_id prov, f.service_date d, f.allowed_amount usd
                          FROM synthetic.low_value_finding f JOIN synthetic.low_value_measure m ON m.measure_id = f.measure_id
                          JOIN synthetic.claim_line cl ON cl.claim_line_id = f.claim_line_id
                          JOIN synthetic.claim c ON c.claim_id = cl.claim_id JOIN synthetic.patient p ON p.patient_id = c.patient_id
                          WHERE f.classification <> 'necessary' AND f.service_date BETWEEN %(lv_start)s AND %(end)s""", P)
        self.lv = lv
        sb_lv = [r for r in lv if r["net"] == P["net"]]
        self.lv_sb = sb_lv
        self.lv_annual = sum(float(r["usd"]) for r in sb_lv)
        self.lv_pmpm = self.lv_annual / (self.members * 12)
        meas = defaultdict(lambda: [0, 0.0, "", ""])
        for r in sb_lv:
            x = meas[r["measure_id"]]
            x[0] += 1
            x[1] += float(r["usd"])
            x[2], x[3] = r["measure_name"], r["basis"]
        self.lv_measures = [{"id": k, "name": v[2], "basis": v[3], "services": v[0], "dollars": rnd(v[1], -3) if False else rnd(v[1] / 1000) * 1000}
                            for k, v in sorted(meas.items())]
        self.lv_site = defaultdict(float)
        for r in sb_lv:
            self.lv_site[r["site"]] += float(r["usd"])
        self.lv_county = defaultdict(float)
        for r in lv:
            self.lv_county[r["cf"]] += float(r["usd"])

    # low back pain imaging (Choosing Wisely LV01) ------------------------------------------------------------
    def imaging(self):
        cur, P = self.cur, self.P
        rot = rows(cur, """SELECT min(e.start_time)::date d, e.clinic_site_id site, count(DISTINCT e.provider_id) n
                           FROM synthetic.encounter e JOIN synthetic.provider pr ON pr.provider_id = e.provider_id
                           WHERE pr.locum_flag AND pr.clinic_site_id = %(site)s GROUP BY 2""", {"site": CONFIG["imaging_site"]})
        self.rotation = rot[0]["d"] if rot else self.start
        self.locum_count = rot[0]["n"] if rot else 0
        win_start = date(self.rotation.year, self.rotation.month, 1)
        visits = rows(cur, """SELECT cl.clinic_site_id site, cl.ordering_provider_id prov, date_trunc('month', c.service_date)::date m, count(*) n
                              FROM synthetic.claim_line cl JOIN synthetic.claim c ON c.claim_id = cl.claim_id
                              JOIN synthetic.patient p ON p.patient_id = c.patient_id
                              WHERE cl.diagnosis_code = 'M54.50' AND cl.line_number = 1 AND cl.procedure_code = '99214'
                                AND p.network_id = %(net)s AND c.service_date BETWEEN %(lv_start)s AND %(end)s GROUP BY 1, 2, 3""", P)
        imaged = [r for r in self.lv_sb if r["measure_id"] == "LV01"]
        def in_win(d):
            return win_start <= d <= self.period_end
        v_site, i_site = Counter(), Counter()
        v_prov, i_prov = Counter(), Counter()
        v_month, i_month = Counter(), Counter()
        for r in visits:
            if in_win(r["m"]):
                v_site[r["site"]] += r["n"]
                v_prov[r["prov"]] += r["n"]
            if r["site"] == CONFIG["imaging_site"] and r["m"] >= self.start:
                v_month[r["m"].month] += r["n"]
        for r in imaged:
            if in_win(r["d"]):
                i_site[r["site"]] += 1
                i_prov[r["prov"]] += 1
            if r["site"] == CONFIG["imaging_site"] and r["d"] >= self.start:
                i_month[r["d"].month] += 1
        self.img_rate = {s: pct(i_site[s], v_site[s]) for s in v_site}
        self.img_network = pct(sum(i_site.values()), sum(v_site.values()))
        locums = rows(cur, "SELECT provider_id, last_name FROM synthetic.provider WHERE locum_flag AND clinic_site_id = %(s)s ORDER BY provider_id",
                      {"s": CONFIG["imaging_site"]})
        self.locums = [{"id": f"Locum clinician {i}", "ratePct": pct(i_prov[l["provider_id"]], v_prov[l["provider_id"]]),
                        "orders": i_prov[l["provider_id"]]} for i, l in enumerate(locums, start=1)]
        self.win_trend = [{"month": MON[m], "value": pct(i_month[m], v_month[m])} for m in sorted(v_month) if m <= self.period_end.month]
        lv01 = [r for r in self.lv_sb if r["measure_id"] == "LV01"]
        self.lbp_usd = sum(float(r["usd"]) for r in lv01)
        self.win_share = pct(sum(float(r["usd"]) for r in lv01 if r["site"] == CONFIG["imaging_site"]), self.lbp_usd)

    # quality --------------------------------------------------------------------------------------------------
    def quality(self):
        cur, P, A = self.cur, self.P, self.A
        qm = rows(cur, "SELECT * FROM synthetic.quality_measure ORDER BY gate_flag DESC, measure_code")
        order = ["CMS2", "CMS125", "CMS165", "CMS122", "CMS130"]
        qm.sort(key=lambda m: order.index(m["measure_code"]) if m["measure_code"] in order else 99)
        res = rows(cur, """SELECT r.measure_code m, p.network_id net, p.county_fips cf, count(*) FILTER (WHERE r.denominator_flag) den,
                                  count(*) FILTER (WHERE r.numerator_flag) num,
                                  count(*) FILTER (WHERE r.numerator_flag AND r.computed_at::date > %(end)s::date - interval '3 months') recent
                           FROM synthetic.quality_measure_result r JOIN synthetic.patient p ON p.patient_id = r.patient_id
                           WHERE r.period_year = extract(year FROM %(as_of)s::date) GROUP BY 1, 2, 3""", P)
        agg = defaultdict(lambda: [0, 0, 0])
        for r in res:
            for key in ((r["m"], "net", r["net"]), (r["m"], "cf", r["cf"])):
                a = agg[key]
                a[0] += r["den"]; a[1] += r["num"]; a[2] += r["recent"]
        self.q_agg = agg
        months_left = A.get("projection_months_left", 3)
        sb = lambda code: agg[(code, "net", P["net"])]
        near = one(cur, "SELECT count(*) FROM synthetic.campaign_member WHERE campaign_id = %(bp)s", P)
        fit_kits = one(cur, "SELECT count(*) FROM synthetic.campaign_member WHERE campaign_id = %(fit)s", P)
        rechecks = one(cur, """SELECT count(*) FROM synthetic.ehr_order o JOIN synthetic.patient p ON p.patient_id = o.patient_id
                               WHERE p.network_id = %(net)s AND o.procedure_code = '83036' AND o.ordered_at::date > %(end)s""", P)
        self.bp_projected_controls = rnd(near * A.get("bp_reach_rate", 0) * A.get("bp_control_if_reached", 0))
        measures = []
        for m in qm:
            code = m["measure_code"]
            den, num, recent = sb(code)
            if code == "CMS165":
                proj_num = num + self.bp_projected_controls
            elif code == "CMS122":
                proj_num = num - rechecks * A.get("hba1c_recheck_improve_rate", 0)
            elif code == "CMS130":
                proj_num = num + fit_kits * A.get("fit_return_rate", 0)
            else:
                proj_num = num + recent / 3 * months_left
            measures.append({"id": code, "name": m["measure_name"], "current": pct(num, den), "target": rnd(m["target_rate"]),
                             "higherIsBetter": not m["lower_is_better"], "projected": pct(proj_num, den),
                             "denominator": den, "numerator": num})
        self.measures = measures
        self.gate_met = sum(1 for m in measures if (m["current"] >= m["target"]) == m["higherIsBetter"] or m["current"] == m["target"])
        self.fit_kits, self.rechecks, self.near = fit_kits, rechecks, near
        bp = next(m for m in measures if m["id"] == "CMS165")
        self.bp = bp
        self.fit_gain = rnd(fit_kits * A.get("fit_return_rate", 0) / sb("CMS130")[0] * 100) if sb("CMS130")[0] else 0

    # the BP campaign: members, reasons, contact, status ------------------------------------------------------
    def campaign(self):
        cur, P, A = self.cur, self.P, self.A
        cm = rows(cur, """SELECT m.patient_id id, m.outreach_rank rank, m.recommended_visit_mode mode, m.cuff_on_file cuff, m.booked_flag,
                                 m.outcome status, r.score likelihood, so.description standing_order
                          FROM synthetic.campaign_member m
                          LEFT JOIN synthetic.risk_score r ON r.patient_id = m.patient_id AND r.model_name = 'bp_control_likelihood'
                          LEFT JOIN synthetic.standing_order so ON so.campaign_id = m.campaign_id AND so.patient_id = m.patient_id
                          WHERE m.campaign_id = %(bp)s ORDER BY m.outreach_rank""", P)
        ids = [r["id"] for r in cm]
        self.cm_ids = ids
        bp_rows = rows(cur, """SELECT patient_id, t, s, d, home FROM (
                                 SELECT patient_id, observed_at t, value_systolic s, value_diastolic d, false home FROM synthetic.observation
                                   WHERE observation_type = 'blood pressure' AND patient_id = ANY(%(ids)s)
                                 UNION ALL SELECT patient_id, reading_time, value_systolic, value_diastolic, true FROM synthetic.remote_bp_reading
                                   WHERE patient_id = ANY(%(ids)s)) x ORDER BY t""", {"ids": ids})
        self.bp_before, self.bp_after = {}, defaultdict(list)
        for r in bp_rows:
            if r["t"].date() < self.campaign_start:
                self.bp_before[r["patient_id"]] = r
            else:
                self.bp_after[r["patient_id"]].append(r)
        last_visit = dict(rows_to_pairs(rows(cur, """SELECT patient_id, max(start_time)::date FROM synthetic.encounter
                       WHERE encounter_type IN ('office', 'telehealth') AND patient_id = ANY(%(ids)s) AND start_time::date < %(cs)s GROUP BY 1""",
                                                  {"ids": ids, "cs": self.campaign_start})))
        ed_this_year = {r["patient_id"] for r in rows(cur, """SELECT DISTINCT patient_id FROM synthetic.claim WHERE avoidable_ed_flag
                        AND patient_id = ANY(%(ids)s) AND extract(year FROM service_date) = extract(year FROM %(as_of)s::date)""",
                                                       {"ids": ids, "as_of": self.as_of})}
        gaps = defaultdict(set)
        for r in rows(cur, "SELECT patient_id, measure_code FROM synthetic.care_gap WHERE status = 'open' AND patient_id = ANY(%(ids)s)", {"ids": ids}):
            gaps[r["patient_id"]].add(r["measure_code"])
        self.open_gaps = gaps
        conds = defaultdict(list)
        unrecap = defaultdict(list)
        for r in rows(cur, """SELECT patient_id, icd10_code, documented_year, recaptured_year FROM synthetic.condition
                              WHERE patient_id = ANY(%(ids)s) ORDER BY condition_id""", {"ids": ids}):
            n = COND_NAME.get(r["icd10_code"])
            if n and n not in conds[r["patient_id"]]:
                conds[r["patient_id"]].append(n)
            if r["recaptured_year"] is None and n and n not in unrecap[r["patient_id"]]:
                unrecap[r["patient_id"]].append(n)
        self.unrecap = unrecap
        needs = defaultdict(list)
        for r in rows(cur, """SELECT patient_id, domain FROM synthetic.sdoh_screening WHERE response = 'positive' AND patient_id = ANY(%(ids)s)
                              ORDER BY screening_id""", {"ids": ids}):
            if r["domain"] not in needs[r["patient_id"]]:
                needs[r["patient_id"]].append(r["domain"])
        prefs = {}
        for r in rows(cur, """SELECT DISTINCT ON (patient_id) patient_id, channel, consent_flag, best_time, phone_note, language
                              FROM synthetic.contact_preference WHERE patient_id = ANY(%(ids)s) ORDER BY patient_id, preference_id""", {"ids": ids}):
            prefs[r["patient_id"]] = r
        noshow = dict(rows_to_pairs(rows(cur, """SELECT patient_id, count(*) FROM synthetic.appointment WHERE status = 'no-show'
                     AND patient_id = ANY(%(ids)s) AND slot_id IN (SELECT slot_id FROM synthetic.slot WHERE slot_start::date > %(as_of)s::date - 365)
                     GROUP BY 1""", {"ids": ids, "as_of": self.as_of})))
        self.noshow = noshow
        tasks = {}
        for r in rows(cur, """SELECT DISTINCT ON (patient_id) patient_id, assigned_to, status, last_attempt_at FROM synthetic.outreach_task
                              WHERE campaign_id = %(bp)s AND task_type = 'bp_campaign_call' ORDER BY patient_id, created_at DESC""", P):
            tasks[r["patient_id"]] = r
        self.tasks = tasks
        teresa_sites = sorted({self.pat[i]["home_site_id"] for i, t in tasks.items() if t["assigned_to"] == CONFIG["chw"]},
                              key=lambda s: [x["clinic_site_id"] for x in self.sb_sites].index(s))
        self.teresa_sites = teresa_sites
        out = []
        for r in cm:
            p = self.pat[r["id"]]
            b = self.bp_before.get(r["id"])
            months = months_between(last_visit[r["id"]], self.as_of) if r["id"] in last_visit else 12
            mode = r["mode"].capitalize() if r["mode"] else ("Telehealth" if (p["drive"] or 0) > 60 else "In person")
            mode = "Telehealth" if mode.lower() == "telehealth" else "In person"
            site_name = self.site[p["home_site_id"]]["site_name"].replace("Sierra Basin ", "")
            reasons = []
            if b:
                reasons.append(f"BP {bp_text(b['s'], b['d'])} in {MONTH[b['t'].month]}")
            reasons.append(f"{p['drive']}-minute drive" if mode == "Telehealth" else f"{p['drive']}-minute drive to {site_name}")
            if months >= 6:
                reasons.append(f"No visit in {months} months")
            elif r["id"] in ed_this_year:
                reasons.append("Avoidable ED visit this year")
            elif "CMS122" in gaps[r["id"]]:
                reasons.append("Open diabetes gap")
            else:
                reasons.append("BP above 140/90")
            t = tasks.get(r["id"]) or {}
            pref = prefs.get(r["id"]) or {}
            if r["status"] == "Reached and booked":
                last = "Visit booked"
            elif t.get("status") == "left_message" and t.get("last_attempt_at"):
                last = f"{rel_day(t['last_attempt_at'].date(), self.as_of)}, left message"
            elif noshow.get(r["id"]):
                last = f"Missed {noshow[r['id']]} visit{'s' if noshow[r['id']] != 1 else ''}"
            else:
                last = "None this campaign"
            cuff = "Not needed" if r["cuff"] is None else ("On file" if r["cuff"] else "Ship first")
            m = {"id": r["id"], "name": p["name"], "age": age_on(p["birth_date"], self.as_of), "siteId": p["home_site_id"], "site": site_name,
                 "county": self.cid[p["county_fips"]], "driveMin": p["drive"], "lastBp": bp_text(b["s"], b["d"]) if b else None,
                 "lastBpMonth": MONTH[b["t"].month] if b else None, "reasons": reasons, "monthsSinceVisit": months,
                 "likelihood": rnd(r["likelihood"]), "language": p["language"], "channel": "SMS" if pref.get("consent_flag") else "Voice",
                 "socialNeeds": needs.get(r["id"], []), "conditions": conds.get(r["id"], []), "lastContact": last, "status": r["status"],
                 "standingOrder": r["standing_order"], "frontier": p["frontier"], "phone": p["phone"],
                 "bestTime": pref.get("best_time") or "Any time", "rank": r["rank"], "mode": mode, "cuff": cuff}
            if pref.get("phone_note"):
                m["phoneNote"] = pref["phone_note"]
            m["teresaTop"] = (p["home_site_id"] in teresa_sites and m["status"] != "Reached and booked"
                              and m["likelihood"] >= A.get("chw_list_min_likelihood", 70))
            out.append(m)
        self.REC["campaignMembers"] = out
        self.cm = {m["id"]: m for m in out}
        # members whose recheck reading after the campaign started is under 140/90
        self.controlled = sum(1 for i in ids if any(x["s"] < 140 and x["d"] < 90 for x in self.bp_after.get(i, [])))

    # scheduling and reminders -------------------------------------------------------------------------------
    def scheduling(self):
        cur, P = self.cur, self.P
        provs = {r["provider_id"]: r for r in rows(cur, "SELECT * FROM synthetic.provider")}

        def prov_name(pid):
            r = provs[pid]
            if r["specialty"].startswith("Mobile"):
                return f"{r['first_name']} {r['last_name']}"
            if "Nurse Practitioner" in r["specialty"]:
                return f"{r['first_name']} {r['last_name']}, NP"
            return f"Dr. {r['first_name']} {r['last_name']}"
        self.prov_name = prov_name
        linda = CONFIG["linda"]
        drive_to = dict(rows_to_pairs(rows(cur, "SELECT clinic_site_id, min(drive_minutes) FROM synthetic.travel_time WHERE patient_id = %(p)s GROUP BY 1",
                                           {"p": linda})))
        sl = rows(cur, """SELECT s.slot_id, s.slot_start, s.status, s.telehealth_flag, sc.provider_id, sc.clinic_site_id, sc.service_category
                          FROM synthetic.slot s JOIN synthetic.schedule sc ON sc.schedule_id = s.schedule_id
                          LEFT JOIN synthetic.appointment a ON a.slot_id = s.slot_id AND a.status = 'booked'
                          WHERE s.slot_start::date > %(as_of)s AND (s.status = 'open' OR a.patient_id = %(p)s)
                          ORDER BY s.slot_id""", {"as_of": self.as_of, "p": linda})
        slots = []
        for s in sl:
            site = self.site[s["clinic_site_id"]]
            if s["telehealth_flag"]:
                mode, where, drive = "Telehealth (video)", "Video visit", 0
            elif s["service_category"] == "mobile clinic":
                town = site["address"].split(",")[-2].strip()
                mode, where, drive = "Mobile clinic", f"Mobile clinic, {town}", int(drive_to.get(s["clinic_site_id"]) or 0)
            else:
                mode, where, drive = "In person", site["site_name"], int(drive_to.get(s["clinic_site_id"]) or self.pat[linda]["drive"])
            slots.append({"id": s["slot_id"], "mode": mode, "where": where, "provider": prov_name(s["provider_id"]),
                          "day": short_day(s["slot_start"]), "time": hm(s["slot_start"]), "driveMin": drive, "status": s["status"]})
        self.REC["slots"] = slots
        # pending bookings: book-visit tasks handed to the access coordinator, with the latest eligibility response
        pb = rows(cur, """SELECT t.patient_id, t.handed_off_by, t.reason_summary, t.task_id,
                                 (SELECT e.coverage_status FROM synthetic.eligibility_check e WHERE e.patient_id = t.patient_id
                                   ORDER BY e.checked_at DESC NULLS LAST LIMIT 1) cov,
                                 (SELECT e.payer FROM synthetic.eligibility_check e WHERE e.patient_id = t.patient_id
                                   ORDER BY e.checked_at DESC NULLS LAST LIMIT 1) payer
                          FROM synthetic.outreach_task t WHERE t.task_type = 'book_visit' AND t.status = 'open' AND t.assigned_to = %(a)s
                          ORDER BY t.created_at, t.task_id""", {"a": CONFIG["access"]})
        self.REC["pendingBookings"] = [{"memberId": r["patient_id"], "name": self.pat[r["patient_id"]]["name"], "from": r["handed_off_by"],
                                        "mode": self.cm[r["patient_id"]]["mode"] if r["patient_id"] in self.cm else "In person",
                                        "eligibility": (r["cov"] or "unknown").capitalize(), "planName": r["payer"] or self.cb["payer"],
                                        "taskId": r["task_id"]} for r in pb]
        # reminders: upcoming booked visits with their reminder messages
        ap = rows(cur, """SELECT a.appointment_id, a.patient_id, a.visit_mode, a.status, a.visit_type, a.visit_link, a.no_show_risk, s.slot_start,
                                 sc.clinic_site_id, a.provider_id, s.slot_id
                          FROM synthetic.appointment a JOIN synthetic.slot s ON s.slot_id = a.slot_id
                          JOIN synthetic.schedule sc ON sc.schedule_id = s.schedule_id
                          WHERE a.status IN ('booked', 'confirmed') AND s.slot_start::date > %(as_of)s ORDER BY s.slot_start""", P)
        msgs = defaultdict(list)
        for r in rows(cur, """SELECT m.* FROM synthetic.reminder_message m WHERE m.appointment_id = ANY(%(ids)s)
                              ORDER BY coalesce(m.sent_at, m.scheduled_for), m.message_id""", {"ids": [a["appointment_id"] for a in ap]}):
            msgs[r["appointment_id"]].append(r)
        prefs = {r["patient_id"]: r for r in rows(cur, """SELECT DISTINCT ON (patient_id) patient_id, quiet_hours_start, quiet_hours_end
                 FROM synthetic.contact_preference ORDER BY patient_id, preference_id""")}
        self.appts = ap
        reminders = []
        for a in ap:
            ms = msgs.get(a["appointment_id"])
            if not ms or a["patient_id"] not in self.pat:
                continue
            p = self.pat[a["patient_id"]]
            d = a["slot_start"].date()
            where = "video" if a["visit_mode"] == "telehealth" else self.site[a["clinic_site_id"]]["site_name"].replace("Sierra Basin ", "")
            day = rel_day(d, self.as_of, full=True)
            visit = f"{day}, {hm(a['slot_start'])} · {where}" if day in ("Today", "Tomorrow") else f"{day if a['patient_id'] == CONFIG['linda'] else short_day(d)}, {hm(a['slot_start'])} · {where}"
            offs = sorted({m["offset_hours"] for m in ms if m["offset_hours"] is not None}, reverse=True)
            plan = (", ".join(f"{o} h" for o in offs[:-1]) + f" and {offs[-1]} h before") if len(offs) > 1 else (f"{offs[0]} h before" if offs else "")
            q = prefs.get(a["patient_id"])
            if q and len(offs) >= 3:
                qs, qe = (int(str(q[k])[:2]) for k in ("quiet_hours_start", "quiet_hours_end"))
                plan += f" · quiet hours {qs % 12 or 12} {'PM' if qs >= 12 else 'AM'} to {qe % 12 or 12} {'PM' if qe >= 12 else 'AM'}"
            replies = [m["reply"] for m in ms if m["reply"]]
            delivered = [m for m in ms if m["delivery_status"] == "delivered"]
            status = ("Change requested (R)" if replies and replies[-1].upper() == "R" else "Confirmed" if replies and replies[-1].upper() == "C"
                      else "No reply yet" if delivered else "Scheduled")
            log = []
            for m in ms:
                if m["sent_at"]:
                    log.append({"at": f"{rel_day(m['sent_at'].date(), self.as_of)}, {hm(m['sent_at'])}", "dir": "out",
                                "text": TEMPLATE_TEXT.get(m["template"], m["template"])})
                if m["reply"]:
                    log.append({"at": f"{rel_day(m['replied_at'].date(), self.as_of)}, {hm(m['replied_at'])}", "dir": "in", "text": m["reply"]})
            reminders.append({"memberId": a["patient_id"], "name": p["name"], "visit": visit, "language": p["language"], "plan": plan,
                              "status": status, "log": log, "appointmentId": a["appointment_id"], "siteId": a["clinic_site_id"],
                              "date": d.isoformat(), "tomorrow": d == self.as_of + timedelta(days=1)})
        self.REC["reminders"] = reminders

    # model governance ------------------------------------------------------------------------------------------
    def model(self):
        cur, P = self.cur, self.P
        sc = rows(cur, """SELECT i.patient_id, i.model_version v, i.score, i.outreach_rank rk, i.segment,
                                 (SELECT c.icd10_code FROM synthetic.condition c WHERE c.patient_id = i.patient_id AND c.status = 'primary' LIMIT 1) prim
                          FROM synthetic.impactability_score i JOIN synthetic.patient p ON p.patient_id = i.patient_id
                          WHERE p.network_id = %(net)s AND i.segment = 'impactable'""", P)
        means = defaultdict(list)
        ranks = defaultdict(dict)
        for r in sc:
            g = GROUPS.get(r["prim"])
            fr = self.pat[r["patient_id"]]["frontier"]
            ranks[r["patient_id"]][r["v"]] = r["rk"]
            if g:
                means[(r["v"], g, fr)].append(float(r["score"]))
                means[(r["v"], "*", fr)].append(float(r["score"]))
        mean = lambda k: sum(means[k]) / len(means[k]) if means[k] else 0
        gap = lambda v: (mean((v, "*", False)) - mean((v, "*", True))) / mean((v, "*", False)) * 100 if means[(v, "*", False)] else 0
        self.GOV["SUBGROUP"] = [{"group": g, "town": rnd(mean(("v1.3", g, False))), "frontier": rnd(mean(("v1.3", g, True))),
                                 "frontierAfter": rnd(mean(("v1.4", g, True)))} for g in GROUPS.values()]
        cards = {r["model_version"]: r for r in rows(cur, "SELECT * FROM synthetic.model_card")}
        released = next(v for v, r in cards.items() if r["release_status"] == "released")
        cand = next((v for v, r in cards.items() if r["release_status"] != "released"), released)
        feats = rows(cur, "SELECT * FROM synthetic.model_feature WHERE model_version = %(v)s ORDER BY weight DESC, model_feature_id", {"v": cand})
        top = CONFIG["top_n"]
        cms165 = {r["patient_id"] for r in rows(cur, """SELECT patient_id FROM synthetic.quality_measure_result WHERE measure_code = 'CMS165'
                                                       AND denominator_flag""")}
        conds = defaultdict(set)
        for r in rows(cur, "SELECT patient_id, icd10_code FROM synthetic.condition WHERE patient_id = ANY(%(ids)s)",
                      {"ids": [p for p, r in ranks.items() if r.get("v1.3") and r.get("v1.4") and ((r["v1.3"] <= top) != (r["v1.4"] <= top))]}):
            conds[r["patient_id"]].add(r["icd10_code"])
        swaps = []
        for pid, r in ranks.items():
            b, a = r.get("v1.3"), r.get("v1.4")
            if not b or not a or (b <= top) == (a <= top):
                continue
            c = conds[pid]
            prim = next((x["prim"] for x in sc if x["patient_id"] == pid and x["v"] == "v1.3"), None)
            label = "Hypertension and diabetes" if {"I10", "E11.9"} <= c else (GROUPS.get(prim) or "Other")
            swaps.append({"id": pid, "direction": "Enters top 300" if a <= top else "Leaves top 300", "condition": label,
                          "driveMin": self.pat[pid]["drive"], "rankBefore": b, "rankAfter": a, "inBpDenominator": pid in cms165})
        swaps.sort(key=lambda s: (s["direction"] != "Enters top 300", s["id"]))
        self.GOV["swaps"] = swaps
        self.GOV["FEATURES"] = []
        for f in feats:
            note = f["note"]
            if f["feature_code"] == "pcVisits":
                note = re.sub(r"\d+% fewer", f"{self._fewer_visits()}% fewer", note)
            if f["feature_code"] == "ed":
                note = re.sub(r"\d+-day", f"{self.lag}-day", note)
            self.GOV["FEATURES"].append({"id": f["feature_code"], "name": f["feature_name"], "weight": float(f["weight"]), "kind": f["kind"], "note": note})
        # drive time against visits for a de-identified sample (the access scatter)
        ap = rows(cur, """SELECT p.patient_id, (SELECT count(*) FROM synthetic.encounter e WHERE e.patient_id = p.patient_id
                                AND e.encounter_type IN ('office', 'telehealth') AND e.start_time::date BETWEEN %(lv_start)s AND %(end)s) visits
                          FROM synthetic.patient p WHERE p.network_id = %(net)s ORDER BY md5(p.patient_id) LIMIT 600""", P)
        fr = [r for r in ap if self.pat[r["patient_id"]]["frontier"]][:30]
        tw = [r for r in ap if not self.pat[r["patient_id"]]["frontier"]][:60]
        pts = sorted(fr + tw, key=lambda r: r["patient_id"])
        self.GOV["accessPoints"] = [{"id": f"P{i}", "driveMin": self.pat[r["patient_id"]]["drive"], "visits": r["visits"],
                                     "frontier": self.pat[r["patient_id"]]["frontier"]} for i, r in enumerate(pts)]
        enter = [s for s in swaps if s["direction"].startswith("Enters")]
        frontier_drives = sorted(p["drive"] for p in self.pat.values() if p["frontier"] and p["drive"] is not None)
        adt = one(cur, "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM received_at - event_time) / 60) FROM synthetic.adt_event")
        src = dict(rows_to_pairs(rows(cur, "SELECT source_kind, count(*) FROM synthetic.data_source WHERE record_count > 0 GROUP BY 1")))
        screened = one(cur, """SELECT count(DISTINCT s.patient_id) FROM synthetic.sdoh_screening s JOIN synthetic.patient p ON p.patient_id = s.patient_id
                               WHERE p.network_id = %(net)s""", P)
        no_bb = one(cur, """SELECT count(*) FROM synthetic.patient p JOIN synthetic.broadband_coverage b ON b.zcta = p.zip_code
                            WHERE p.network_id = %(net)s AND NOT b.served_flag""", P)
        self.screened = screened
        self.C["MODEL"] = {
            "name": cards[released]["model_name"], "version": released, "candidate": cand,
            "frontierGapPct": rnd(gap(released)), "frontierGapAfterPct": rnd(gap(cand)),
            "releaseThresholdPct": rnd(cards[cand].get("release_threshold_pct") or self.A.get("model_release_threshold_pct", 5)),
            "missingFromTop": len(enter), "inBpDenominator": sum(1 for s in enter if s["inBpDenominator"]),
            "fewerVisitsPct": self._fewer_visits(), "medianDriveMin": rnd(statistics.median(frontier_drives)) if frontier_drives else 0,
            "noBroadband": no_bb, "socialScreenedPct": pct(screened, self.members),
            "publicSources": src.get("public", 0), "syntheticSources": src.get("synthetic", 0),
            "adtLag": "Under 1 hour" if adt is not None and adt < 60 else f"About {rnd((adt or 0) / 60)} hours",
            "auc": float(cards[cand]["auc"]), "unmatchedRecords": one(cur, "SELECT count(*) FROM synthetic.match_review WHERE status = 'unmatched'"),
        }
        self.match_reasons = rows(cur, """SELECT reason, count(*) n FROM synthetic.match_review WHERE status = 'unmatched'
                                          GROUP BY 1 ORDER BY 2 DESC""")

    def _fewer_visits(self):
        if not hasattr(self, "_fv"):
            r = rows(self.cur, """SELECT p.patient_id, count(e.encounter_id) n FROM synthetic.patient p
                                  LEFT JOIN synthetic.encounter e ON e.patient_id = p.patient_id AND e.encounter_type IN ('office', 'telehealth')
                                   AND e.start_time::date BETWEEN %(lv_start)s AND %(end)s
                                  WHERE p.network_id = %(net)s GROUP BY 1""", self.P)
            f = [x["n"] for x in r if self.pat[x["patient_id"]]["frontier"]]
            t = [x["n"] for x in r if not self.pat[x["patient_id"]]["frontier"]]
            self._fv = rnd((1 - (sum(f) / len(f)) / (sum(t) / len(t))) * 100) if f and t else 0
        return self._fv

    # counties, networks, the state view -------------------------------------------------------------------
    def geography(self):
        cur, P = self.cur, self.P
        fips = [c["fips"] for c in self.counties]
        pub = {r["fips"]: r for r in rows(cur, """
            SELECT c.f AS fips,
                   (SELECT p.data_value FROM public_data.cdc_places p WHERE p.locationid::text = c.f AND p.measureid = 'BPHIGH'
                      AND p.data_value_type = 'Crude prevalence' ORDER BY p.year DESC LIMIT 1) htn,
                   (SELECT p.data_value FROM public_data.cdc_places p WHERE p.locationid::text = c.f AND p.measureid = 'DIABETES'
                      AND p.data_value_type = 'Crude prevalence' ORDER BY p.year DESC LIMIT 1) dm,
                   (SELECT s.rpl_themes FROM public_data.svi_county s WHERE s.fips::text = c.f) svi,
                   (SELECT bool_or(h.hpsa_component_type_description = 'Single County') FROM public_data.hpsa_primary_care h
                     WHERE h.common_state_county_fips_code = c.f AND h.hpsa_status = 'Designated' AND h.designation_type ILIKE '%%Geographic%%') whole,
                   (SELECT count(*) FROM public_data.hpsa_primary_care h WHERE h.common_state_county_fips_code = c.f AND h.hpsa_status = 'Designated') hpsa_n,
                   (SELECT a.pct_households_broadband FROM public_data.acs_county a WHERE a.county_fips::text = c.f) bb
            FROM unnest(%(f)s::text[]) AS c(f)""", {"f": fips})}
        # what the ACS broadband share measures (public_data.acs_variables, the ACS variable dictionary)
        bb_label = one(cur, """SELECT acs_table || ': ' || label FROM public_data.acs_variables
                              WHERE "column" = 'pct_households_broadband'""") or "ACS broadband subscription share"
        # County Health Rankings 2025 (public_data.county_health_rankings), when loaded
        chr_ = {}
        if one(cur, "SELECT to_regclass('public_data.county_health_rankings') IS NOT NULL"):
            chr_ = {r["fips"]: r for r in rows(cur, """SELECT fipscode::text fips, year, v001_rawvalue prem, v004_rawvalue pcp,
                        v005_rawvalue stays, v085_rawvalue unins, v050_rawvalue mammo FROM public_data.county_health_rankings
                        WHERE fipscode::text = ANY(%(f)s)""", {"f": fips})}
        visits = rows(cur, """WITH lbp AS (SELECT DISTINCT c.encounter_id FROM synthetic.claim c JOIN synthetic.claim_line cl ON cl.claim_id = c.claim_id
                                           WHERE cl.diagnosis_code = 'M54.50' AND c.encounter_id IS NOT NULL)
                              SELECT p.county_fips cf, extract(month FROM e.start_time)::int m, count(*) n
                              FROM synthetic.encounter e JOIN synthetic.patient p ON p.patient_id = e.patient_id
                              WHERE e.encounter_type IN ('office', 'telehealth') AND e.start_time::date BETWEEN %(start)s AND %(end)s
                                AND e.encounter_id NOT IN (SELECT encounter_id FROM lbp) GROUP BY 1, 2""", P)
        vm = defaultdict(dict)
        for r in visits:
            vm[r["cf"]][r["m"]] = r["n"]
        hf = dict(rows_to_pairs(rows(cur, """SELECT p.county_fips, count(DISTINCT c.patient_id) FROM synthetic.condition c
                    JOIN synthetic.patient p ON p.patient_id = c.patient_id WHERE c.icd10_code = 'I50.9' GROUP BY 1""")))
        ed_c = defaultdict(int)
        for r in self.ed_rows:
            ed_c[r["cf"]] += r["n"]
        last3 = [self.period_end.month - 2, self.period_end.month - 1, self.period_end.month]
        out = []
        for c in self.counties:
            f = c["fips"]
            pb = pub.get(f, {})
            jan = vm[f].get(1, 0)
            late = sum(vm[f].get(m, 0) for m in last3) / 3
            den, num, _ = self.q_agg[("CMS165", "cf", f)]
            out.append({"id": c["id"], "name": c["name"], "members": self.mem_by_county.get(f, 0),
                        "htnPct": rnd(pb.get("htn"), 1), "diabetesPct": rnd(pb.get("dm"), 1), "svi": rnd(pb.get("svi"), 2),
                        "hpsa": "Whole county" if pb.get("whole") else "Part of county", "hpsaDesignations": pb.get("hpsa_n") or 0,
                        "broadbandPct": rnd(pb.get("bb")) if pb.get("bb") is not None else None,
                        "broadbandSource": f"Census ACS {bb_label} (public_data.acs_county)",
                        "pcVisitChangePct": pct(late - jan, jan) if jan else 0,
                        "edPer1000": rnd(ed_c[f] / self.mem_by_county.get(f, 1) * 1000 * self.annualize),
                        "lowValue": rnd(self.lv_county[f] / 1000) * 1000, "heartFailure": hf.get(f, 0), "bpControlPct": pct(num, den),
                        "fips": f,
                        "chr": ({"year": chr_[f]["year"], "prematureDeath": rnd(chr_[f]["prem"]), "pcpPer100k": rnd((chr_[f]["pcp"] or 0) * 1e5),
                                 "preventableStays": rnd(chr_[f]["stays"]), "uninsuredPct": rnd((chr_[f]["unins"] or 0) * 100, 1),
                                 "mammographyPct": rnd((chr_[f]["mammo"] or 0) * 100), "source": "County Health Rankings (public_data.county_health_rankings)"}
                                if f in chr_ else None)})
        self.C["COUNTIES"] = out
        self.county = {c["id"]: c for c in out}
        nets = []
        site_n = Counter(s["grantee_id"] for s in self.sites if s["site_type"] != "Mobile clinic")
        ed_n = defaultdict(int)
        for r in self.ed_rows:
            ed_n[r["net"]] += r["n"]
        for g in self.grantees:
            bpd, bpn, _ = self.q_agg[("CMS165", "net", g["grantee_id"])]
            crd, crn, _ = self.q_agg[("CMS130", "net", g["grantee_id"])]
            nets.append({"id": g["grantee_id"], "name": g["network_name"], "sites": site_n[g["grantee_id"]], "bpControlPct": pct(bpn, bpd),
                         "colorectalPct": pct(crn, crd), "edPer1000": rnd(ed_n[g["grantee_id"]] / self.mem_by_net[g["grantee_id"]] * 1000 * self.annualize)})
        self.C["NETWORKS"] = nets
        low_bb = rows(cur, """SELECT b.zcta, z.place_name, z.county_id, b.household_pct FROM synthetic.broadband_coverage b
                              JOIN synthetic.zip_place z ON z.zcta = b.zcta WHERE NOT b.served_flag ORDER BY b.coverage_id""")
        self.low_bb = low_bb
        self.low_bb_members = one(cur, """SELECT count(*) FROM synthetic.patient p JOIN synthetic.broadband_coverage b ON b.zcta = p.zip_code
                                          WHERE NOT b.served_flag""")
        self.hpsa_counties = sum(1 for c in out if c["hpsaDesignations"] > 0)

    # assemble ------------------------------------------------------------------------------------------------
    def assemble(self):
        C, REC, A, P = self.C, self.REC, self.A, self.P
        gap_total = self.actual - self.expected
        coding, ed, lowv = rnd(self.coding_pmpm, 1), rnd(self.ed_gap_pmpm, 1), rnd(self.lv_pmpm, 1)
        sb_name = next(g["network_name"] for g in self.grantees if g["grantee_id"] == P["net"])
        lv_services = len(self.lv_sb)
        C.update({
            "ILLUSTRATIVE": CONFIG["illustrative"], "PERSONAS": CONFIG["personas"],
            "ORG": {"network": sb_name, "networkShort": " ".join(sb_name.split()[:2]), "plan": self.cb["payer"],
                    "program": next(g["program_initiative"] for g in self.grantees if g["grantee_id"] == P["net"]), "product": CONFIG["product"]},
            "CONTRACT": {"members": self.members, "actualPmpm": rnd(self.actual), "expectedPmpm": rnd(self.expected),
                         "abovePct": rnd(gap_total / self.expected * 100, 1), "annualGap": rnd(gap_total * self.members * 12 / 1e5) * 100000,
                         "daysLeft": (self.end - self.as_of).days, "gateNeeded": self.cb["quality_gate_required"],
                         "gateMeasures": self.cb["quality_gate_total"], "gateMet": self.gate_met, "claimsLagDays": self.lag},
            "GAP": [{"id": "coding", "label": "Coding gap", "value": coding,
                     "note": f"Not spending: {self.coding_members} high-need members not yet recaptured"},
                    {"id": "ed", "label": "Excess avoidable ED", "value": ed,
                     "note": f"{rnd(self.ed_rate)} visits per 1,000 against {rnd(self.ed_bench)}"},
                    {"id": "lowValue", "label": "Low-value care", "value": lowv,
                     "note": f"{lv_services:,} services across {len(self.lv_measures)} measures"},
                    {"id": "other", "label": "Other", "value": rnd(rnd(gap_total) - coding - ed - lowv, 1), "note": "Noise"}],
            "SEGMENTS": [{"id": k, "label": CONFIG["segments"][k][0], "members": n, "sharePct": pct(n, self.members, 1),
                          "spendPct": rnd(self.seg_spend.get(k, 0) * 100), "action": CONFIG["segments"][k][1]}
                         for k, n in [(k, sum(1 for p in self.pat.values() if p["segment"] == k)) for k in ("highNeed", "impactable", "stable")]],
            "COHORT": {"topRanked": CONFIG["top_n"], "avoidedCost12m": rnd(self._avoided() / 1e5) * 100000},
            "CODING": {"members": self.coding_members, "ofHighNeed": self.high_need, "sharePct": pct(self.coding_members, self.high_need),
                       "understatedPct": rnd(self.coding_pmpm / self.expected * 100, 1), "correctedBenchmark": rnd(self.expected + self.coding_pmpm),
                       "gapAfterPct": rnd((self.actual - self.expected - self.coding_pmpm) / (self.expected + self.coding_pmpm) * 100, 1)},
            "LOW_VALUE": {"services": lv_services, "annual": rnd(self.lv_annual / 1000) * 1000, "measures": len(self.lv_measures),
                          "lbpImaging": rnd(self.lbp_usd / 1000) * 1000, "winnemuccaSharePct": self.win_share,
                          "networkRatePct": self.img_network, "winnemuccaRatePct": self.img_rate.get(CONFIG["imaging_site"], 0),
                          "rotationMonth": MONTH[self.rotation.month], "clinicians": self.locum_count},
            "ED": {"per1000": rnd(self.ed_rate), "benchmark": rnd(self.ed_bench)},
            "MEASURES": [{k: m[k] for k in ("id", "name", "current", "target", "higherIsBetter", "projected")} for m in self.measures],
        })
        bp = self.bp
        modes = Counter(m["mode"] for m in REC["campaignMembers"])
        C["BP"] = {"hypertensive": bp["denominator"], "nearControl": self.near, "withinPoints": 10,
                   "needed": math.ceil(bp["target"] / 100 * bp["denominator"]) - bp["numerator"], "projected": self.bp_projected_controls,
                   "inPerson": modes["In person"], "telehealth": modes["Telehealth"],
                   "cuffsToShip": sum(1 for m in REC["campaignMembers"] if m["cuff"] == "Ship first"), "shortPts": bp["target"] - bp["current"]}
        C["FIT"] = {"gainPts": self.fit_gain}
        drop = max((-c["pcVisitChangePct"] for c in C["COUNTIES"]), default=0)
        all_ed = sum(r["n"] for r in self.ed_rows)
        C["STATE"] = {"networks": len(self.grantees), "sites": sum(n["sites"] for n in C["NETWORKS"]), "members": self.all_members,
                      "counties": len(self.counties), "hpsaCounties": self.hpsa_counties,
                      "edPer1000": rnd(all_ed / self.all_members * 1000 * self.annualize), "lowValue": rnd(sum(self.lv_county.values()) / 1e5) * 100000,
                      "pcVisitDropPct": drop, "lowBroadbandZips": len(self.low_bb), "broadbandFloorPct": rnd(A.get("broadband_floor_pct", 40)),
                      "suppressUnder": rnd(A.get("suppress_under", 11)), "optionAEdCutPct": rnd(A.get("option_a_ed_cut_pct", 12))}
        members = REC["campaignMembers"]
        teresa = [t for t in self.tasks.values() if t["assigned_to"] == CONFIG["chw"]]
        rem = REC["reminders"]
        provs = one(self.cur, "SELECT count(*) FROM synthetic.provider WHERE specialty ILIKE '%%telehealth%%'")
        teresa_open = one(self.cur, "SELECT count(*) FROM synthetic.outreach_task WHERE assigned_to = %(a)s AND status <> 'closed'", {"a": CONFIG["chw"]})
        C["CARE"] = {"teresaTop": sum(1 for m in members if m["teresaTop"]),
                     "teresaNoCallback": sum(1 for t in teresa if t["status"] == "left_message" and t["last_attempt_at"]
                                             and t["last_attempt_at"].date() == self.as_of - timedelta(days=1)),
                     "teresaOpen": teresa_open, "booked": sum(1 for m in members if m["status"] == "Reached and booked"),
                     "controlled": self.controlled, "brandonBookings": len(REC["pendingBookings"]),
                     "brandonUnconfirmed": sum(1 for r in rem if r["status"] == "No reply yet" and r["tomorrow"]),
                     "brandonRReplies": sum(1 for r in rem if r["status"].startswith("Change requested")), "telehealthProviders": provs}
        C["SITES"] = [{"id": s["clinic_site_id"], "name": s["site_name"].replace("Sierra Basin ", ""), "county": self.cid[s["county_fips"]],
                       "members": self.mem_by_site[s["clinic_site_id"]], "pmpm": rnd(self.site_pmpm.get(s["clinic_site_id"], 0)),
                       "imagingPct": self.img_rate.get(s["clinic_site_id"], 0), "lowValue": rnd(self.lv_site[s["clinic_site_id"]] / 1000) * 1000,
                       "locum": s["locums"] > 0} for s in self.sb_sites]
        C["PMPM_TREND"] = self.pmpm_trend
        C["WINNEMUCCA_TREND"] = self.win_trend
        C["LOCUMS"] = self.locums
        C["LV_MEASURES"] = self.lv_measures
        a_reach = sum(self.county[c]["members"] for c in CONFIG["focus_counties"])
        ed_cut = rnd(A.get("option_a_ed_cut_pct", 12))
        C["OPTIONS"] = [
            {"id": "A", "name": CONFIG["options"]["A"][0], "reach": a_reach, "cost": rnd(A.get("option_a_cost", 0)),
             "outcome": f"Recover most lost primary care visits; avoidable ED down about {ed_cut}% there", "time": CONFIG["options"]["A"][1],
             "impact": CONFIG["options"]["A"][2]},
            {"id": "B", "name": CONFIG["options"]["B"][0], "reach": self.all_members, "cost": rnd(A.get("option_b_cost", 0)),
             "outcome": f"Cut about a third of the {usd_m(C['STATE']['lowValue'])}", "time": CONFIG["options"]["B"][1], "impact": CONFIG["options"]["B"][2]},
            {"id": "C", "name": CONFIG["options"]["C"][0], "reach": rnd(self.low_bb_members / 100) * 100, "cost": rnd(A.get("option_c_cost", 0)),
             "outcome": "Access floor that option A depends on", "time": CONFIG["options"]["C"][1], "impact": CONFIG["options"]["C"][2]}]
        C["LOW_BB_PLACES"] = [r["place_name"] for r in self.low_bb]
        C["FRESHNESS"] = f"Claims through Q{self.quarter} ({self.lag}-day lag) · ADT today"
        screened_site = dict(rows_to_pairs(rows(self.cur, """SELECT p.home_site_id, count(DISTINCT s.patient_id) FROM synthetic.sdoh_screening s
                              JOIN synthetic.patient p ON p.patient_id = s.patient_id WHERE p.network_id = %(net)s GROUP BY 1""", P)))
        C["SITE_SOCIAL"] = {s["clinic_site_id"]: pct(screened_site.get(s["clinic_site_id"], 0), self.mem_by_site[s["clinic_site_id"]]) for s in self.sb_sites}
        C["TERESA_SITES"] = self.teresa_sites
        C["SCOPES"] = {}
        C["TASKS"] = {}
        self._patients()

    def _avoided(self):
        return float(one(self.cur, """SELECT coalesce(sum(i.predicted_cost_avoided), 0) FROM synthetic.impactability_score i
                                      JOIN synthetic.patient p ON p.patient_id = i.patient_id
                                      WHERE p.network_id = %(net)s AND i.model_version = 'v1.3' AND i.outreach_rank <= %(n)s""",
                         {"net": CONFIG["network"], "n": CONFIG["top_n"]}))

    def _patients(self):
        cur, C = self.cur, self.C
        L = self.cm[CONFIG["linda"]]
        lp = self.pat[CONFIG["linda"]]
        nxt = [a for a in self.appts if a["patient_id"] == CONFIG["linda"]]
        visit = {}
        link = None
        if nxt:
            a = nxt[0]
            t = a["slot_start"]
            visit = {"day": DAY[t.weekday()], "date": f"{MON[t.month]} {t.day}", "time": hm(t),
                     "es": f"el {ES_DAY[t.weekday()]} {t.day} de {ES_MON[t.month]} a las {hm(t)}", "appointmentId": a["appointment_id"],
                     "mode": a["visit_mode"]}
            link = a["visit_link"]
        raw = rows(cur, """SELECT value_systolic s, value_diastolic d, reading_time FROM synthetic.rpm_reading WHERE patient_id = %(p)s
                           AND reading_time::date >= %(cs)s ORDER BY reading_time DESC LIMIT 1""", {"p": CONFIG["linda"], "cs": self.campaign_start})
        b = self.bp_before.get(CONFIG["linda"])
        C["LINDA"] = {"name": L["name"], "first": lp["first_name"], "age": L["age"], "town": L["site"], "driveMin": L["driveMin"],
                      "bp": L["lastBp"], "bpMonth": L["lastBpMonth"], "monthsSinceVisit": L["monthsSinceVisit"],
                      "missedVisits": self.noshow.get(CONFIG["linda"], 0), "language": L["language"],
                      "reading": bp_text(raw[0]["s"], raw[0]["d"]) if raw else None,
                      "readingRecorded": any(x["home"] for x in self.bp_after.get(CONFIG["linda"], [])),
                      "visit": visit, "link": link, "memberId": CONFIG["linda"]}

    # datasets --------------------------------------------------------------------------------------------------
    def datasets(self):
        C, REC, GOV, DS = self.C, self.REC, self.GOV, self.DS
        S = C["SITES"]
        members = REC["campaignMembers"]
        DS["site_imaging"] = bar(f"Low back pain imaging by site, share of eligible visits (network {C['LOW_VALUE']['networkRatePct']}%)",
                                 [{"name": "Imaging rate", "points": [{"label": s["name"], "value": s["imagingPct"]} for s in S]}], unit="%")
        DS["site_lowvalue"] = bar("Low-value spend by site, $K a year",
                                  [{"name": "Low-value care ($K)", "points": [{"label": s["name"], "value": rnd(s["lowValue"] / 1000)} for s in S]}])
        DS["site_social"] = bar(f"Members with a social needs screening, by site (network {C['MODEL']['socialScreenedPct']}%)",
                                [{"name": "Screened", "points": [{"label": s["name"], "value": C["SITE_SOCIAL"][s["id"]]} for s in S]}], unit="%")
        top5 = sorted(C["LV_MEASURES"], key=lambda m: -m["dollars"])[:5]
        DS["lv_top5"] = table(f"The five largest of {C['LOW_VALUE']['measures']} low-value measures ({C['LOW_VALUE']['services']:,} services, "
                              f"{usd_k(C['LOW_VALUE']['annual'])} a year in all)",
                              [col("measure", "Measure"), col("basis", "Basis"), col("services", "Services", kind="number"),
                               col("spend", "Annual spend", align="right")],
                              [{"measure": m["name"], "basis": m["basis"], "services": m["services"], "spend": usd_k(m["dollars"])} for m in top5])
        now = C["CONTRACT"]["abovePct"]
        after = C["CODING"]["gapAfterPct"]
        drift, moves = self.A.get("gap_drift_pts_per_quarter", 0), self.A.get("three_moves_pts_per_quarter", 0)
        qs = [f"Q{(self.quarter + i) % 4 + 1} {self.period_end.year + (self.quarter + i) // 4}" for i in range(5)]
        DS["projection_2027"] = bar("Gap to expected cost by quarter, through 2027",
                                    [{"name": "Do nothing", "points": [{"label": q, "value": rnd(now + drift * i, 1)} for i, q in enumerate(qs)]},
                                     {"name": "Three moves", "points": [{"label": q, "value": max(0, rnd(after - moves * i, 1))} for i, q in enumerate(qs)]}],
                                    unit="%", kind="line")
        M = C["MEASURES"]
        DS["measure_projection"] = bar("Each gate measure: current, projected by December 31, and target (CMS122 is lower-is-better)",
                                       [{"name": n, "points": [{"label": m["id"], "value": m[k]} for m in M]}
                                        for n, k in (("Current", "current"), ("Projected Dec 31", "projected"), ("Target", "target"))], unit="%")
        DS["mode_split"] = {"columns": 3, "children": [
            {"type": "stat", "version": 1, "props": {"label": "Telehealth with home cuff", "value": str(C["BP"]["telehealth"]), "caption": "Drive more than an hour", "status": "info"}},
            {"type": "stat", "version": 1, "props": {"label": "In person", "value": str(C["BP"]["inPerson"]), "caption": "Drive under an hour"}},
            {"type": "stat", "version": 1, "props": {"label": "Cuffs to ship first", "value": str(C["BP"]["cuffsToShip"]), "caption": "Before the telehealth visit", "status": "warning"}}]}
        mcols = [col("rank", "#", kind="number"), col("name", "Member"), col("reasons", "Top reasons"), col("likely", "Likely to control", align="right"),
                 col("mode", "Visit mode")]
        mrow = lambda m: {"rank": m["rank"], "name": m["name"], "reasons": " · ".join(m["reasons"]), "likely": f"{m['likelihood']}%", "mode": m["mode"]}
        DS["campaign_top10"] = table(f"Top 10 of the {len(members)}, by likelihood of reaching control", mcols, [mrow(m) for m in members[:10]])
        DS["teresa_top5"] = table("Your five patients closest to control", mcols, [mrow(m) for m in members if m["teresaTop"]][:5])
        left = [m for m in members if m["lastContact"].endswith("left message")]
        DS["teresa_noreply"] = table("Called yesterday, no callback yet: call these back today",
                                     [col("rank", "#", kind="number"), col("name", "Patient"), col("phone", "Phone"), col("best", "Best time"), col("mode", "Visit mode")],
                                     [{"rank": m["rank"], "name": m["name"], "phone": m["phone"], "best": m["bestTime"], "mode": m["mode"]} for m in left])
        DS["subgroup"] = bar("Average risk rank by condition group (percentile), frontier vs town",
                             [{"name": "Town", "points": [{"label": g["group"], "value": g["town"]} for g in GOV["SUBGROUP"]]},
                              {"name": "Frontier", "points": [{"label": g["group"], "value": g["frontier"]} for g in GOV["SUBGROUP"]]}])
        cur_f = [f for f in GOV["FEATURES"] if f["kind"] == "Current"]
        w2 = rnd(sum(f["weight"] for f in cur_f if f["id"] in ("cost", "pcVisits")) * 100)
        DS["features"] = table(f"Feature list, {C['MODEL']['version']}: prior-year cost and visits carry {w2}% of the weight",
                               [col("feature", "Feature"), col("weight", "Weight", align="right"), col("note", "How it treats frontier members")],
                               [{"feature": f["name"], "weight": f"{rnd(f['weight'] * 100)}%", "note": f["note"]} for f in cur_f])
        sw = GOV["swaps"]
        enter = [s for s in sw if s["direction"].startswith("Enters")]
        leave = [s for s in sw if not s["direction"].startswith("Enters")]
        scol = [col("id", "Member"), col("change", "Change"), col("condition", "Condition"), col("drive", "Drive", align="right"),
                col("rank", "Rank before to after", align="right")]
        srow = lambda s: {"id": s["id"], "change": s["direction"], "condition": s["condition"], "drive": f"{s['driveMin']} min",
                          "rank": f"{s['rankBefore']} to {s['rankAfter']}"}
        DS["swaps"] = table(f"Sample of the {len(enter)} entering and {len(leave)} leaving the top {CONFIG['top_n']}, de-identified", scol,
                            [srow(s) for s in enter[:4] + leave[:4]])
        DS["swaps_in"] = table(f"8 of the {len(enter)} high-need frontier members, de-identified; {C['MODEL']['inBpDenominator']} are in the BP denominator",
                               scol, [srow(s) for s in enter[:8]])
        Mo = C["MODEL"]
        DS["before_after"] = {"columns": 2, "children": [
            {"type": "stat", "version": 1, "props": {"label": "Frontier gap", "value": f"{Mo['frontierGapPct']}% to {Mo['frontierGapAfterPct']}%",
                                                     "caption": f"Threshold {Mo['releaseThresholdPct']}%",
                                                     "status": "good" if Mo["frontierGapAfterPct"] <= Mo["releaseThresholdPct"] else "warning"}},
            {"type": "stat", "version": 1, "props": {"label": f"Top {CONFIG['top_n']}", "value": f"{len(enter)} in, {len(leave)} out",
                                                     "caption": "High-need frontier enter", "status": "info"}},
            {"type": "stat", "version": 1, "props": {"label": "Count toward CMS165", "value": str(Mo["inBpDenominator"]), "caption": "Now reached by outreach", "status": "good"}},
            {"type": "stat", "version": 1, "props": {"label": "Accuracy (AUC)", "value": f"{Mo['auc']:.2f}", "caption": "Holds steady"}}]}
        DS["county_lowvalue"] = bar(f"Low-value spend by county, $K a year ({usd_m(C['STATE']['lowValue'])} in all)",
                                    [{"name": "Low-value care ($K)", "points": [{"label": c["name"], "value": rnd(c["lowValue"] / 1000)} for c in C["COUNTIES"]]}])
        cut = C["STATE"]["optionAEdCutPct"]
        fc = [self.county[c] for c in CONFIG["focus_counties"]]
        DS["ed_projection"] = bar(f"Avoidable ED per 1,000, now and 12 months after options A and C (about {cut}% lower)",
                                  [{"name": "Now", "points": [{"label": c["name"], "value": c["edPer1000"]} for c in fc]},
                                   {"name": "In 12 months", "points": [{"label": c["name"], "value": rnd(c["edPer1000"] * (1 - cut / 100))} for c in fc]}])
        DS["options"] = table("Outcomes Accelerator funding options (reach and cost illustrative)",
                              [col("option", "Option"), col("what", "What"), col("reach", "Reach", align="right"), col("cost", "Cost", align="right"),
                               col("outcome", "Projected outcome"), col("time", "Time to impact"), col("alignment", "RHTP alignment")],
                              [{"option": o["id"], "what": o["name"], "reach": f"{o['reach']:,} members",
                                "cost": usd_m(o["cost"]) if o["cost"] else "No new funds", "outcome": o["outcome"], "time": o["time"],
                                "alignment": "Outcomes Accelerator"} for o in C["OPTIONS"]])
        rem = REC["reminders"]
        rcols = [col("name", "Patient"), col("visit", "Visit"), col("language", "Language"), col("next", "Next step")]
        nr = [r for r in rem if r["status"] == "No reply yet" and r["tomorrow"]]
        rr = [r for r in rem if r["status"].startswith("Change requested")]
        DS["reminders_unconfirmed"] = table(f"{len(nr)} visits tomorrow with no reply", rcols,
                                            [{"name": r["name"], "visit": r["visit"], "language": r["language"], "next": "Call task on Teresa’s worklist"} for r in nr])
        DS["reminders_r"] = table(f"{len(rr)} patients replied R", rcols,
                                  [{"name": r["name"], "visit": r["visit"], "language": r["language"], "next": "Three new slots by SMS"} for r in rr])
        DS["networks"] = table("Participating networks, aggregated and de-identified",
                               [col("network", "Network"), col("sites", "Sites", kind="number"), col("bp", "BP control", align="right"),
                                col("crc", "Colorectal screening", align="right"), col("ed", "Avoidable ED per 1,000", kind="number")],
                               [{"network": n["name"], "sites": n["sites"], "bp": f"{n['bpControlPct']}%", "crc": f"{n['colorectalPct']}%", "ed": n["edPer1000"]}
                                for n in C["NETWORKS"]])

    def run(self) -> dict:
        self.frame()
        self.reference()
        self.cost()
        self.imaging()
        self.quality()
        self.campaign()
        self.scheduling()
        self.model()
        self.geography()
        self.assemble()
        self.datasets()
        return {"constants": self.C, "records": self.REC, "governance": self.GOV, "datasets": self.DS,
                "meta": {"asOf": self.as_of.isoformat(), "periodEnd": self.period_end.isoformat(), "months": self.months,
                         "members": self.members, "assumptions": self.A}}


def rows_to_pairs(rs):
    return [tuple(r.values())[:2] for r in rs]


def compute(cur) -> dict:
    """The whole computed context. `cur` is a psycopg2 cursor on rain_v4."""
    calc = _Calc(cur)
    ctx = calc.run()
    try:      # the patient and payer personas (Linda, Rosa, Hannah) add their own computed values
        import metrics_personas_v4
    except ImportError:
        return ctx
    metrics_personas_v4.extend(ctx, cur, calc)
    return ctx


# ─── a small cache: recomputed when the source rows change (any writer), after a write-back, or after the TTL ─
_lock = threading.Lock()
_cache: dict = {"at": 0.0, "value": None, "version": 0, "ms": 0.0, "fp": None}
TTL_SECONDS = 600
# Postgres counts every insert, update and delete per table. A different total means somebody changed the
# source rows (the write-back flow, psql, pgAdmin, the generator), so the next request recomputes.
_FINGERPRINT_SQL = """SELECT coalesce(sum(n_tup_ins + n_tup_upd + n_tup_del), 0)::bigint || ':' || count(*)
                      FROM pg_stat_user_tables WHERE schemaname IN ('synthetic', 'public_data')"""


def invalidate():
    with _lock:
        _cache["at"] = 0.0
        _cache["version"] += 1


def cached(cur) -> tuple[dict, dict]:
    """(context, info) - info says whether it was computed for this request, why, and how long it took."""
    fp = one(cur, _FINGERPRINT_SQL)
    with _lock:
        fresh = _cache["value"] is not None and time.time() - _cache["at"] < TTL_SECONDS
        if fresh and fp == _cache["fp"]:
            return _cache["value"], {"computed": False, "ms": _cache["ms"], "version": _cache["version"],
                                     "ageSeconds": round(time.time() - _cache["at"], 1), "fingerprint": fp}
        reason = ("first request" if _cache["value"] is None else
                  "source rows changed" if fp != _cache["fp"] else "write-back or expired")
    t0 = time.perf_counter()
    value = compute(cur)
    ms = (time.perf_counter() - t0) * 1000
    with _lock:
        _cache.update(at=time.time(), value=value, ms=round(ms, 1), fp=fp)
        return value, {"computed": True, "reason": reason, "ms": round(ms, 1), "version": _cache["version"],
                       "ageSeconds": 0.0, "fingerprint": fp}
