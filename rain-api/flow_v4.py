"""RAIN v0.4 write-back flow: the care team's actions change rows, and the next UI request shows it.

POST /api/v4/flow/<action> writes to rain_v4.synthetic and invalidates the computed UI context
(metrics_v4), so every persona sees the new state on its next GET /api/v4/ui/data:

  handoff   approve a hand-off (CEO's top-300 list, coding recapture, the CMO's BP campaign)
  contact   log a call outcome (left message, reached, declined, wrong number)
  book      book a member into an open slot: appointment + reminder plan + eligibility + task closed
  reply     a patient's reply to a reminder (C confirm, R change, T switch to a video visit; V is read as T)
  reading   a home blood pressure reading; under 140/90 it closes the member's CMS165 gap
  signoff   CIO / CMO sign-off of the candidate model; both release it
  note      a feedback note (logged)
  reset     undo every flow change, back to the generated morning

Each change is one row in synthetic.flow_event with what it did and how to undo it (the undo list
is replayed by /reset). Time is the data's own clock: the as-of date of the loaded data with the
current time of day, so "Today" in the UI stays the demo's today.
"""
from __future__ import annotations

import json
import logging
import os
import random
from datetime import datetime, timedelta
from typing import Any

import psycopg2
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import metrics_v4

router = APIRouter(tags=["flow-v4"])
log = logging.getLogger("rain.api.flow")


def _conn():
    return psycopg2.connect(host=os.getenv("PG_HOST", "127.0.0.1"), port=os.getenv("PG_PORT", "5432"),
                            dbname=os.getenv("PG_DB_V4", "rain_v4"), user=os.getenv("PG_USER", "rain_app"),
                            password=os.getenv("PG_PASSWORD", "rain_dev_pw"))


class _Tx:
    """One flow action: its cursor, its clock and its undo list."""

    def __init__(self, cur, flow: str, actor: str | None, patient_id: str | None):
        self.cur, self.flow, self.actor, self.patient_id = cur, flow, actor, patient_id
        self.undo: list[list[Any]] = []
        self.did: dict[str, Any] = {}
        if patient_id:
            cur.execute("SELECT 1 FROM synthetic.patient WHERE patient_id = %s", (patient_id,))
            if not cur.fetchone():
                raise HTTPException(404, f"member {patient_id} not found")
        cur.execute("SELECT max(last_refreshed)::date FROM synthetic.data_source")
        as_of = cur.fetchone()[0]
        t = datetime.now().time().replace(microsecond=0)
        self.now = datetime.combine(as_of, t)
        cur.execute("INSERT INTO synthetic.flow_event (flow, actor, patient_id, detail, created_at) VALUES (%s, %s, %s, '{}'::jsonb, %s) "
                    "RETURNING flow_event_id", (flow, actor, patient_id, self.now))
        self.id = cur.fetchone()[0]
        self.n = 0

    def new_id(self, prefix: str) -> str:
        self.n += 1
        return f"{prefix}F{self.id}-{self.n}"

    def one(self, sql, args=()):
        self.cur.execute(sql, args)
        r = self.cur.fetchone()
        if r is None:
            return None
        names = [d[0] for d in self.cur.description]
        return dict(zip(names, r))

    def all(self, sql, args=()):
        self.cur.execute(sql, args)
        names = [d[0] for d in self.cur.description]
        return [dict(zip(names, r)) for r in self.cur.fetchall()]

    def insert(self, table: str, row: dict, key: str):
        cols = list(row)
        self.cur.execute(f"INSERT INTO synthetic.{table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})", [row[c] for c in cols])
        self.undo.append([f"DELETE FROM synthetic.{table} WHERE {key} = %s", [row[key]]])

    def update(self, table: str, key: str, key_value, **changes):
        old = self.one(f"SELECT {', '.join(changes)} FROM synthetic.{table} WHERE {key} = %s", (key_value,))
        if old is None:
            raise HTTPException(404, f"{table} {key_value} not found")
        sets = ", ".join(f"{c} = %s" for c in changes)
        self.cur.execute(f"UPDATE synthetic.{table} SET {sets} WHERE {key} = %s", [*changes.values(), key_value])
        self.undo.append([f"UPDATE synthetic.{table} SET {sets} WHERE {key} = %s", [*[_j(old[c]) for c in changes], key_value]])

    def finish(self, **detail):
        self.did.update(detail)
        self.cur.execute("UPDATE synthetic.flow_event SET detail = %s WHERE flow_event_id = %s",
                         (json.dumps({"did": self.did, "undo": self.undo}, default=str), self.id))


