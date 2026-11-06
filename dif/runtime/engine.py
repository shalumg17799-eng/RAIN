"""Agent runtime on LangGraph.

An agent (YAML, versioned, registered at runtime) is compiled into a LangGraph StateGraph: one node per step, each
invoking a registered skill, running a sub-agent as a child run, fanning out a parallel group, or pausing at an
approval gate. Every step is checkpointed to the run store, so a run can be resumed after a crash (completed steps are
skipped), paused for a human decision, cancelled between steps, and audited. Steps are traced with OpenTelemetry.

Step input values like "$.input.x" / "$.steps.<id>.output.x" are resolved from run state at execution time.
Execution is executor-independent: the local executor runs `Runtime.execute` on a thread pool, the Temporal executor
runs it inside a durable workflow activity (see dif/runtime/temporal)."""
import logging
import threading
import time
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from dif import telemetry
from dif.config import settings
from dif.runtime.acceptance import check_acceptance
from dif.runtime.agents import AgentError, AgentRegistry  # noqa: F401  (re-exported)
from dif.runtime.metrics import ACTIVE, RUNS, STEP_ERRORS, STEP_RETRIES, STEP_SECONDS
from dif.runtime.policy import policy_from_step, run_with_policy
from dif.runtime.store import Store
from dif.skills.registry import SkillRegistry

log = logging.getLogger("dif.runtime")
RESUMABLE = {"failed", "cancelled"}
TERMINAL = {"succeeded", "failed", "cancelled", "rejected"}
MAX_AGENT_DEPTH = 4  # agent -> sub-agent -> ... ; guards against agents that (indirectly) call each other
_ctx = threading.local()  # _ctx.parent_call: the child is being executed inside its parent's step (no wake needed)


class Cancelled(Exception):
    retryable = False


class Paused(Exception):
    """Raised by an approval gate (or a sub-agent step whose child paused): the run waits for a human decision."""
    retryable = False

    def __init__(self, step_id):
        super().__init__(f"awaiting approval at step '{step_id}'")
        self.step_id = step_id


class AcceptanceFailed(Exception):
    retryable = False


def _merge(a: dict, b: dict) -> dict:
    return {**a, **b}


class RunState(TypedDict):
    input: dict
    steps: Annotated[dict, _merge]


def resolve(value, input_, steps):
    if isinstance(value, dict):
        return {k: resolve(v, input_, steps) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, input_, steps) for v in value]
    if isinstance(value, str) and value.startswith("$."):
        cur = {"input": input_, "steps": steps}
        for p in value[2:].split("."):
            cur = cur.get(p) if isinstance(cur, dict) else None
        return cur
    return value


def _done(rec) -> bool:
    """A checkpointed step is complete when it produced an output (succeeded, skipped, or an approved gate)."""
    return rec is not None and "output" in rec and not rec.get("failed")


