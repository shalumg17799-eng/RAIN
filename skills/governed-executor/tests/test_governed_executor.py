"""governed-executor: happy path, bad input, entitlement difference, adversarial SQL (no database).

A stand-in adapter records what reaches the platform. The real-database checks are in
tests/datasources/test_pipeline_integration.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from insights.contracts.enums import AuditEventType
from insights.contracts.principal import Principal
from insights.contracts.state import ExecutionRecord, ResultRef
from insights.datasources.base import (
    AccessDeniedError,
    PlanEstimate,
    QueryError,
    QueryResult,
    QueryTimeoutError,
    ResultColumn,
)
from insights.runtime.stores import InMemoryResultStore, ResultNotFoundError
from insights.skills_core.context import make_context
from insights.skills_core.errors import SkillError
from insights.skills_core.protocols import Services
from insights.skills_core.registry import SkillRegistry

NAME = "governed-executor"
ROWS = (("auto", 12), ("mortgage", 7))
COLUMNS = (ResultColumn("product_type", "text"), ResultColumn("applications", "bigint"))


class FakeAdapter:
    def __init__(self, *, explain=None, result=None, error=None):
        self._explain = PlanEstimate(10.0, 5) if explain is None else explain
        self._error = error
        self._result = result or QueryResult(COLUMNS, ROWS, truncated=False, duration_ms=3)
        self.explains: list[tuple[str, object]] = []
        self.executes: list[tuple[str, object]] = []

    def explain(self, sql, binding, *, timeout_ms):
        self.explains.append((sql, binding))
        if isinstance(self._explain, Exception):
            raise self._explain
        return self._explain

    def execute(self, sql, binding, *, max_rows, timeout_ms):
        self.executes.append((sql, binding))
        if self._error:
            raise self._error
        return self._result


class FakeData:
    def __init__(self, adapter):
        self.adapter = adapter

    def adapter_for(self, app):
        return self.adapter


@pytest.fixture(scope="module")
def registry(repo: Path) -> SkillRegistry:
    reg = SkillRegistry.scan(repo / "skills")
    assert NAME in reg.names(), reg.errors
    return reg


def who(*roles: str, **attributes: str) -> Principal:
    return Principal(
        subject="user-0077",
        tenant="t",
        roles=roles,
        attributes=attributes,
        entitlement_digest="a" * 64,
    )


@pytest.fixture
def ctx_with(skill_ctx, services):
    def _make(adapter, **kw):
        base = skill_ctx(**kw)
        return make_context(
            **{
                **base,
                "services": Services(
                    catalogs=services.catalogs, kag=services.kag, data=FakeData(adapter)
                ),
            }  # type: ignore[arg-type]
        )

    return _make


def sliver_for(registry, skill_ctx, query, principal):
    return registry.invoke("schema-sliver", None, {"query": query}, skill_ctx(who=principal))[
        "sliver"
    ]


SQL = (
    "SELECT p.product_type, count(*) AS applications FROM loan_application a "
    "JOIN loan_product p ON p.product_id = a.product_id GROUP BY p.product_type"
)


def execute(registry, ctx, sql, sliver):
    return registry.invoke(NAME, None, {"sql": sql, "sliver": sliver}, ctx)


# ---- happy path ------------------------------------------------------------------------------


def test_rows_are_held_by_reference_and_never_in_the_output(registry, skill_ctx, ctx_with):
    adapter = FakeAdapter()
    results = InMemoryResultStore()
    ctx = ctx_with(adapter, results=results, who=who("analyst"))
    sliver = sliver_for(registry, skill_ctx, "applications by product type", who("analyst"))
    out = execute(registry, ctx, SQL, sliver)
    assert out["label"] == out["status"] == "ok"
    assert out["row_count"] == 2
    assert out["truncated"] is False
    assert [c["name"] for c in out["columns"]] == ["product_type", "applications"]
    assert [c["role"] for c in out["columns"]] == ["dimension", "measure"]
    assert out["tables"] == ["loan_application", "loan_product"]
    assert len(out["sql_sha256"]) == 64
    assert [d["layer"] for d in out["policy"]] == ["l1", "l2", "l3"]
    assert all(d["decision"] == "allow" for d in out["policy"])
    dump = json.dumps(out)
    assert "auto" not in dump  # the values live in the store only
    assert "mortgage" not in dump
    ExecutionRecord.model_validate(
        {k: v for k, v in out.items() if k not in ("label", "policy", "sql_sha256", "tables")}
    )
    stored = results.get(ResultRef(**out["result_ref"]), owner="user-0077")
    assert stored.rows == ROWS
    with pytest.raises(ResultNotFoundError):
        results.get(ResultRef(**out["result_ref"]), owner="someone-else")


def test_the_sql_that_runs_is_the_checked_one_with_a_limit(registry, skill_ctx, ctx_with):
    adapter = FakeAdapter()
    ctx = ctx_with(adapter, who=who("analyst"))
    sliver = sliver_for(registry, skill_ctx, "applications by product type", who("analyst"))
    execute(registry, ctx, SQL + " /* a comment */", sliver)
    ran, binding = adapter.executes[0]
    assert ran.rstrip().upper().endswith("LIMIT 1001")  # the sample app's max_rows + 1
    assert "/*" not in ran
    assert binding.role == "insights_analyst"
    assert adapter.explains[0][0] == ran  # the dry run saw the same text


def test_audit_holds_hashes_and_decisions_only(registry, skill_ctx, ctx_with):
    ctx = ctx_with(FakeAdapter(), who=who("analyst"))
    sliver = sliver_for(registry, skill_ctx, "applications by product type", who("analyst"))
    out = execute(registry, ctx, SQL, sliver)
    events = ctx["audit"].events()
    assert [e.type for e in events] == [AuditEventType.POLICY_DECISION, AuditEventType.EXECUTION]
    execution = events[-1]
    assert execution.sql_sha256 == out["sql_sha256"]
    assert execution.row_count == 2
    assert execution.execution_status.value == "ok"
    assert [p.layer.value for p in execution.policy] == ["l1", "l2", "l3"]
    blob = json.dumps([e.model_dump(mode="json") for e in events])
    assert "SELECT" not in blob
    assert "auto" not in blob


def test_masked_columns_are_named_for_a_role_with_masks(registry, skill_ctx, ctx_with):
    result = QueryResult(
        (ResultColumn("email", "text"), ResultColumn("n", "bigint")), (("x", 1),), False, 1
    )
    ctx = ctx_with(FakeAdapter(result=result), who=who("compliance"))
    sliver = sliver_for(registry, skill_ctx, "members by email", who("compliance"))
    out = execute(
        registry, ctx, "SELECT m.email, count(*) AS n FROM member m GROUP BY m.email", sliver
    )
    assert out["label"] == "ok"
    assert out["masked_columns"] == ["email"]


# ---- bad input -------------------------------------------------------------------------------


def test_missing_sql_or_sliver_fails_before_running(registry, skill_ctx):
    for bad in ({"sliver": {}}, {"sql": "SELECT 1"}):
        with pytest.raises(SkillError) as exc:
            registry.invoke(NAME, None, bad, skill_ctx())
        assert exc.value.phase == "input"


@pytest.mark.parametrize(
    "bad",
    [
        {"sql": 5, "sliver": {}},
        {"sql": "   ", "sliver": {}},
        {"sql": "SELECT 1", "sliver": {"nope": 1}},
    ],
)
def test_bad_values_are_skill_errors(registry, skill_ctx, bad):
    with pytest.raises(SkillError) as exc:
        registry.invoke(NAME, None, bad, skill_ctx())
    assert exc.value.phase == "execution"


def test_without_a_data_service_the_run_is_an_error_after_policy_passed(
    registry, skill_ctx, services
):
    base = skill_ctx(who=who("analyst"))
    ctx = make_context(**{**base, "services": Services(catalogs=services.catalogs)})  # type: ignore[arg-type]
    sliver = sliver_for(registry, skill_ctx, "applications by product type", who("analyst"))
    out = execute(registry, ctx, SQL, sliver)
    assert out["label"] == "error"
    assert "data source unavailable" in out["detail"]
    assert [d["layer"] for d in out["policy"]] == ["l1"]  # policy ran, nothing executed


# ---- the entitlement difference --------------------------------------------------------------


def test_the_same_query_and_sliver_are_allowed_for_one_role_and_denied_for_another(
    registry, skill_ctx, ctx_with
):
    sql = (
        "SELECT f.group_label, sum(f.approvals) AS approvals "
        "FROM fair_lending_snapshot f GROUP BY f.group_label"
    )
    sliver = sliver_for(registry, skill_ctx, "fair lending approvals by group", who("compliance"))
    assert "fair_lending_snapshot" in json.dumps(sliver)

    compliance_adapter = FakeAdapter()
    ok = execute(registry, ctx_with(compliance_adapter, who=who("compliance")), sql, sliver)
    assert ok["label"] == "ok"
    assert len(compliance_adapter.executes) == 1

    analyst_adapter = FakeAdapter()
    denied = execute(registry, ctx_with(analyst_adapter, who=who("analyst")), sql, sliver)
    assert (
        denied["label"] == "policy_denied"
    )  # entitlements are re-applied here, not trusted from the sliver
    assert "table_not_allowed" in denied["policy"][0]["rules_fired"]
    assert analyst_adapter.explains == []
    assert analyst_adapter.executes == []
    assert denied["result_ref"] is None
    assert denied["row_count"] is None


def test_a_caller_with_no_role_is_access_denied_before_any_policy(registry, skill_ctx, ctx_with):
    adapter = FakeAdapter()
    sliver = sliver_for(registry, skill_ctx, "applications by product type", who("analyst"))
    out = execute(registry, ctx_with(adapter, who=who("stranger")), SQL, sliver)
    assert out["label"] == "access_denied"
    assert out["policy"][0]["rules_fired"] == ["identity_not_bound"]
    assert adapter.executes == []


def test_a_branch_managers_binding_carries_their_branch_claim(registry, skill_ctx, ctx_with):
    adapter = FakeAdapter()
    principal = who("branch_manager", branch_id="B03")
    sliver = sliver_for(registry, skill_ctx, "applications by product type", principal)
    execute(registry, ctx_with(adapter, who=principal), SQL, sliver)
    _, binding = adapter.executes[0]
    assert binding.role == "insights_branch_manager"
    assert binding.settings["insights.branch_id"] == "B03"


# ---- adversarial SQL never reaches the platform ------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE loan_application",
        "SELECT 1 FROM loan_product; DROP TABLE loan_product",
        "SELECT pg_sleep(30) FROM loan_product",
        "SELECT * FROM pg_catalog.pg_shadow",
        "SET ROLE insights_compliance",
        "SELECT set_config('insights.branch_id', 'B01', true) FROM loan_product",
        "SELECT * FROM loan_product FOR UPDATE",
        "SELECT email FROM member",
        "WITH d AS (DELETE FROM loan_application RETURNING *) SELECT count(*) FROM d",
        "SELECT * INTO stolen FROM loan_product",
    ],
)
def test_hostile_sql_is_policy_denied_and_the_adapter_is_never_called(
    registry, skill_ctx, ctx_with, sql
):
    adapter = FakeAdapter()
    sliver = sliver_for(
        registry, skill_ctx, "applications by product type and member", who("analyst")
    )
    out = execute(registry, ctx_with(adapter, who=who("analyst")), sql, sliver)
    assert out["label"] == "policy_denied", out
    assert adapter.explains == []
    assert adapter.executes == []
    assert sql not in json.dumps(out)  # the denial names a rule, never the SQL


# ---- the platform's own answers are typed -------------------------------------------------------


def test_a_dry_run_over_the_limits_is_policy_denied(registry, skill_ctx, ctx_with):
    adapter = FakeAdapter(explain=PlanEstimate(total_cost=1e9, plan_rows=10))
    sliver = sliver_for(registry, skill_ctx, "applications by product type", who("analyst"))
    out = execute(registry, ctx_with(adapter, who=who("analyst")), SQL, sliver)
    assert out["label"] == "policy_denied"
    assert "cost_limit" in out["detail"]
    assert adapter.executes == []


@pytest.mark.parametrize(
    ("failure", "label"),
    [
        (AccessDeniedError("no"), "access_denied"),
        (QueryTimeoutError("slow"), "timeout"),
        (QueryError("syntax", "42601"), "error"),
    ],
)
def test_platform_failures_during_the_dry_run_are_typed(
    registry, skill_ctx, ctx_with, failure, label
):
    adapter = FakeAdapter(explain=failure)
    sliver = sliver_for(registry, skill_ctx, "applications by product type", who("analyst"))
    out = execute(registry, ctx_with(adapter, who=who("analyst")), SQL, sliver)
    assert out["label"] == label
    assert adapter.executes == []


@pytest.mark.parametrize(
    ("failure", "label"),
    [
        (AccessDeniedError("no"), "access_denied"),
        (QueryTimeoutError("slow"), "timeout"),
        (QueryError("database", "22012"), "error"),
    ],
)
def test_platform_failures_during_execution_are_typed_and_carry_no_text(
    registry, skill_ctx, ctx_with, failure, label
):
    adapter = FakeAdapter(error=failure)
    sliver = sliver_for(registry, skill_ctx, "applications by product type", who("analyst"))
    out = execute(registry, ctx_with(adapter, who=who("analyst")), SQL, sliver)
    assert out["label"] == label
    assert out["result_ref"] is None
    assert out["failure"] == label
    assert len(out["detail"]) <= 200