def _j(v):
    return v.isoformat(sep=" ") if isinstance(v, datetime) else v


def _run(flow: str, actor: str | None, patient_id: str | None, fn) -> dict:
    with _conn() as conn, conn.cursor() as cur:
        tx = _Tx(cur, flow, actor, patient_id)
        result = fn(tx)
        tx.finish(**(result or {}))
    metrics_v4.invalidate()
    log.info("flow %s by %s patient=%s event=%s: %s", flow, actor, patient_id, tx.id, json.dumps(result, default=str)[:300])
    return {"ok": True, "flow": flow, "event": tx.id, "at": tx.now.isoformat(sep=" "), "result": result}


# ─── payloads ─────────────────────────────────────────────────────────────────────────────────────────────
class HandoffIn(BaseModel):
    handoffId: str
    approvedBy: str | None = None
    memberCount: int | None = None
    toBucket: str | None = None
    fromBucket: str | None = None


class ContactIn(BaseModel):
    memberId: str
    outcome: str = Field(description="Left message | Reached and booked | Reached and declined | Wrong number | Not contacted")
    by: str | None = None


class BookIn(BaseModel):
    memberId: str
    slotId: str
    by: str | None = None


class ReplyIn(BaseModel):
    memberId: str
    reply: str = Field(description="C (confirm), R (change), T (switch to a video visit; V is accepted as T)")


class ReadingIn(BaseModel):
    memberId: str
    systolic: int
    diastolic: int
    source: str = "home cuff"


class SignoffIn(BaseModel):
    who: str = Field(description="cio or cmo")
    name: str | None = None


class NoteIn(BaseModel):
    noteId: str
    by: str | None = None
    to: str | None = None
    text: str | None = None


# ─── actions ─────────────────────────────────────────────────────────────────────────────────────────────
HANDOFF_ALIAS = {"outreach300": "HO-TOP300", "coding73": "HO-CODING", "bp412": "HO-BP2026"}


@router.post("/handoff")
def handoff(body: HandoffIn):
    def fn(tx: _Tx):
        hid = HANDOFF_ALIAS.get(body.handoffId, body.handoffId)
        row = tx.one("SELECT * FROM synthetic.handoff WHERE handoff_id = %s", (hid,))
        if row:
            tx.update("handoff", "handoff_id", hid, status="approved", approved_by=body.approvedBy or row["approved_by"],
                      approved_at=tx.now)
            if hid == "HO-TOP300":     # the approved list becomes the care team's outreach tasks
                top = tx.all("""SELECT i.patient_id, i.score FROM synthetic.impactability_score i
                                WHERE i.model_version = 'v1.3' AND i.outreach_rank <= %s AND NOT EXISTS (
                                  SELECT 1 FROM synthetic.outreach_task t WHERE t.patient_id = i.patient_id AND t.campaign_id = 'TOP300')
                                ORDER BY i.outreach_rank""", (row["member_count"] or 300,))
                for r in top:
                    tx.insert("outreach_task", {"task_id": tx.new_id("TSK-"), "patient_id": r["patient_id"], "campaign_id": "TOP300",
                                                "task_type": "impactable_outreach", "priority_score": r["score"], "reason_summary": None,
                                                "assigned_to": "Care team", "status": "open", "created_at": tx.now, "closed_at": None,
                                                "last_attempt_at": None}, "task_id")
                tx.update("campaign", "campaign_id", "TOP300", status="active")
                return {"handoff": hid, "status": "approved", "tasksCreated": len(top)}
            return {"handoff": hid, "status": "approved"}
        tx.insert("handoff", {"handoff_id": hid, "campaign_id": None, "from_bucket": body.fromBucket, "to_bucket": body.toBucket,
                              "member_count": body.memberCount, "approved_by": body.approvedBy, "approved_at": tx.now,
                              "status": "approved"}, "handoff_id")
        return {"handoff": hid, "status": "approved", "created": True}
    return _run("handoff", body.approvedBy, None, fn)


