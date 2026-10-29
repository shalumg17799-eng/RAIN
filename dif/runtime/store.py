"""State persistence + audit history (SQLite by default, PostgreSQL via DIF_DATABASE_URL).

Runs and artifacts are scoped by enterprise_id (null = platform-wide). Child runs carry parent_run_id. Large artifact
bodies can live in the object store (artifacts.uri); the row then keeps metadata plus a small body/summary."""
import json
import time
import uuid

from sqlalchemy import (Column, Float, Integer, MetaData, String, Table, Text, create_engine, insert, select, update)

md = MetaData()
runs = Table("runs", md,
             Column("id", String(36), primary_key=True), Column("agent", String(100)),
             Column("agent_version", String(20)), Column("created_by", String(100)),
             Column("status", String(20)), Column("input", Text), Column("state", Text),
             Column("output", Text), Column("error", Text),
             Column("created_at", Float), Column("updated_at", Float),
             Column("enterprise_id", String(50)), Column("parent_run_id", String(36)))
events = Table("events", md,
               Column("id", Integer, primary_key=True, autoincrement=True), Column("run_id", String(36)),
               Column("ts", Float), Column("event", String(50)), Column("detail", Text))
artifacts = Table("artifacts", md,
                  Column("id", Integer, primary_key=True, autoincrement=True), Column("run_id", String(36)),
                  Column("kind", String(50)), Column("version", Integer), Column("body", Text),
                  Column("created_at", Float), Column("enterprise_id", String(50)), Column("uri", Text))
agent_defs = Table("agent_defs", md,
                   Column("id", Integer, primary_key=True, autoincrement=True), Column("name", String(100)),
                   Column("version", String(20)), Column("enabled", Integer), Column("config", Text),
                   Column("created_by", String(100)), Column("created_at", Float), Column("enterprise_id", String(50)))

RUN_SUMMARY = (runs.c.id, runs.c.agent, runs.c.agent_version, runs.c.status, runs.c.created_by, runs.c.created_at,
               runs.c.updated_at, runs.c.enterprise_id, runs.c.parent_run_id)


