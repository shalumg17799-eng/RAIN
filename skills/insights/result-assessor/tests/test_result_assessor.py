"""result-assessor: happy path, bad input, entitlement difference, adversarial results, judge."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from insights.contracts.enums import Purpose
from insights.contracts.principal import Principal
from insights.contracts.profile import ModelPolicy
from insights.contracts.response import Column
from insights.contracts.state import ResultRef
from insights.gateway.gateway import LLMGateway
from insights.runtime.stores import InMemoryResultStore, ResultNotFoundError
from insights.skills_core.errors import SkillError
from insights.skills_core.registry import SkillRegistry
from insights_test_support.fake_provider import FakeProvider, load_fixtures

NAME = "result-assessor"


@pytest.fixture(scope="module")
def registry(repo: Path) -> SkillRegistry:
    reg = SkillRegistry.scan(repo / "skills")
    assert NAME in reg.names(), reg.errors
    return reg


def who(*roles: str) -> Principal:
    return Principal(subject="user-0077", tenant="t", roles=roles, entitlement_digest="a" * 64)


def sliver_for(registry, skill_ctx, query, principal=None):
    return registry.invoke(
        "schema-sliver", None, {"query": query}, skill_ctx(who=principal or who("analyst"))
    )["sliver"]


def execution_with(
    results: InMemoryResultStore,
    rows,
    *,
    status="ok",
    truncated=False,
    run_id="run-1",
    owner="user-0001",
):
    columns = (
        Column(name="product_type", type="text", role="dimension"),
        Column(name="n", type="bigint", role="measure"),
    )
    if status != "ok":
        return {
            "status": status,
            "failure": status,
            "columns": [],
            "row_count": None,
            "truncated": False,
            "result_ref": None,
            "duration_ms": 1,
            "masked_columns": [],
            "detail": "database error (database, 22012)",
        }
    ref = results.put(run_id=run_id, owner=owner, columns=columns, rows=rows)
    return {
        "status": "ok",
        "failure": None,
        "columns": [c.model_dump(mode="json") for c in columns],
        "row_count": len(rows),
        "truncated": truncated,
        "result_ref": ref.model_dump(mode="json"),
        "duration_ms": 5,
        "masked_columns": [],
        "detail": "",
    }


def assess(registry, ctx, **input):
    return registry.invoke(NAME, None, {"question": "approval rate by product type", **input}, ctx)


# ---- happy path ------------------------------------------------------------------------------


def test_a_good_result_is_answered_with_a_full_score(registry, skill_ctx):
    results = InMemoryResultStore()
    ctx = skill_ctx(results=results)
    sliver = sliver_for(registry, skill_ctx, "approval rate by product type")
    out = assess(
        registry,
        ctx,
        execution=execution_with(results, (("auto", 3), ("mortgage", 2))),
        sliver=sliver,
    )
    assert out["label"] == "answer"
    assert out["score"] == 1.0
    assert out["critique"] is None
    assert out["signals"]["ran"] is True
    assert out["signals"]["row_count"] == 2
    assert out["signals"]["null_ratio"] == 0.0
    assert out["signals"]["coverage"] == 1.0
    assert out["signals"]["judge"] == "disabled"
    json.dumps(out)
    assert "auto" not in json.dumps(out)  # signals are numbers and codes, never values


def test_the_rows_are_still_held_after_an_answer(registry, skill_ctx):
    results = InMemoryResultStore()
    ctx = skill_ctx(results=results)
    execution = execution_with(results, (("auto", 3),))
    assess(
        registry,
        ctx,
        execution=execution,
        sliver=sliver_for(registry, skill_ctx, "approval rate by product type"),
    )
    assert results.get(ResultRef(**execution["result_ref"]), owner="user-0001").rows == (
        ("auto", 3),
    )


# ---- bad input -------------------------------------------------------------------------------


def test_missing_inputs_fail_before_the_skill_runs(registry, skill_ctx):
    with pytest.raises(SkillError) as exc:
        registry.invoke(NAME, None, {"question": "q", "sliver": {}}, skill_ctx())
    assert exc.value.phase == "input"


@pytest.mark.parametrize(
    "bad",
    [
        {"question": 1, "execution": {"status": "ok"}, "sliver": {}},
        {"question": "q", "execution": "not a dict", "sliver": {}},
        {"question": "q", "execution": {"no_status": 1}, "sliver": {}},
        {"question": "q", "execution": {"status": "ok"}, "sliver": {"nope": 1}},
        {
            "question": "q",
            "execution": {"status": "ok"},
            "sliver": {"tables": [], "coverage": 1, "path_used": "bypass", "catalog_version": "v"},
            "attempt": 9,
        },
    ],
)
def test_bad_values_are_skill_errors(registry, skill_ctx, bad):
    with pytest.raises(SkillError) as exc:
        registry.invoke(NAME, None, bad, skill_ctx())
    assert exc.value.phase == "execution"


# ---- the decisions ---------------------------------------------------------------------------


def test_terminal_failures_escalate_and_are_never_refined(registry, skill_ctx):
    results = InMemoryResultStore()
    for status in ("policy_denied", "access_denied", "timeout"):
        out = assess(
            registry,
            skill_ctx(results=results),
            execution=execution_with(results, (), status=status),
            sliver=sliver_for(registry, skill_ctx, "approval rate by product type"),
        )
        assert out["label"] == "escalate", status
        assert out["signals"]["terminal"] is True


def test_a_query_error_asks_for_a_different_query_with_the_error_kind(registry, skill_ctx):
    results = InMemoryResultStore()
    emitted: list = []
    out = assess(
        registry,
        skill_ctx(results=results, emitted=emitted),
        execution=execution_with(results, (), status="error"),
        sliver=sliver_for(registry, skill_ctx, "approval rate by product type"),
    )
    assert out["label"] == "refine_query"
    assert "failed to run" in out["critique"]
    assert "22012" in out["critique"]  # the kind and code, never database text
    assert ("refine_query", None) in emitted


def test_low_coverage_widens_the_sliver_and_names_the_gap(registry, skill_ctx):
    results = InMemoryResultStore()
    sliver = sliver_for(registry, skill_ctx, "approval rate by product type")
    sliver["coverage"] = 0.3
    out = assess(
        registry,
        skill_ctx(results=results),
        execution=execution_with(results, (("auto", 1),)),
        sliver=sliver,
        unmatched=["weather", "mood"],
    )
    assert out["label"] == "refine_sliver"
    assert "weather, mood" in out["critique"]


def test_an_empty_result_with_middling_coverage_widens_the_sliver(registry, skill_ctx):
    results = InMemoryResultStore()
    sliver = sliver_for(registry, skill_ctx, "approval rate by product type")
    sliver["coverage"] = 0.7
    out = assess(
        registry, skill_ctx(results=results), execution=execution_with(results, ()), sliver=sliver
    )
    assert out["label"] == "refine_sliver"


def test_an_empty_result_with_full_coverage_is_an_honest_empty_answer(registry, skill_ctx):
    results = InMemoryResultStore()
    out = assess(
        registry,
        skill_ctx(results=results),
        execution=execution_with(results, ()),
        sliver=sliver_for(registry, skill_ctx, "approval rate by product type"),
    )
    assert out["label"] == "answer"
    assert out["signals"]["empty"] is True
    assert out["score"] == 0.7
    assert "no rows matched" in out["signals"]["note"]


def test_mostly_null_values_ask_for_a_different_query(registry, skill_ctx):
    results = InMemoryResultStore()
    out = assess(
        registry,
        skill_ctx(results=results),
        execution=execution_with(results, ((None, None), (None, 1), ("x", None))),
        sliver=sliver_for(registry, skill_ctx, "approval rate by product type"),
    )
    assert out["label"] == "refine_query"
    assert out["signals"]["null_ratio"] > 0.5
    assert "NULL" in out["critique"]
    assert out["critique"] != "x"  # no values, only the ratio


def test_a_refine_drops_the_runs_rows(registry, skill_ctx):
    results = InMemoryResultStore()
    ctx = skill_ctx(results=results)
    execution = execution_with(results, ((None, None), (None, None)))
    out = assess(
        registry,
        ctx,
        execution=execution,
        sliver=sliver_for(registry, skill_ctx, "approval rate by product type"),
    )
    assert out["label"] == "refine_query"
    with pytest.raises(ResultNotFoundError):
        results.get(ResultRef(**execution["result_ref"]), owner="user-0001")


def test_truncation_and_repairs_lower_the_score_but_still_answer(registry, skill_ctx):
    results = InMemoryResultStore()
    out = assess(
        registry,
        skill_ctx(results=results),
        execution=execution_with(results, (("auto", 1),), truncated=True),
        sliver=sliver_for(registry, skill_ctx, "approval rate by product type"),
        generation={"repairs": 1, "sql": "SELECT 1"},
    )
    assert out["label"] == "answer"
    assert out["score"] == 0.8
    assert out["signals"]["truncated"] is True
    assert out["signals"]["repairs"] == 1


def test_rows_that_vanished_cannot_be_answered(registry, skill_ctx):
    results = InMemoryResultStore()
    execution = execution_with(results, (("auto", 1),))
    results.drop_run("run-1")
    out = assess(
        registry,
        skill_ctx(results=results),
        execution=execution,
        sliver=sliver_for(registry, skill_ctx, "approval rate by product type"),
    )
    assert out["label"] == "refine_query"
    assert out["signals"]["rows_missing"] is True


# ---- the entitlement difference --------------------------------------------------------------


def test_rows_held_by_another_caller_are_not_readable_here(registry, skill_ctx):
    results = InMemoryResultStore()
    execution = execution_with(
        results, (("auto", 1),), owner="someone-else"
    )  # not this ctx's subject
    out = assess(
        registry,
        skill_ctx(results=results),
        execution=execution,
        sliver=sliver_for(registry, skill_ctx, "approval rate by product type"),
    )
    assert out["label"] == "refine_query"
    assert out["signals"]["rows_missing"] is True


# ---- the optional judge -----------------------------------------------------------------------


def _judge_on(synthetic_profile):
    policy = ModelPolicy(enabled=True, model_group="fast", temperature=0.0, max_tokens=300)
    return synthetic_profile.model_copy(
        update={"model_policy": {**synthetic_profile.model_policy, Purpose.JUDGE: policy}}
    )


@pytest.fixture
def recording(repo: Path):
    provider = FakeProvider(load_fixtures(repo / "tests" / "fixtures" / "llm"), record_calls=True)
    return LLMGateway(provider, model_for=lambda g: f"fake-{g}"), provider


def test_the_judge_never_sees_rows_and_can_agree(registry, skill_ctx, synthetic_profile, recording):
    gateway, provider = recording
    results = InMemoryResultStore()
    ctx = skill_ctx(results=results, gateway=gateway, app=_judge_on(synthetic_profile))
    out = assess(
        registry,
        ctx,
        execution=execution_with(results, (("Zebra Holdings LLC", 3),)),
        sliver=sliver_for(registry, skill_ctx, "approval rate by product type"),
        generation={
            "sql": "SELECT p.product_type, count(*) AS n FROM loan_application a "
            "JOIN loan_product p ON p.product_id = a.product_id GROUP BY p.product_type"
        },
    )
    assert out["label"] == "answer"
    assert out["signals"]["judge"] == "agrees"
    call = provider.calls[0]
    everything = " ".join(m.content for m in call.messages)
    assert "Zebra" not in everything
    assert "Result columns: product_type (text), n (bigint)" in everything
    assert all(not m.contains_rows for m in call.messages)
    assert call.no_store is False


def test_a_disagreeing_judge_asks_for_a_different_query_with_its_issue(
    registry, skill_ctx, synthetic_profile, recording
):
    gateway, _ = recording
    results = InMemoryResultStore()
    ctx = skill_ctx(results=results, gateway=gateway, app=_judge_on(synthetic_profile))
    out = registry.invoke(
        NAME,
        None,
        {
            "question": "which branches had the most denials",
            "execution": execution_with(results, (("East", 3),)),
            "sliver": sliver_for(registry, skill_ctx, "denials by branch"),
            "generation": {
                "sql": "SELECT b.region, count(*) FROM loan_application a "
                "JOIN branch b ON b.branch_id = a.branch_id GROUP BY b.region"
            },
        },
        ctx,
    )
    assert out["label"] == "refine_query"
    assert "groups by region" in out["critique"]
    assert out["signals"]["judge"] == "disagrees"


def test_an_unavailable_judge_does_not_block_an_answer(registry, skill_ctx, synthetic_profile):
    gateway = LLMGateway(FakeProvider([]), model_for=lambda g: f"fake-{g}")
    results = InMemoryResultStore()
    ctx = skill_ctx(results=results, gateway=gateway, app=_judge_on(synthetic_profile))
    out = assess(
        registry,
        ctx,
        execution=execution_with(results, (("auto", 1),)),
        sliver=sliver_for(registry, skill_ctx, "approval rate by product type"),
        generation={"sql": "SELECT 1"},
    )
    assert out["label"] == "answer"
    assert out["signals"]["judge"].startswith("unavailable:")