OUTCOME_TASK = {"Left message": "left_message", "Reached and booked": "closed", "Reached and declined": "closed",
                "Wrong number": "open", "Not contacted": "open"}


@router.post("/contact")
def contact(body: ContactIn):
    if body.outcome not in OUTCOME_TASK:
        raise HTTPException(422, f"outcome must be one of {sorted(OUTCOME_TASK)}")

    def fn(tx: _Tx):
        cm = tx.one("SELECT campaign_member_id, outcome FROM synthetic.campaign_member WHERE patient_id = %s AND campaign_id = 'BP2026'",
                    (body.memberId,))
        if not cm:
            raise HTTPException(404, f"{body.memberId} is not in the BP campaign")
        if body.outcome != "Reached and booked":      # booking happens through /book
            tx.update("campaign_member", "campaign_member_id", cm["campaign_member_id"], outcome=body.outcome)
        task = tx.one("""SELECT task_id FROM synthetic.outreach_task WHERE patient_id = %s AND campaign_id = 'BP2026'
                         AND task_type = 'bp_campaign_call' ORDER BY created_at DESC LIMIT 1""", (body.memberId,))
        if task:
            closed = OUTCOME_TASK[body.outcome] == "closed"
            tx.update("outreach_task", "task_id", task["task_id"], status=OUTCOME_TASK[body.outcome], last_attempt_at=tx.now,
                      closed_at=tx.now if closed else None)
        handed = False
        if body.outcome == "Reached and booked" and cm["outcome"] != "Reached and booked":   # reached: booking goes to access
            open_book = tx.one("""SELECT task_id FROM synthetic.outreach_task WHERE patient_id = %s AND task_type = 'book_visit'
                                  AND status = 'open'""", (body.memberId,))
            if not open_book:
                mode = tx.one("SELECT recommended_visit_mode m FROM synthetic.campaign_member WHERE campaign_member_id = %s",
                              (cm["campaign_member_id"],))["m"]
                tx.insert("outreach_task", {"task_id": tx.new_id("TSK-"), "patient_id": body.memberId, "campaign_id": "BP2026",
                                            "task_type": "book_visit", "priority_score": None, "reason_summary": f"{mode} recheck",
                                            "assigned_to": "Brandon Kee", "status": "open", "created_at": tx.now, "closed_at": None,
                                            "last_attempt_at": None, "handed_off_by": body.by or "Teresa Lopez, CHW"}, "task_id")
                handed = True
        return {"member": body.memberId, "outcome": body.outcome, "handedToAccess": handed}
    return _run("contact", body.by, body.memberId, fn)


def _plan(tx: _Tx, patient_id: str, drive: float, start: datetime, tele: bool):
    hist = tx.one("SELECT no_show_count FROM synthetic.no_show_rate WHERE patient_id = %s", (patient_id,)) or {"no_show_count": 0}
    ns = hist["no_show_count"] or 0
    risk = round(min(0.95, 0.06 + 0.15 * ns + 0.002 * max(0, (drive or 0) - 30)), 3)
    offsets = [72, 24, 3] if risk >= 0.35 or (drive or 0) > 60 else [24, 3]
    return risk, [o for o in offsets if start - timedelta(hours=o) > tx.now] or [3]


