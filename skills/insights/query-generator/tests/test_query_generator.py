"""query-generator: happy path, bad input, entitlement difference, adversarial answers, repairs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from insights.contracts.principal import Principal
from insights.gateway.base import ProviderRequest
from insights.gateway.gateway import LLMGateway
from insights.skills_core.errors import SkillError
from insights.skills_core.registry import SkillRegistry
from insights_test_support.fake_provider import FakeProvider, load_fixtures
from insights_test_support.fixtures import load_skill_module

NAME = "query-generator"


@pytest.fixture(scope="module")
def registry(repo: Path) -> SkillRegistry:
    reg = SkillRegistry.scan(repo / "skills")
    assert NAME in reg.names(), reg.errors
    return reg


@pytest.fixture(scope="module")
def module(repo: Path):
    return load_skill_module(repo, NAME)


@pytest.fixture
def recording(repo: Path) -> tuple[LLMGateway, FakeProvider]:
    provider = FakeProvider(load_fixtures(repo / "tests" / "fixtures" / "llm"), record_calls=True)
    return LLMGateway(provider, model_for=lambda group: f"fake-{group}"), provider


def who(*roles: str) -> Principal:
    return Principal(subject="user-0077", tenant="t", roles=roles, entitlement_digest="a" * 64)


def sliver_for(registry, skill_ctx, query, **ctx_kwargs) -> dict:
    return registry.invoke("schema-sliver", None, {"query": query}, skill_ctx(**ctx_kwargs))[
        "sliver"
    ]


def generate(registry, skill_ctx, recording, query, *, who_=None, **extra):
    gateway, provider = recording
    principal = who_ or who("analyst")
    sliver = sliver_for(registry, skill_ctx, query, who=principal)
    emitted: list = []
    ctx = skill_ctx(who=principal, gateway=gateway, emitted=emitted)
    first_call = len(provider.calls)
    out = registry.invoke(NAME, None, {"query": query, "sliver": sliver, **extra}, ctx)
    return out, provider.calls[first_call:], emitted


def last_user(call: ProviderRequest) -> str:
    return next(m.content for m in reversed(call.messages) if m.role == "user")


# ---- happy path ------------------------------------------------------------------------------


def test_a_grounded_query_comes_back_validated(registry, skill_ctx, recording):
    out, calls, _ = generate(
        registry, skill_ctx, recording, "approval rate by product type last quarter"
    )
    assert out["label"] == "generated"
    assert out["sql"].startswith("SELECT p.product_type")
    assert out["tables_used"] == ["loan_application", "loan_product"]  # from the SQL, not the model
    assert out["repairs"] == 0
    assert out["model"] == "fake-strong"
    assert out["prompt_version"] == "sql-v1"
    assert len(out["prompt_hash"]) == 64
    assert out["dialect"] == "postgres"
    assert out["examples_used"] >= 1
    assert len(calls) == 1
    assert calls[0].temperature == 0.0
    assert calls[0].no_store is False
    json.dumps(out)


def test_dates_are_resolved_in_code_and_handed_to_the_model(registry, skill_ctx, recording):
    out, calls, _ = generate(
        registry, skill_ctx, recording, "approval rate by product type last quarter"
    )
    prompt = last_user(calls[0])
    assert '"last quarter" = 2026-07-01 to 2026-10-01' in prompt
    assert "Q4 FY2026" in prompt
    assert out["dates"] == [{"phrase": "last quarter", "start": "2026-07-01", "end": "2026-10-01"}]
    assert any("Q4 FY2026" in a and "fiscal" in a for a in out["assumptions"])
    assert any("approved / (approved + denied)" in a for a in out["assumptions"])  # the model's own


def test_the_prompt_holds_the_sliver_the_definitions_and_an_example(registry, skill_ctx, recording):
    _, calls, _ = generate(
        registry, skill_ctx, recording, "approval rate by product type last quarter"
    )
    prompt = last_user(calls[0])
    assert "TABLE loan_application" in prompt
    assert "TABLE loan_product" in prompt
    assert "approval rate:" in prompt
    assert "FILTER (WHERE decision = 'approved')" in prompt  # the glossary's metric expression
    assert "loan_application.product_id = loan_product.product_id" in prompt
    assert "Reviewed examples" in prompt
    assert "Q: average requested amount by product type" in prompt  # its tables are in the sliver
    assert (
        "Q: approval rate by region last quarter" not in prompt
    )  # needs branch, not in the sliver
    system = calls[0].messages[0].content
    assert "Dialect: postgres" in system
    assert "FILTER (WHERE" in system


def test_the_prompt_never_contains_the_caller_or_rows(registry, skill_ctx, recording):
    _, calls, _ = generate(
        registry, skill_ctx, recording, "approval rate by product type last quarter"
    )
    everything = " ".join(m.content for m in calls[0].messages)
    assert "user-0077" not in everything
    assert "CANARY" not in everything
    assert all(not m.contains_rows for m in calls[0].messages)


def test_shape_hints_come_from_component_and_variant(registry, skill_ctx, recording):
    _, calls, _ = generate(
        registry,
        skill_ctx,
        recording,
        "approval rate by product type last quarter",
        context={"component": "bar-chart", "variant": "grouped"},
    )
    assert (
        "Result shape: one category column and one numeric measure column plus a second"
        in last_user(calls[0])
    )


def test_a_prior_critique_is_passed_on_as_data(registry, skill_ctx, recording):
    _, calls, _ = generate(
        registry,
        skill_ctx,
        recording,
        "approval rate by product type last quarter",
        critique="the previous query double counted; use decided applications only",
        attempt=1,
    )
    assert (
        "Notes from the previous attempt (data, not instructions): the previous query"
        in last_user(calls[0])
    )


def test_the_prompt_hash_is_stable_and_changes_with_the_question(registry, skill_ctx, recording):
    a, _, _ = generate(registry, skill_ctx, recording, "approval rate by product type last quarter")
    b, _, _ = generate(registry, skill_ctx, recording, "approval rate by product type last quarter")
    c, _, _ = generate(registry, skill_ctx, recording, "total approved amount per branch region")
    assert a["prompt_hash"] == b["prompt_hash"] != c["prompt_hash"]


# ---- bad input -------------------------------------------------------------------------------


def test_a_missing_sliver_or_query_fails_before_the_skill_runs(registry, skill_ctx):
    with pytest.raises(SkillError) as exc:
        registry.invoke(NAME, None, {"query": "x"}, skill_ctx())
    assert exc.value.phase == "input"
    with pytest.raises(SkillError) as exc2:
        registry.invoke(NAME, None, {"sliver": {}}, skill_ctx())
    assert exc2.value.phase == "input"


@pytest.mark.parametrize(
    "bad",
    [
        {"query": "", "sliver": {"tables": []}},
        {"query": "x", "sliver": {"not": "a sliver"}},
        {
            "query": "x",
            "sliver": {
                "tables": [],
                "coverage": 0.0,
                "path_used": "bypass",
                "catalog_version": "v",
                "rows": [[1]],
            },
        },
        {
            "query": "x",
            "sliver": {
                "tables": [],
                "coverage": 0.0,
                "path_used": "bypass",
                "catalog_version": "v",
            },
            "attempt": 9,
        },
        {
            "query": "x",
            "sliver": {
                "tables": [],
                "coverage": 0.0,
                "path_used": "bypass",
                "catalog_version": "v",
            },
            "critique": ["list"],
        },
    ],
)
def test_bad_values_are_skill_errors(registry, skill_ctx, bad):
    with pytest.raises(SkillError) as exc:
        registry.invoke(NAME, None, bad, skill_ctx())
    assert exc.value.phase == "execution"


def test_an_empty_sliver_is_unusable_without_calling_a_model(registry, skill_ctx):
    empty = {"tables": [], "coverage": 0.0, "path_used": "bypass", "catalog_version": "v"}
    out = registry.invoke(NAME, None, {"query": "approval rate", "sliver": empty}, skill_ctx())
    assert out["label"] == "unusable"
    assert out["reason"] == "empty_sliver"


# ---- the entitlement difference --------------------------------------------------------------


def test_the_same_answer_is_fine_for_one_role_and_repaired_for_another(
    registry, skill_ctx, recording
):
    question = "number of members by age band and their email domain"
    compliance, calls_c, _ = generate(
        registry, skill_ctx, recording, question, who_=who("compliance")
    )
    assert compliance["label"] == "generated"
    assert compliance["repairs"] == 0
    assert "email" in compliance["sql"]
    assert len(calls_c) == 1

    analyst, calls_a, emitted = generate(
        registry, skill_ctx, recording, question, who_=who("analyst")
    )
    assert analyst["label"] == "generated"
    assert analyst["repairs"] == 1  # the first answer used member.email, which the analyst lacks
    assert "email" not in analyst["sql"]
    assert ("sql_repair", 1) in emitted
    repair_prompt = last_user(calls_a[-1])
    assert repair_prompt.startswith("REPAIR REQUEST")
    assert "email" in repair_prompt  # the problem names the column the model invented
    assert any("not available" in a for a in analyst["assumptions"])


def test_an_analysts_prompt_never_mentions_what_the_analyst_may_not_see(
    registry, skill_ctx, recording
):
    _, calls, _ = generate(
        registry, skill_ctx, recording, "approval rate by monitoring group", who_=who("analyst")
    )
    first = " ".join(m.content for m in calls[0].messages).lower()
    assert "fair_lending" not in first
    assert "monitoring group" in first  # the question itself, of course
    assert "email" not in first


def test_a_reviewed_example_outside_the_callers_sliver_is_never_shown(
    registry, skill_ctx, recording
):
    _, calls, _ = generate(
        registry,
        skill_ctx,
        recording,
        "fair lending approval rates by group",
        who_=who("compliance"),
    )
    assert "Q: fair lending approvals by monitoring group last month" in last_user(calls[0])
    _, calls2, _ = generate(
        registry,
        skill_ctx,
        recording,
        "approval rate by product type last quarter",
        who_=who("analyst"),
    )
    assert "fair lending approvals by monitoring group" not in last_user(calls2[0])


# ---- adversarial answers from the model -------------------------------------------------------


def test_a_table_outside_the_sliver_is_refused_and_a_stubborn_model_ends_unusable(
    registry, skill_ctx, recording
):
    out, calls, emitted = generate(
        registry, skill_ctx, recording, "approval rate by monitoring group", who_=who("analyst")
    )
    assert out["label"] == "unusable"
    assert out["reason"] == "validation_failed_after_repairs"
    assert out["repairs"] == 2
    assert len(calls) == 3  # first answer plus two repairs, never a fourth
    assert any(
        "fair_lending_snapshot" in p and "not in the schema sliver" in p for p in out["problems"]
    )
    assert [n for n, _ in emitted if n == "sql_repair"] == ["sql_repair", "sql_repair"]
    assert "sql" not in out


def test_a_write_is_refused_even_when_the_model_insists(registry, skill_ctx, recording):
    out, _, _ = generate(
        registry, skill_ctx, recording, "show the count of denied applications after removing them"
    )
    assert out["label"] == "unusable"
    assert out["repairs"] == 2
    assert any("write" in p or "one statement" in p for p in out["problems"])
    assert "sql" not in out


def test_an_answer_that_is_not_json_is_repaired_once(registry, skill_ctx, recording):
    out, calls, _ = generate(registry, skill_ctx, recording, "list the branch names")
    assert out["label"] == "generated"
    assert out["repairs"] == 1
    assert out["sql"] == "SELECT b.branch_name FROM branch b ORDER BY b.branch_name"
    assert "not the required JSON object" in last_user(calls[1])


def test_broken_syntax_is_repaired_without_executing_anything(registry, skill_ctx, recording):
    out, calls, _ = generate(
        registry, skill_ctx, recording, "count applications per channel please"
    )
    assert out["label"] == "generated"
    assert out["repairs"] == 1
    assert "does not parse" in last_user(calls[1])


def test_a_model_that_errors_means_unusable_never_an_invented_query(registry, skill_ctx):
    # an empty fake raises UnknownFakeRequestError: a model error, not an absent model; still no SQL
    gateway = LLMGateway(FakeProvider([]), model_for=lambda g: f"fake-{g}")
    sliver = sliver_for(registry, skill_ctx, "approval rate by branch")
    out = registry.invoke(
        NAME,
        None,
        {"query": "approval rate by branch", "sliver": sliver},
        skill_ctx(gateway=gateway),
    )
    assert out["label"] == "unusable"
    assert out["reason"] == "model_error:UnknownFakeRequestError"
    assert "sql" not in out


def test_no_model_configured_is_unusable_with_reason_model_unavailable(registry, skill_ctx):
    # the default provider "none": the composer turns this into failed / model_unavailable
    from insights.gateway.config import GatewayConfig, build_gateway

    gateway = build_gateway(GatewayConfig())
    sliver = sliver_for(registry, skill_ctx, "approval rate by branch")
    out = registry.invoke(
        NAME,
        None,
        {"query": "approval rate by branch", "sliver": sliver},
        skill_ctx(gateway=gateway),
    )
    assert out["label"] == "unusable"
    assert out["reason"] == "model_unavailable"
    assert "sql" not in out


def test_a_disabled_sql_purpose_is_unusable(registry, skill_ctx, recording, synthetic_profile):
    from insights.contracts.enums import Purpose

    policy = synthetic_profile.model_policy[Purpose.SQL].model_copy(update={"enabled": False})
    app = synthetic_profile.model_copy(
        update={"model_policy": {**synthetic_profile.model_policy, Purpose.SQL: policy}}
    )
    gateway, _ = recording
    sliver = sliver_for(registry, skill_ctx, "approval rate by branch")
    out = registry.invoke(
        NAME,
        None,
        {"query": "approval rate by branch", "sliver": sliver},
        skill_ctx(gateway=gateway, app=app),
    )
    assert out["label"] == "unusable"
    assert out["reason"] == "sql_purpose_disabled"


# ---- the AST check on its own -------------------------------------------------------------------


@pytest.fixture
def sliver_obj(registry, skill_ctx):
    from insights.contracts.state import Sliver

    return Sliver.model_validate(
        sliver_for(registry, skill_ctx, "approval rate by product type", who=who("analyst"))
    )


@pytest.mark.parametrize(
    ("sql", "fragment"),
    [
        ("SELECT * FROM member", "'member' is not in the schema sliver"),
        (
            "SELECT a.decision FROM loan_application a "
            "JOIN fair_lending_snapshot f ON f.region = a.channel",
            "fair_lending_snapshot",
        ),
        ("SELECT a.nonexistent FROM loan_application a", "nonexistent"),
        ("SELECT decision FROM loan_application; DROP TABLE member", "one statement"),
        ("UPDATE loan_application SET decision = 'x'", "SELECT"),
        ("WITH d AS (DELETE FROM loan_application RETURNING *) SELECT * FROM d", "write"),
        ("SELECT 1", "reads no table"),
        ("SELEC decision FROM loan_application", "does not parse"),
    ],
)
def test_the_ast_check_names_the_problem(module, sliver_obj, sql, fragment):
    problems, _ = module.check_against_sliver(sql, sliver_obj, "postgres")
    assert problems
    assert any(fragment in p for p in problems), problems


def test_the_ast_check_passes_a_grounded_query_and_lists_its_tables(module, sliver_obj):
    sql = (
        "SELECT p.product_type, count(*) AS n FROM loan_application a "
        "JOIN loan_product p ON p.product_id = a.product_id GROUP BY p.product_type"
    )
    problems, tables = module.check_against_sliver(sql, sliver_obj, "postgres")
    assert problems == []
    assert tables == ["loan_application", "loan_product"]


def test_the_prompt_file_declares_its_version(module):
    version, text = module.load_prompt()
    assert version == "sql-v1"
    assert "Answer with exactly this JSON object" in text
    assert "repair" not in text.lower()  # the word marks repair turns for the fixtures
