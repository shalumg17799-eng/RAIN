"""Versioned agent registry: seed agents from agents/*.yaml, runtime-registered agents persisted in the DB
(visible to every API replica and worker). Agents can be disabled (retired) without deleting history.

Step kinds (exactly one per step): `skill:` runs a skill, `agent:` runs another agent as a child run,
`parallel: [...]` runs member steps concurrently (fan-out/fan-in), `approval: {...}` pauses for a human decision.
Optional on any step: `when:` / `unless:` ("$." reference), `enterprises: [...]` (skip for other tenants),
`retry:` / `timeout:` (see policy.py). Agent level: `defaults:` (policy), `acceptance:` (see acceptance.py)."""
from pathlib import Path

import yaml

from dif.runtime.acceptance import validate_acceptance
from dif.runtime.policy import validate_policy
from dif.runtime.store import Store
from dif.skills.registry import SkillRegistry, _vkey

MAX_PARALLEL = 8
KINDS = ("skill", "agent", "parallel", "approval")


class AgentError(Exception):
    pass


def step_kind(st: dict) -> str:
    kinds = [k for k in KINDS if st.get(k)]
    if len(kinds) != 1:
        raise AgentError(f"step '{st.get('id')}' needs exactly one of {', '.join(KINDS)}")
    return kinds[0]


def _check_common(st, seen, where):
    for cond in ("when", "unless"):
        if cond in st and not (isinstance(st[cond], str) and st[cond].startswith("$.")):
            raise AgentError(f"{where}: '{cond}' must be a \"$.\" reference")
    if "enterprises" in st and not (isinstance(st["enterprises"], list) and st["enterprises"]):
        raise AgentError(f"{where}: 'enterprises' must be a non-empty list")
    try:
        validate_policy(st, where)
    except ValueError as e:
        raise AgentError(str(e))
    for ref in _refs(st.get("input", {})) + _refs([st.get("when"), st.get("unless")]):
        if ref.startswith("steps.") and ref.split(".")[1] not in seen:
            raise AgentError(f"{where} references '{ref}' before it runs")


def _check_leaf(st, skills, agents, seen, used, where):
    kind = step_kind(st)
    if kind == "parallel":
        raise AgentError(f"{where}: nested parallel groups are not supported")
    _check_common(st, seen, where)
    try:
        if kind == "skill":
            used.append(skills.get(st["skill"], st.get("version")))
        elif kind == "agent":
            if agents is None:
                raise AgentError("agent steps need the agent registry")
            agents.get(st["agent"], st.get("version"))
        elif kind == "approval":
            a = st["approval"]
            if not isinstance(a, dict):
                raise AgentError("approval must be a mapping {title, payload, roles}")
            if "roles" in a and not (isinstance(a["roles"], list) and set(a["roles"]) <= {"approver", "admin"}):
                raise AgentError("approval.roles may only contain approver and admin")
            for ref in _refs(a.get("payload", {})):
                if ref.startswith("steps.") and ref.split(".")[1] not in seen:
                    raise AgentError(f"{where} payload references '{ref}' before it runs")
    except AgentError:
        raise
    except Exception as e:
        raise AgentError(f"{where}: {e}")