@router.post("/book")
def book(body: BookIn):
    def fn(tx: _Tx):
        slot = tx.one("""SELECT s.slot_id, s.slot_start, s.status, s.telehealth_flag, sc.provider_id, sc.clinic_site_id, sc.service_category
                         FROM synthetic.slot s JOIN synthetic.schedule sc ON sc.schedule_id = s.schedule_id WHERE s.slot_id = %s""",
                      (body.slotId,))
        if not slot:
            raise HTTPException(404, f"slot {body.slotId} not found")
        if slot["status"] != "open":
            mine = tx.one("""SELECT appointment_id FROM synthetic.appointment WHERE slot_id = %s AND patient_id = %s
                             AND status IN ('booked', 'confirmed')""", (body.slotId, body.memberId))
            if mine:      # already this member's visit: nothing to change
                return {"appointment": mine["appointment_id"], "slot": body.slotId, "alreadyBooked": True}
            raise HTTPException(409, f"slot {body.slotId} is {slot['status']}")
        pat = tx.one("""SELECT p.patient_id, p.language, p.home_site_id,
                               (SELECT t.drive_minutes FROM synthetic.travel_time t WHERE t.patient_id = p.patient_id
                                  AND t.clinic_site_id = p.home_site_id LIMIT 1) drive
                        FROM synthetic.patient p WHERE p.patient_id = %s""", (body.memberId,))
        if not pat:
            raise HTTPException(404, f"member {body.memberId} not found")
        in_bp = tx.one("SELECT campaign_member_id FROM synthetic.campaign_member WHERE patient_id = %s AND campaign_id = 'BP2026'",
                       (body.memberId,))
        # a member holds one upcoming BP recheck: an earlier booking is released
        for old in tx.all("""SELECT a.appointment_id, a.slot_id FROM synthetic.appointment a JOIN synthetic.slot s ON s.slot_id = a.slot_id
                             WHERE a.patient_id = %s AND a.status = 'booked' AND a.visit_type = 'BP recheck' AND s.slot_start > %s""",
                          (body.memberId, tx.now)):
            tx.update("appointment", "appointment_id", old["appointment_id"], status="cancelled")
            tx.update("slot", "slot_id", old["slot_id"], status="open")
        tele = bool(slot["telehealth_flag"])
        mode = "telehealth" if tele else ("mobile clinic" if slot["service_category"] == "mobile clinic" else "in person")
        risk, offsets = _plan(tx, body.memberId, float(pat["drive"] or 0), slot["slot_start"], tele)
        aid = tx.new_id("APT-")
        tx.insert("appointment", {"appointment_id": aid, "slot_id": slot["slot_id"], "patient_id": body.memberId,
                                  "provider_id": slot["provider_id"], "visit_mode": mode, "status": "booked", "booked_via": body.by or "front desk",
                                  "booked_at": tx.now, "no_show_risk": risk, "visit_type": "BP recheck" if in_bp else "Primary care",
                                  "visit_link": f"sierrabasin.example/v/{random.Random(aid).randint(1000, 9999)}" if tele else None}, "appointment_id")
        tx.update("slot", "slot_id", slot["slot_id"], status="booked")
        channel = tx.one("""SELECT CASE WHEN consent_flag THEN 'SMS' ELSE 'Voice' END c FROM synthetic.contact_preference
                            WHERE patient_id = %s ORDER BY preference_id LIMIT 1""", (body.memberId,))
        for off in offsets:
            tx.insert("reminder_message", {"message_id": tx.new_id("MSG-"), "appointment_id": aid, "patient_id": body.memberId,
                                           "channel": (channel or {}).get("c", "SMS"), "language": pat["language"],
                                           "template": "reminder_offer_telehealth" if off == 24 and not tele and risk >= 0.35 else "reminder",
                                           "offset_hours": off, "sent_at": None, "delivery_status": "scheduled", "reply": None,
                                           "replied_at": None, "scheduled_for": slot["slot_start"] - timedelta(hours=off)}, "message_id")
        tx.insert("reminder_message", {"message_id": tx.new_id("MSG-"), "appointment_id": aid, "patient_id": body.memberId,
                                       "channel": (channel or {}).get("c", "SMS"), "language": pat["language"], "template": "booking_confirmation",
                                       "offset_hours": None, "sent_at": tx.now, "delivery_status": "delivered", "reply": None,
                                       "replied_at": None, "scheduled_for": tx.now}, "message_id")
        cov = tx.one("""SELECT payer, coverage_status, response_code FROM synthetic.eligibility_check WHERE patient_id = %s
                        ORDER BY checked_at DESC NULLS LAST LIMIT 1""", (body.memberId,))
        tx.insert("eligibility_check", {"check_id": tx.new_id("ELG-"), "patient_id": body.memberId, "appointment_id": aid,
                                        "payer": (cov or {}).get("payer") or "High Desert Health Plan",
                                        "coverage_status": (cov or {}).get("coverage_status") or "active",
                                        "response_code": (cov or {}).get("response_code") or "1", "checked_at": tx.now}, "check_id")
        for t in tx.all("""SELECT task_id FROM synthetic.outreach_task WHERE patient_id = %s AND status <> 'closed'
                           AND task_type IN ('book_visit', 'bp_campaign_call')""", (body.memberId,)):
            tx.update("outreach_task", "task_id", t["task_id"], status="closed", closed_at=tx.now, last_attempt_at=tx.now)
        if in_bp:
            tx.update("campaign_member", "campaign_member_id", in_bp["campaign_member_id"], outcome="Reached and booked", booked_flag=True)
        return {"appointment": aid, "slot": slot["slot_id"], "start": slot["slot_start"].isoformat(sep=" "), "mode": mode,
                "noShowRisk": risk, "reminders": offsets, "coverage": (cov or {}).get("coverage_status") or "active"}
    return _run("book", body.by, body.memberId, fn)