class Runtime:
    def __init__(self, store: Store, skills: SkillRegistry, agents: AgentRegistry, executor=None, artifacts=None,
                 contracts_dir=None):
        self.store, self.skills, self.agents, self.executor = store, skills, agents, executor
        self.artifacts = artifacts
        self.contracts_dir = contracts_dir or settings.contracts_dir
        self.progress = None  # optional callable(run_id, step_id): executor progress hook (Temporal heartbeat)
        if executor is not None:
            executor.bind(self)

    # ---- lifecycle -------------------------------------------------------------------------------
    def create(self, agent, input_, dry_run=False, by=None, version=None, enterprise=None, parent=None) -> str:
        cfg = self.agents.get(agent, version)  # raises if unknown/disabled; pins the version used
        rid = self.store.create_run(agent, {**input_, "__dry_run": True} if dry_run else input_,
                                    str(cfg["version"]), by, enterprise, parent)
        self.store.log(rid, "created", {"agent": agent, "version": str(cfg["version"]), "dry_run": dry_run, "by": by,
                                        "enterprise": enterprise, "parent": parent})
        return rid

    def submit(self, agent, input_, dry_run=False, by=None, version=None, enterprise=None) -> dict:
        """Async: hand the run to the executor and return immediately (status=pending)."""
        rid = self.create(agent, input_, dry_run, by, version, enterprise)
        self.executor.submit(rid)
        self.store.log(rid, "queued", {"executor": self.executor.kind})
        return self.store.get_run(rid)

    def start(self, agent, input_, dry_run=False, by=None, version=None, enterprise=None) -> dict:
        """Sync: execute in the caller's thread (used by wait=true, evaluation and tests)."""
        return self.execute(self.create(agent, input_, dry_run, by, version, enterprise))

    def resume(self, rid, wait=True) -> dict:
        run = self.store.get_run(rid)
        if not run:
            raise AgentError("unknown run")
        if run["status"] == "awaiting_approval":
            raise AgentError("run is awaiting approval; use /approve or /reject")
        stale = run["status"] == "running" and time.time() - run["updated_at"] > settings.stale_seconds
        if run["status"] not in RESUMABLE and not stale:
            raise AgentError(f"run is {run['status']}; only failed/cancelled/stale runs can be resumed")
        self.store.update_run(rid, status="pending", error=None)
        self.store.log(rid, "resumed")
        return self._continue(rid, wait)

    def approve(self, rid, by, comment=None, data=None, wait=False) -> dict:
        run = self.store.get_run(rid)
        if not run:
            raise AgentError("unknown run")
        if run["status"] != "awaiting_approval":
            raise AgentError(f"run is {run['status']}, not awaiting approval")
        sid, rec = self.store.pending_gate(rid)
        if rec.get("delegated"):  # the gate belongs to a child run: decide there, the child wakes this run
            return self.approve(rec["child_run"], by, comment, data, wait)
        self.store.decide_gate(rid, "approved", by, comment, data)
        self.store.log(rid, "approved", {"step": sid, "by": by, "comment": comment})
        return self._continue(rid, wait)

    def reject(self, rid, by, comment=None) -> dict:
        run = self.store.get_run(rid)
        if not run:
            raise AgentError("unknown run")
        if run["status"] != "awaiting_approval":
            raise AgentError(f"run is {run['status']}, not awaiting approval")
        sid, rec = self.store.pending_gate(rid)
        if rec.get("delegated"):
            return self.reject(rec["child_run"], by, comment)
        self.store.decide_gate(rid, "rejected", by, comment)
        self.store.log(rid, "rejected", {"step": sid, "by": by, "comment": comment})
        RUNS.labels(run["agent"], "rejected").inc()
        if self.executor is not None:
            self.executor.notify(rid)  # a durable workflow parked on the gate observes the rejection and ends
        run = self.store.get_run(rid)
        self._wake_parent(run)
        return run

    def _continue(self, rid, wait):
        if wait or self.executor is None:
            return self.execute(rid)
        self.executor.resume(rid)
        return self.store.get_run(rid)

    def recover_orphans(self) -> int:
        """Local (single-process) executor only: threads die with the process, so re-enqueue unfinished runs at
        startup. Child runs are re-run by their parent, so only top-level runs are re-enqueued."""
        found = {}  # collect first: enqueueing flips a run to "running", so listing while enqueueing would count it twice
        for st in ("pending", "running"):
            for r in self.store.list_runs(1000, status=st):
                if not r.get("parent_run_id"):
                    found.setdefault(r["id"], st)
        for rid, st in found.items():
            self.executor.submit(rid)
            self.store.log(rid, "recovered", {"from": st})
        return len(found)

    def cancel(self, rid) -> str:
        run = self.store.get_run(rid)
        if not run:
            raise AgentError("unknown run")
        status = self.store.cancel_run(rid)
        self.store.log(rid, "cancel_requested", {"status": status})
        if status == "cancelled":
            if run["status"] == "awaiting_approval":
                RUNS.labels(run["agent"], "cancelled").inc()
            if self.executor is not None:
                self.executor.notify(rid)
            self._wake_parent(self.store.get_run(rid))
        return status

    # ---- execution -------------------------------------------------------------------------------
    def _checkpoint(self, rid, sid, rec):
        self.store.checkpoint_step(rid, sid, rec)
        if self.progress:
            try:
                self.progress(rid, sid)
            except Exception:  # progress reporting must never break a run
                log.debug("progress hook failed", exc_info=True)

    def _check_cancel(self, rid):
        if (self.store.get_run(rid) or {}).get("status") == "cancelling":
            raise Cancelled()

    def _run_child(self, rid, step, data, dry, depth, enterprise, existing):
        """Orchestrator step: run another agent as a linked child run (own audit trail, same worker)."""
        sid = step["id"]
        crid = (existing or {}).get("child_run")
        child = self.store.get_run(crid) if crid else None
        if child and child["status"] == "succeeded":  # resumed parent: adopt the finished child
            return crid, child["output"]
        if child and child["status"] == "awaiting_approval":
            raise Paused(sid)
        if child and child["status"] in ("pending", "running"):
            pass  # resumed parent: finish the child in-process below
        elif child and not (existing or {}).get("failed"):  # child was rejected/failed/cancelled on its own
            raise AgentError(f"sub-agent '{step['agent']}' (run {crid}) {child['status']}: {child.get('error')}")
        else:  # first execution, or retry after the parent step was marked failed
            if depth + 1 > MAX_AGENT_DEPTH:
                raise AgentError(f"sub-agent depth limit ({MAX_AGENT_DEPTH}) exceeded; check for agents calling each other")
            parent = self.store.get_run(rid) or {}
            crid = self.create(step["agent"], {**data, "__depth": depth + 1}, dry, parent.get("created_by"),
                               step.get("version"), enterprise, parent=rid)
            self._checkpoint(rid, sid, {"agent": step["agent"], "child_run": crid, "status": "pending"})
            self.store.log(rid, "sub_agent_started", {"step": sid, "agent": step["agent"], "child_run": crid})
        prev, _ctx.parent_call = getattr(_ctx, "parent_call", False), True
        try:
            child = self.execute(crid)
        finally:
            _ctx.parent_call = prev
        if child["status"] == "succeeded":
            return crid, child["output"]
        if child["status"] == "awaiting_approval":
            gate = self.store.pending_gate(crid)
            self._checkpoint(rid, sid, {"agent": step["agent"], "child_run": crid, "gate": True, "delegated": True,
                                        "status": "pending", "title": (gate[1].get("title") if gate else None),
                                        "payload": (gate[1].get("payload") if gate else None)})
            raise Paused(sid)
        raise AgentError(f"sub-agent '{step['agent']}' (run {crid}) {child['status']}: {child.get('error')}")

    def _skip(self, step, state, enterprise):
        if "enterprises" in step and enterprise not in step["enterprises"]:
            return True
        if "when" in step and not resolve(step["when"], state["input"], state["steps"]):
            return True
        return "unless" in step and bool(resolve(step["unless"], state["input"], state["steps"]))

    def _build_graph(self, rid, cfg, dry, depth=0, enterprise=None):
        defaults = cfg.get("defaults", {})

        def make_node(step, collect=False):
            sid = step["id"]

            def node(state: RunState):
                rec = state["steps"].get(sid)
                if _done(rec):  # checkpointed earlier -> skip on resume
                    return {}
                self._check_cancel(rid)
                if self._skip(step, state, enterprise):
                    rec = {"output": None, "skipped": True, "skill": step.get("skill"), "agent": step.get("agent")}
                    self._checkpoint(rid, sid, rec)
                    self.store.log(rid, "step_skipped", {"step": sid})
                    return {"steps": {sid: rec}}
                if step.get("approval"):
                    if rec and rec.get("status") == "rejected":
                        raise AgentError(f"step '{sid}' was rejected: {rec.get('comment')}")
                    a = step["approval"]
                    rec = {"gate": True, "status": "pending", "title": a.get("title", sid),
                           "payload": resolve(a.get("payload", {}), state["input"], state["steps"]),
                           "roles": a.get("roles", ["approver", "admin"]), "requested_at": time.time()}
                    self._checkpoint(rid, sid, rec)
                    self.store.log(rid, "approval_requested", {"step": sid, "title": rec["title"]})
                    raise Paused(sid)
                data = resolve(step.get("input", {}), state["input"], state["steps"])
                policy = policy_from_step(step, defaults)
                attempts = {"n": 1}

                def on_retry(attempt, exc, wait):
                    attempts["n"] = attempt + 1
                    STEP_RETRIES.labels(step.get("skill") or step.get("agent")).inc()
                    self.store.log(rid, "step_retry", {"step": sid, "attempt": attempt, "error": str(exc), "sleep": wait})

                t0 = time.time()
                try:
                    with telemetry.tracer.start_as_current_span(f"step:{sid}") as span:
                        span.set_attribute("dif.run_id", rid)
                        if step.get("agent"):
                            span.set_attribute("dif.sub_agent", step["agent"])
                            child_id, out = run_with_policy(
                                policy, lambda: self._run_child(rid, step, data, dry, depth, enterprise, rec), on_retry,
                                lambda: (self.store.get_run(rid) or {}).get("status") == "cancelling")
                            rec = {"output": out, "agent": step["agent"], "child_run": child_id}
                        else:
                            skill = self.skills.get(step["skill"], step.get("version"), enterprise)
                            span.set_attribute("dif.skill", skill.name)
                            self.store.log(rid, "step_started", {"step": sid, "skill": skill.name, "version": skill.version,
                                                                 "enterprise_override": skill.enterprise})
                            ctx = {"run_id": rid, "dry_run": dry, "enterprise": enterprise, "artifacts": self.artifacts,
                                   "registry": {"skills": self.skills, "agents": self.agents},
                                   "store": self.store, "step": sid}
                            with STEP_SECONDS.labels(skill.name).time():
                                out = run_with_policy(policy, lambda: skill.execute(data, ctx), on_retry,
                                                      lambda: (self.store.get_run(rid) or {}).get("status") == "cancelling")
                            rec = {"output": out, "skill": skill.name, "version": skill.version}
                except (Cancelled, Paused):
                    raise
                except Exception as e:
                    STEP_ERRORS.labels(step.get("skill") or step.get("agent") or sid).inc()
                    failed = {"failed": True, "error": str(e), "skill": step.get("skill"), "agent": step.get("agent"),
                              "child_run": (rec or {}).get("child_run"), "attempts": attempts["n"]}
                    self._checkpoint(rid, sid, failed)
                    self.store.log(rid, "step_failed", {"step": sid, "error": str(e), "attempts": attempts["n"]})
                    if collect:  # parallel group with on_error=collect: record and let siblings finish
                        return {"steps": {sid: failed}}
                    raise AgentError(f"step '{sid}' failed: {e}") from e
                rec.update({"seconds": round(time.time() - t0, 4), "attempts": attempts["n"]})
                self._checkpoint(rid, sid, rec)
                self.store.log(rid, "step_succeeded", {"step": sid, "seconds": rec["seconds"],
                                                       **({"child_run": rec["child_run"]} if "child_run" in rec else {})})
                return {"steps": {sid: rec}}

            return node

        def make_fanout(group):
            def fanout(state: RunState):
                if not _done(state["steps"].get(group["id"])):
                    self._check_cancel(rid)
                    self.store.log(rid, "group_started", {"group": group["id"], "members": [m["id"] for m in group["parallel"]]})
                return {}
            return fanout

        def make_join(group):
            gid, members = group["id"], [m["id"] for m in group["parallel"]]

            def join(state: RunState):
                if _done(state["steps"].get(gid)):
                    return {}
                steps = state["steps"]
                failed = [m for m in members if (steps.get(m) or {}).get("failed")]
                if failed and group.get("on_error", "fail_fast") == "fail_fast":
                    raise AgentError(f"group '{gid}' failed: " + "; ".join(f"{m}: {steps[m].get('error')}" for m in failed))
                rec = {"group": True, "members": members, "failed": failed,
                       "output": {m: (steps.get(m) or {}).get("output") for m in members}}
                self._checkpoint(rid, gid, rec)
                self.store.log(rid, "group_joined", {"group": gid, "failed": failed})
                return {"steps": {gid: rec}}
            return join

        g = StateGraph(RunState)
        prev = START
        for st in cfg["steps"]:
            if st.get("parallel"):
                gid, fan = st["id"], f"{st['id']}__fanout"
                collect = st.get("on_error", "fail_fast") == "collect"
                g.add_node(fan, make_fanout(st))
                g.add_edge(prev, fan)
                for m in st["parallel"]:
                    g.add_node(m["id"], make_node(m, collect))
                    g.add_edge(fan, m["id"])
                g.add_node(gid, make_join(st))
                g.add_edge([m["id"] for m in st["parallel"]], gid)  # join waits for every member
                prev = gid
            else:
                g.add_node(st["id"], make_node(st))
                g.add_edge(prev, st["id"])
                prev = st["id"]
        g.add_edge(prev, END)
        return g.compile()

    def execute(self, rid: str) -> dict:
        run = self.store.get_run(rid)
        if not run or run["status"] in TERMINAL - {"failed"} or run["status"] == "awaiting_approval":
            return run  # nothing to do: finished, or waiting for a decision (approve/reject re-enqueue it)
        if run["status"] == "failed":
            return run  # a failed run is only re-executed through resume(), which flips it to pending first
        cfg = self.agents.get(run["agent"], run["agent_version"])
        input_ = dict(run["input"])
        dry = bool(input_.pop("__dry_run", False))
        depth = int(input_.pop("__depth", 0))
        input_.pop("__parent", None)
        enterprise = run.get("enterprise_id")
        done = (run["state"] or {}).get("steps", {})
        self.store.update_run(rid, status="running")
        ACTIVE.inc()
        try:
            with telemetry.tracer.start_as_current_span(f"run:{cfg['name']}") as span:
                span.set_attribute("dif.run_id", rid)
                span.set_attribute("dif.agent_version", str(cfg["version"]))
                final = self._build_graph(rid, cfg, dry, depth, enterprise).invoke({"input": input_, "steps": done})
                steps = final["steps"]
                output = resolve(cfg.get("output", {}), input_, steps)
                published = []
                body = resolve(cfg["persist"]["from"], input_, steps) if cfg.get("persist") else None
                if body is not None and not dry:  # a skipped producing step yields nothing to persist
                    v = self.store.publish(rid, cfg["persist"]["kind"], body)
                    output["artifact_version"] = v
                    published.append(cfg["persist"]["kind"])
                    self.store.log(rid, "persisted", {"kind": cfg["persist"]["kind"], "version": v})
                if cfg.get("acceptance"):
                    report = check_acceptance(cfg["acceptance"], output, published, input_, steps, self.contracts_dir, dry)
                    self.store.set_state(rid, "acceptance", report)
                    self.store.log(rid, "acceptance_passed" if report["passed"] else "acceptance_failed",
                                   {"checks": [c["name"] for c in report["checks"] if not c["passed"]] or "all"})
                    if not report["passed"]:
                        self.store.update_run(rid, output=output)
                        raise AcceptanceFailed("acceptance failed: " + ", ".join(c["name"] for c in report["checks"] if not c["passed"]))
            self.store.update_run(rid, status="succeeded", output=output)
            self.store.log(rid, "succeeded")
            RUNS.labels(cfg["name"], "succeeded").inc()
        except Paused as p:
            self.store.update_run(rid, status="awaiting_approval")
            self.store.log(rid, "paused", {"step": p.step_id})
            RUNS.labels(cfg["name"], "awaiting_approval").inc()
        except Cancelled:
            self.store.update_run(rid, status="cancelled")
            self.store.log(rid, "cancelled")
            RUNS.labels(cfg["name"], "cancelled").inc()
        except Exception as e:
            if not isinstance(e, AcceptanceFailed):
                log.exception("run %s failed", rid)
            self.store.update_run(rid, status="failed", error=str(e))
            self.store.log(rid, "failed", {"error": str(e)})
            RUNS.labels(cfg["name"], "failed").inc()
        finally:
            ACTIVE.dec()
        run = self.store.get_run(rid)
        if not getattr(_ctx, "parent_call", False):
            self._wake_parent(run)
        return run

    def _wake_parent(self, run):
        """A child run that finished on its own (after its gate was decided) re-enqueues the parent waiting on it."""
        if not run or not run.get("parent_run_id") or run["status"] not in TERMINAL:
            return
        parent = self.store.get_run(run["parent_run_id"])
        if not parent or parent["status"] != "awaiting_approval":
            return
        gate = self.store.pending_gate(parent["id"])
        if not gate or not gate[1].get("delegated") or gate[1].get("child_run") != run["id"]:
            return
        self.store.decide_gate(parent["id"], "resolved", f"child:{run['id']}", run["status"])
        self.store.log(parent["id"], "child_resolved", {"step": gate[0], "child_run": run["id"], "status": run["status"]})
        if self.executor is not None:
            self.executor.resume(parent["id"])
        else:
            self.execute(parent["id"])