def validate_agent(cfg: dict, skills: SkillRegistry, agents: "AgentRegistry | None" = None, contracts_dir: Path | None = None):
    for k in ("name", "version", "steps"):
        if not cfg.get(k):
            raise AgentError(f"agent config missing '{k}'")
    try:
        validate_policy({"retry": cfg.get("defaults", {}).get("retry"), "timeout": cfg.get("defaults", {}).get("timeout")}, "defaults")
        if contracts_dir is not None:
            validate_acceptance(cfg, contracts_dir)
    except (ValueError, FileNotFoundError) as e:
        raise AgentError(str(e))
    seen, used = [], []
    for st in cfg["steps"]:
        if not st.get("id"):
            raise AgentError("every step needs an 'id'")
        if st["id"] in seen:
            raise AgentError(f"duplicate step id '{st['id']}'")
        where = f"step '{st['id']}'"
        if step_kind(st) == "parallel":
            members = st["parallel"]
            if not isinstance(members, list) or not members or len(members) > MAX_PARALLEL:
                raise AgentError(f"{where}: parallel needs 1..{MAX_PARALLEL} member steps")
            if st.get("on_error", "fail_fast") not in ("fail_fast", "collect"):
                raise AgentError(f"{where}: on_error must be fail_fast or collect")
            _check_common({k: v for k, v in st.items() if k != "input"}, seen, where)
            group_seen = list(seen)  # members may reference earlier steps but not each other
            for m in members:
                if not m.get("id"):
                    raise AgentError(f"{where}: every member needs an 'id'")
                if m["id"] in seen or m["id"] == st["id"]:
                    raise AgentError(f"duplicate step id '{m['id']}'")
                _check_leaf(m, skills, agents, group_seen, used, f"{where} member '{m['id']}'")
                seen.append(m["id"])
        else:
            _check_leaf(st, skills, agents, seen, used, where)
        seen.append(st["id"])
    names = {s.name for s in used}
    for s in used:
        missing = [d for d in s.dependencies if d not in names]
        if missing:
            raise AgentError(f"skill '{s.name}' requires {missing} to be part of the agent")


def _refs(v):
    if isinstance(v, dict):
        return [r for x in v.values() for r in _refs(x)]
    if isinstance(v, list):
        return [r for x in v for r in _refs(x)]
    return [v[2:]] if isinstance(v, str) and v.startswith("$.") else []


def flat_steps(cfg):
    """Step ids including parallel members (members listed before their group)."""
    out = []
    for st in cfg["steps"]:
        if st.get("parallel"):
            out += [m["id"] for m in st["parallel"]]
        out.append(st["id"])
    return out


class AgentRegistry:
    def __init__(self, agents_dir: Path, store: Store, contracts_dir: Path | None = None):
        self.store, self.contracts_dir = store, contracts_dir
        self.seeds = {}
        for p in sorted(Path(agents_dir).glob("*.yaml")):
            cfg = yaml.safe_load(p.read_text())
            self.seeds[(cfg["name"], str(cfg["version"]))] = {"config": cfg, "enabled": True, "source": "file"}

    def _all(self):
        out = dict(self.seeds)
        for d in self.store.agent_defs():  # later rows (re-enable/disable) override
            out[(d["name"], d["version"])] = {"config": d["config"], "enabled": d["enabled"], "source": "registered",
                                              "enterprise": d.get("enterprise_id")}
        return out

    def get(self, name, version=None):
        cands = {v: e for (n, v), e in self._all().items() if n == name and e["enabled"]}
        if version:
            cands = {v: e for v, e in cands.items() if v == str(version)}
        if not cands:
            raise AgentError(f"unknown or disabled agent '{name}'" + (f" version {version}" if version else ""))
        return cands[max(cands, key=_vkey)]["config"]

    def register(self, cfg, skills, by, enterprise=None):
        validate_agent(cfg, skills, self, self.contracts_dir)
        if (cfg["name"], str(cfg["version"])) in self._all():
            raise AgentError(f"{cfg['name']} {cfg['version']} already exists; bump the version")
        self.store.add_agent_def(cfg, by, enterprise)

    def set_enabled(self, name, version, enabled):
        if (name, version) in self.seeds and not any(d["name"] == name and d["version"] == version
                                                     for d in self.store.agent_defs()):
            self.store.add_agent_def(self.seeds[(name, version)]["config"], "system")  # promote seed to DB
        if not self.store.set_agent_enabled(name, version, enabled):
            raise AgentError("no such agent version")

    def list(self):
        return [{"name": n, "version": v, "enabled": e["enabled"], "source": e["source"],
                 "description": e["config"].get("description"), "steps": flat_steps(e["config"]),
                 "gates": [s["id"] for s in e["config"]["steps"] if s.get("approval")],
                 "acceptance": bool(e["config"].get("acceptance"))}
                for (n, v), e in sorted(self._all().items())]