@router.post("/reply")
def reply(body: ReplyIn):
    r = body.reply.strip().upper()[:1]
    r = "T" if r == "V" else r
    if r not in ("C", "R", "T"):
        raise HTTPException(422, "reply must be C, R or T")

    def fn(tx: _Tx):
        appt = tx.one("""SELECT a.appointment_id, a.status, a.visit_mode FROM synthetic.appointment a JOIN synthetic.slot s ON s.slot_id = a.slot_id
                         WHERE a.patient_id = %s AND a.status IN ('booked', 'confirmed') AND s.slot_start > %s ORDER BY s.slot_start LIMIT 1""",
                      (body.memberId, tx.now))
        if not appt:
            raise HTTPException(404, f"{body.memberId} has no upcoming visit")
        msg = tx.one("""SELECT message_id FROM synthetic.reminder_message WHERE appointment_id = %s AND sent_at IS NOT NULL
                        ORDER BY sent_at DESC LIMIT 1""", (appt["appointment_id"],))
        if not msg:      # the patient answers the first reminder: it counts as sent now
            msg = tx.one("""SELECT message_id FROM synthetic.reminder_message WHERE appointment_id = %s
                            ORDER BY scheduled_for LIMIT 1""", (appt["appointment_id"],))
            tx.update("reminder_message", "message_id", msg["message_id"], sent_at=tx.now, delivery_status="delivered")
        tx.update("reminder_message", "message_id", msg["message_id"], reply=r, replied_at=tx.now)
        if r == "C":
            tx.update("appointment", "appointment_id", appt["appointment_id"], status="confirmed")
        elif r == "T":
            tx.update("appointment", "appointment_id", appt["appointment_id"], visit_mode="telehealth")
        return {"appointment": appt["appointment_id"], "reply": r}
    return _run("reply", body.memberId, body.memberId, fn)