class Store:
    def __init__(self, url: str):
        kw = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, **kw)
        if url.startswith("sqlite"):
            md.create_all(self.engine)  # zero-setup dev/test; shared databases are managed by `python -m dif.migrate`

    # ---- runs ------------------------------------------------------------------------------------
    def create_run(self, agent, inp, version=None, created_by=None, enterprise_id=None, parent_run_id=None):
        rid, now = str(uuid.uuid4()), time.time()
        with self.engine.begin() as c:
            c.execute(insert(runs).values(id=rid, agent=agent, agent_version=version, created_by=created_by, status="pending",
                                          input=json.dumps(inp), state="{}", created_at=now, updated_at=now,
                                          enterprise_id=enterprise_id, parent_run_id=parent_run_id))
        return rid

    def update_run(self, rid, **f):
        for k in ("input", "state", "output"):
            if k in f:
                f[k] = json.dumps(f[k])
        f.setdefault("updated_at", time.time())
        with self.engine.begin() as c:
            c.execute(update(runs).where(runs.c.id == rid).values(**f))

    def _decode(self, r):
        d = dict(r)
        for k in ("input", "state", "output"):
            if k in d:
                d[k] = json.loads(d[k]) if d[k] else None
        return d

    def get_run(self, rid, enterprise=None):
        with self.engine.connect() as c:
            r = c.execute(select(runs).where(runs.c.id == rid)).mappings().first()
        if not r or (enterprise is not None and r["enterprise_id"] != enterprise):
            return None
        return self._decode(r)

    def list_runs(self, limit=50, status=None, agent=None, enterprise=None, parent=None):
        q = select(*RUN_SUMMARY)
        if status:
            q = q.where(runs.c.status == status)
        if agent:
            q = q.where(runs.c.agent == agent)
        if enterprise is not None:
            q = q.where(runs.c.enterprise_id == enterprise)
        if parent is not None:
            q = q.where(runs.c.parent_run_id == parent)
        with self.engine.connect() as c:
            rows = c.execute(q.order_by(runs.c.created_at.desc()).limit(limit)).mappings().all()
        return [dict(r) for r in rows]

    def _modify_state(self, rid, fn):
        """Read-modify-write of runs.state in one transaction (row lock on PostgreSQL). fn(state) -> result."""
        with self.engine.begin() as c:
            raw = c.execute(select(runs.c.state).where(runs.c.id == rid).with_for_update()).scalar()
            state = json.loads(raw) if raw else {}
            result = fn(state)
            c.execute(update(runs).where(runs.c.id == rid).values(state=json.dumps(state), updated_at=time.time()))
        return result

    def checkpoint_step(self, rid, sid, rec):
        """Atomic per-step checkpoint: safe when parallel steps of one run checkpoint concurrently."""
        return self._modify_state(rid, lambda st: st.setdefault("steps", {}).__setitem__(sid, rec))

    def set_state(self, rid, key, value):
        return self._modify_state(rid, lambda st: st.__setitem__(key, value))

    def pending_gate(self, rid):
        run = self.get_run(rid)
        for sid, rec in ((run or {}).get("state") or {}).get("steps", {}).items():
            if rec.get("gate") and rec.get("status") == "pending":
                return sid, rec
        return None

    def decide_gate(self, rid, decision, by, comment=None, data=None):
        """approved | rejected | resolved (a delegated gate whose child run finished). Returns the gate step id."""
        found = {}

        def fn(state):
            for sid, rec in state.get("steps", {}).items():
                if rec.get("gate") and rec.get("status") == "pending":
                    rec.update({"status": decision, "decided_by": by, "decided_at": time.time(), "comment": comment})
                    if decision == "approved":
                        rec["output"] = data if data is not None else rec.get("payload")
                    found["sid"] = sid
                    return
            raise LookupError("no pending approval gate on this run")
        self._modify_state(rid, fn)
        self.update_run(rid, status="rejected" if decision == "rejected" else "pending",
                        error=f"rejected by {by}: {comment or ''}".strip() if decision == "rejected" else None)
        return found["sid"]

    def cancel_run(self, rid):
        """pending/awaiting_approval -> cancelled immediately; running -> cancelling (engine stops at next step boundary)."""
        with self.engine.begin() as c:
            r = c.execute(select(runs.c.status).where(runs.c.id == rid)).first()
            if not r:
                return None
            new = {"pending": "cancelled", "awaiting_approval": "cancelled", "running": "cancelling"}.get(r[0])
            if new:
                c.execute(update(runs).where(runs.c.id == rid).values(status=new, updated_at=time.time()))
            return new or r[0]

    # ---- agent definitions -----------------------------------------------------------------------
    def add_agent_def(self, cfg, by, enterprise_id=None):
        with self.engine.begin() as c:
            c.execute(insert(agent_defs).values(name=cfg["name"], version=str(cfg["version"]), enabled=1,
                                                config=json.dumps(cfg), created_by=by, created_at=time.time(),
                                                enterprise_id=enterprise_id))

    def agent_defs(self):
        with self.engine.connect() as c:
            rows = c.execute(select(agent_defs).order_by(agent_defs.c.id)).mappings().all()
        return [{**dict(r), "config": json.loads(r["config"]), "enabled": bool(r["enabled"])} for r in rows]

    def set_agent_enabled(self, name, version, enabled):
        with self.engine.begin() as c:
            res = c.execute(update(agent_defs).where(agent_defs.c.name == name, agent_defs.c.version == version)
                            .values(enabled=int(enabled)))
        return res.rowcount > 0

    # ---- audit -----------------------------------------------------------------------------------
    def log(self, rid, event, detail=None):
        with self.engine.begin() as c:
            c.execute(insert(events).values(run_id=rid, ts=time.time(), event=event, detail=json.dumps(detail, default=str)))

    def history(self, rid):
        with self.engine.connect() as c:
            rows = c.execute(select(events).where(events.c.run_id == rid).order_by(events.c.id)).mappings().all()
        return [{**dict(r), "detail": json.loads(r["detail"]) if r["detail"] else None} for r in rows]

    # ---- artifacts -------------------------------------------------------------------------------
    def publish(self, rid, kind, body, uri=None):
        """Versioned artifact persistence; the version counter is per (enterprise, kind)."""
        run = self.get_run(rid) or {}
        ent = run.get("enterprise_id")
        with self.engine.begin() as c:
            q = select(artifacts.c.id).where(artifacts.c.kind == kind)
            q = q.where(artifacts.c.enterprise_id == ent) if ent is not None else q.where(artifacts.c.enterprise_id.is_(None))
            n = len(c.execute(q).all())
            c.execute(insert(artifacts).values(run_id=rid, kind=kind, version=n + 1, body=json.dumps(body, default=str),
                                               created_at=time.time(), enterprise_id=ent, uri=uri))
        return n + 1

    def _artifact_row(self, r, include_body=True):
        d = dict(r)
        if include_body:
            d["body"] = json.loads(d["body"]) if d["body"] else None
        else:
            d.pop("body", None)
        return d

    def artifacts(self, kind=None, enterprise=None, run_id=None, include_body=True, limit=200):
        q = select(artifacts).order_by(artifacts.c.id.desc()).limit(limit)
        if kind:
            q = q.where(artifacts.c.kind == kind)
        if enterprise is not None:
            q = q.where(artifacts.c.enterprise_id == enterprise)
        if run_id:
            q = q.where(artifacts.c.run_id == run_id)
        with self.engine.connect() as c:
            rows = c.execute(q).mappings().all()
        return [self._artifact_row(r, include_body) for r in rows]

    def get_artifact(self, aid, enterprise=None):
        with self.engine.connect() as c:
            r = c.execute(select(artifacts).where(artifacts.c.id == aid)).mappings().first()
        if not r or (enterprise is not None and r["enterprise_id"] != enterprise):
            return None
        return self._artifact_row(r)

    def latest_artifact(self, kind, enterprise=None):
        rows = self.artifacts(kind, enterprise, limit=1)
        return rows[0] if rows else None