@router.post("/reading")
def reading(body: ReadingIn):
    if not (60 <= body.systolic <= 260 and 30 <= body.diastolic <= 160):
        raise HTTPException(422, "reading out of range")

    def fn(tx: _Tx):
        if not tx.one("SELECT 1 x FROM synthetic.patient WHERE patient_id = %s", (body.memberId,)):
            raise HTTPException(404, f"member {body.memberId} not found")
        rid = tx.new_id("RBP-")
        tx.insert("remote_bp_reading", {"reading_id": rid, "patient_id": body.memberId, "value_systolic": body.systolic,
                                        "value_diastolic": body.diastolic, "reading_time": tx.now, "device_type": body.source,
                                        "counts_for_measure": True}, "reading_id")
        tx.insert("observation", {"observation_id": tx.new_id("OBS-"), "patient_id": body.memberId, "encounter_id": None,
                                  "loinc_code": "85354-9", "observation_type": "blood pressure", "value_numeric": None,
                                  "value_systolic": body.systolic, "value_diastolic": body.diastolic, "unit": "mm[Hg]",
                                  "observed_at": tx.now}, "observation_id")
        controlled = body.systolic < 140 and body.diastolic < 90
        closed = []
        if controlled:
            for g in tx.all("SELECT care_gap_id FROM synthetic.care_gap WHERE patient_id = %s AND measure_code = 'CMS165' AND status = 'open'",
                            (body.memberId,)):
                tx.update("care_gap", "care_gap_id", g["care_gap_id"], status="closed", closed_at=tx.now, closed_by="reading")
                closed.append(g["care_gap_id"])
        return {"reading": rid, "bp": f"{body.systolic}/{body.diastolic}", "controlled": controlled, "gapsClosed": closed}
    return _run("reading", body.memberId, body.memberId, fn)


@router.post("/signoff")
def signoff(body: SignoffIn):
    who = body.who.lower()
    if who not in ("cio", "cmo"):
        raise HTTPException(422, "who must be cio or cmo")

    def fn(tx: _Tx):
        cand = tx.one("SELECT * FROM synthetic.model_card WHERE release_status <> 'released' AND release_status <> 'retired' "
                      "ORDER BY model_version DESC LIMIT 1")
        if not cand:
            raise HTTPException(409, "no candidate model to sign off")
        name = body.name or ("Raj Malhotra" if who == "cio" else "Dr. Naomi Castellanos")
        col = "signed_off_by" if who == "cio" else "cosigned_by"
        tx.update("model_card", "model_version", cand["model_version"], **{col: name})
        other = cand["cosigned_by"] if who == "cio" else cand["signed_off_by"]
        released = bool(other)
        if released:
            for r in tx.all("SELECT model_version FROM synthetic.model_card WHERE release_status = 'released'"):
                tx.update("model_card", "model_version", r["model_version"], release_status="retired")
            tx.update("model_card", "model_version", cand["model_version"], release_status="released", released_at=tx.now)
        return {"model": cand["model_version"], "signedBy": name, "released": released}
    return _run("signoff", body.name or body.who, None, fn)


@router.post("/note")
def note(body: NoteIn):
    return _run("note", body.by, None, lambda tx: {"note": body.noteId, "to": body.to, "text": body.text})


@router.get("/events")
def events(limit: int = 50):
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT flow_event_id, flow, actor, patient_id, detail -> 'did', created_at FROM synthetic.flow_event "
                    "ORDER BY flow_event_id DESC LIMIT %s", (min(limit, 500),))
        return [{"id": r[0], "flow": r[1], "actor": r[2], "patientId": r[3], "did": r[4], "at": r[5].isoformat(sep=" ")} for r in cur.fetchall()]


@router.post("/reset")
def reset():
    """Undo every flow change in reverse order: the data is back to what the generator wrote."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT flow_event_id, detail FROM synthetic.flow_event ORDER BY flow_event_id DESC")
        events_ = cur.fetchall()
        steps = 0
        for _, detail in events_:
            for sql, args in reversed((detail or {}).get("undo", [])):
                cur.execute(sql, args)
                steps += 1
        cur.execute("DELETE FROM synthetic.flow_event")
    metrics_v4.invalidate()
    log.info("flow reset: %d events, %d undo steps", len(events_), steps)
    return {"ok": True, "eventsUndone": len(events_), "steps": steps}
