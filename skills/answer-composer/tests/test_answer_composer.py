"""answer-composer: every exit path, the threshold, SQL visibility, the masked narrative."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from insights.contracts.enums import PathName, Purpose
from insights.contracts.principal import Principal
from insights.contracts.profile import ModelPolicy
from insights.contracts.response import Column, Provenance
from insights.contracts.state import AnswerRecord, Sliver, SliverColumn, SliverTable
from insights.gateway.gateway import LLMGateway
from insights.runtime.stores import InMemoryResultStore
from insights.skills_core.errors import SkillError
from insights.skills_core.registry import SkillRegistry
from insights_test_support.fake_provider import FakeProvider, load_fixtures

NAME = "answer-composer"
QUESTION = "approval rate by product type"


@pytest.fixture(scope="module")
def registry(repo: Path) -> SkillRegistry:
    reg = SkillRegistry.scan(repo / "skills")
    assert NAME in reg.names(), reg.errors
    return reg


def who(*roles: str) -> Principal:
    return Principal(subject="user-0077", tenant="t", roles=roles, entitlement_digest="a" * 64)


def step(output: dict) -> dict:
    return {
        "skill": "x",
        "version": "1.0.0",
        "output": output,
        "label": output.get("label"),
        "runs": 1,
    }


def compose(registry, ctx, steps: dict, attempt: int = 0, question: str = QUESTION) -> dict:
    refine = {
        "attempt": attempt,
        "max_refines": 2,
        "history": [],
        "tokens_used": 0,
        "exhausted": attempt >= 2,
        "critique": None,
    }
    out = registry.invoke(NAME, None, {"question": question, "steps": steps, "refine": refine}, ctx)
    AnswerRecord.model_validate(out)  # every output is the contract
    assert "rows" not in json.dumps(out)
    return out


def sliver_step(registry, skill_ctx, principal=None):
    out = registry.invoke(
        "schema-sliver", None, {"query": QUESTION}, skill_ctx(who=principal or who("analyst"))
    )
    return step(out)


def full_run(
    registry,
    skill_ctx,
    results: InMemoryResultStore,
    *,
    score=1.0,
    label="answer",
    owner="user-0001",
    rows=(("auto", 0.57), ("mortgage", 0.58)),
):
    columns = (
        Column(name="product_type", type="text", role="dimension"),
        Column(name="approval_rate", type="numeric", role="measure"),
    )
    ref = results.put(run_id="run-1", owner=owner, columns=columns, rows=rows)
    return {
        "route": step({"label": "data_query", "intent": "data_query", "path_preference": "bypass"}),
        "sliver": sliver_step(registry, skill_ctx),
        "generate": step(
            {
                "label": "generated",
                "sql": "SELECT p.product_type, 0.5 AS approval_rate FROM loan_product p",
                "dialect": "postgres",
                "assumptions": ["last quarter = Q4 FY2026"],
                "tables_used": ["loan_product"],
            }
        ),
        "execute": step(
            {
                "label": "ok",
                "status": "ok",
                "columns": [c.model_dump(mode="json") for c in columns],
                "row_count": len(rows),
                "truncated": False,
                "result_ref": ref.model_dump(mode="json"),
                "tables": ["loan_product"],
                "masked_columns": [],
            }
        ),
        "assess": step(
            {
                "label": label,
                "score": score,
                "signals": {"coverage": 1.0, "empty": False, "judge": "disabled"},
            }
        ),
    }


# ---- answered --------------------------------------------------------------------------------


def empty_run(
    registry,
    skill_ctx,
    results: InMemoryResultStore,
    *,
    dates,
    sql="SELECT a.channel, avg(a.requested_amount) FROM loan_application a "
    "WHERE a.application_date >= '2026-10-01' AND a.application_date < '2027-10-01' GROUP BY 1",
    freshness=None,
):
    """An answered run with zero rows: a hand-built sliver carrying the catalog's freshness."""
    run = full_run(registry, skill_ctx, results, rows=())
    tables = (
        SliverTable(
            source_id="main",
            name="loan_application",
            columns=(
                SliverColumn(name="application_date", type="date"),
                SliverColumn(name="decision_date", type="date"),
                SliverColumn(name="requested_amount", type="numeric"),
                SliverColumn(name="channel", type="text"),
            ),
            freshness=dict(freshness or {}),
        ),
    )
    sliver = Sliver(
        tables=tables,
        coverage=1.0,
        path_used=PathName.BYPASS,
        catalog_version="abc123",
        provenance=(Provenance(table="loan_application", source="main"),),
    )
    run["sliver"] = step(
        {"label": "ok", "path_used": "bypass", "sliver": sliver.model_dump(mode="json")}
    )
    run["generate"]["output"].update(
        {"sql": sql, "dates": dates, "tables_used": ["loan_application"]}
    )
    run["execute"]["output"].update({"row_count": 0, "tables": ["loan_application"]})
    run["assess"]["output"]["signals"]["empty"] = True
    return run


NO_DATA_YET = [{"phrase": "this year", "start": "2026-10-01", "end": "2027-10-01"}]
LATEST = {"application_date": "2026-09-30", "decision_date": "2026-09-28"}


def test_an_empty_answer_whose_window_lies_after_the_data_says_so(registry, skill_ctx):
    # P1, decided 2026-10-12: status stays answered; the reason names the latest available date
    results = InMemoryResultStore()
    ctx = skill_ctx(results=results, who=who("analyst"))
    out = compose(
        registry, ctx, empty_run(registry, skill_ctx, results, dates=NO_DATA_YET, freshness=LATEST)
    )
    assert out["status"] == "answered"
    assert out["row_count"] == 0
    assert out["reason"] == {
        "code": "no_data_in_period",
        "message": (
            'No data for "this year" (2026-10-01 to 2027-09-30) yet: the latest '
            "loan_application.application_date is 2026-09-30. Try a period up to 2026-09-30."
        ),
        "hints": ["Try a period up to 2026-09-30"],
    }
    assert out["confidence"]["signals"]["empty"] is True


def test_the_date_column_the_sql_uses_is_the_one_the_reason_names(registry, skill_ctx):
    results = InMemoryResultStore()
    ctx = skill_ctx(results=results, who=who("analyst"))
    by_decision = (
        "SELECT count(*) FROM loan_application a "
        "WHERE a.decision_date >= '2026-10-01' AND a.decision_date < '2027-10-01'"
    )
    out = compose(
        registry,
        ctx,
        empty_run(
            registry, skill_ctx, results, dates=NO_DATA_YET, sql=by_decision, freshness=LATEST
        ),
    )
    assert "the latest loan_application.decision_date is 2026-09-28" in out["reason"]["message"]
    assert out["reason"]["hints"] == ["Try a period up to 2026-09-28"]


def test_an_empty_answer_inside_the_data_window_carries_no_reason(registry, skill_ctx):
    # the window overlaps the data: the result is empty on its merits, nothing to explain away
    results = InMemoryResultStore()
    ctx = skill_ctx(results=results, who=who("analyst"))
    inside = [{"phrase": "last quarter", "start": "2026-07-01", "end": "2026-10-01"}]
    out = compose(
        registry, ctx, empty_run(registry, skill_ctx, results, dates=inside, freshness=LATEST)
    )
    assert out["status"] == "answered"
    assert out["reason"] is None


def test_without_freshness_or_a_time_window_an_empty_answer_carries_no_reason(registry, skill_ctx):
    results = InMemoryResultStore()
    ctx = skill_ctx(results=results, who=who("analyst"))
    no_freshness = empty_run(registry, skill_ctx, results, dates=NO_DATA_YET, freshness={})
    assert compose(registry, ctx, no_freshness)["reason"] is None
    no_window = empty_run(registry, skill_ctx, results, dates=[], freshness=LATEST)
    assert compose(registry, ctx, no_window)["reason"] is None


def test_an_answer_with_rows_never_carries_the_no_data_reason(registry, skill_ctx):
    results = InMemoryResultStore()
    ctx = skill_ctx(results=results, who=who("analyst"))
    run = full_run(registry, skill_ctx, results)
    run["generate"]["output"]["dates"] = NO_DATA_YET  # even with a window after the data
    assert compose(registry, ctx, run)["reason"] is None


def test_an_answer_carries_data_by_reference_sql_assumptions_provenance_and_confidence(
    registry, skill_ctx
):
    results = InMemoryResultStore()
    ctx = skill_ctx(results=results, who=who("analyst"))
    out = compose(registry, ctx, full_run(registry, skill_ctx, results))
    assert out["status"] == "answered"
    assert out["row_count"] == 2
    assert out["result_ref"]["ref"].startswith("mem-")
    assert [c["name"] for c in out["columns"]] == ["product_type", "approval_rate"]
    assert out["query"]["sql"].startswith("SELECT p.product_type")  # analysts may see SQL
    assert out["query"]["tables"] == ["loan_product"]
    assert out["confidence"] == {
        "score": 1.0,
        "calibrated": False,
        "signals": {"coverage": 1.0, "empty": False, "judge": "disabled"},
    }
    assert out["assumptions"] == ["last quarter = Q4 FY2026"]
    assert [p["table"] for p in out["provenance"]] == ["loan_product"]
    assert out["refine"] == {"attempts": 0, "path_used": "bypass"}
    assert out["narrative"] is None  # off by default
    assert "auto" not in json.dumps(out)


def test_sql_is_hidden_for_a_role_that_may_not_see_it(registry, skill_ctx):
    results = InMemoryResultStore()
    ctx = skill_ctx(results=results, who=who("branch_manager"))
    out = compose(registry, ctx, full_run(registry, skill_ctx, results))
    assert out["status"] == "answered"
    assert out["query"]["sql"] is None
    assert out["query"]["tables"] == []
    assert out["query"]["dialect"] == "postgres"


# ---- the metadata chain (DIF-33) ---------------------------------------------------------------

META_Q = "which tables can I query about loan applications"


def _metadata_run(registry, skill_ctx, results, principal=None):
    skill_out = registry.invoke(
        "metadata-answerer",
        None,
        {"query": META_Q},
        skill_ctx(results=results, who=principal or who("analyst")),
    )
    steps = {
        "route": step(
            {"label": "metadata_question", "intent": "metadata_question", "path_preference": "kag"}
        ),
        "metadata_answer": step(skill_out),
    }
    return skill_out, steps


def test_a_metadata_question_is_answered_without_sql(registry, skill_ctx):
    results = InMemoryResultStore()
    ctx = skill_ctx(results=results, who=who("analyst"))
    skill_out, steps = _metadata_run(registry, skill_ctx, results)
    out = compose(registry, ctx, steps, question=META_Q)
    assert out["status"] == "answered"
    assert out["query"]["sql"] is None  # no SQL was generated or executed
    assert out["row_count"] == skill_out["row_count"] > 0
    assert out["result_ref"]["ref"].startswith("mem-")
    assert out["narrative"].startswith("Schema information you can access:")
    assert {p["table"] for p in out["provenance"]} == set(skill_out["tables"])
    assert out["confidence"]["signals"]["path"] == "metadata"


def test_a_metadata_question_with_no_entitled_table_abstains(registry, skill_ctx):
    results = InMemoryResultStore()
    ctx = skill_ctx(results=results, who=who("nobody"))
    _, steps = _metadata_run(registry, skill_ctx, results, principal=who("nobody"))
    out = compose(registry, ctx, steps, question=META_Q)
    assert out["status"] == "abstained"
    assert out["reason"]["code"] == "nothing_retrievable"


def test_a_score_below_the_threshold_abstains_with_hints(registry, skill_ctx, synthetic_profile):
    results = InMemoryResultStore()
    out = compose(
        registry, skill_ctx(results=results), full_run(registry, skill_ctx, results, score=0.4)
    )
    assert out["status"] == "abstained"
    assert out["reason"]["code"] == "low_confidence"
    assert out["confidence"]["score"] == 0.4
    assert out["result_ref"] is None
    assert "approval rate" in out["reason"]["hints"]
    assert synthetic_profile.confidence_threshold > 0.4


def test_escalation_after_rows_abstains(registry, skill_ctx):
    results = InMemoryResultStore()
    out = compose(
        registry,
        skill_ctx(results=results),
        full_run(registry, skill_ctx, results, label="escalate", score=0.5),
        attempt=2,
    )
    assert out["status"] == "abstained"
    assert out["reason"]["code"] == "low_confidence_after_refines"
    assert out["refine"]["attempts"] == 2


# ---- the early exits --------------------------------------------------------------------------


def test_denied_by_the_router(registry, skill_ctx):
    out = compose(
        registry,
        skill_ctx(who=who("stranger")),
        {"route": step({"label": "denied", "reason": "access:no_role_in_app"})},
    )
    assert out["status"] == "denied"
    assert out["reason"]["code"] == "no_role_in_app"
    assert out["reason"]["hints"] == []


def test_out_of_scope_offers_example_questions(registry, skill_ctx, synthetic_profile):
    out = compose(
        registry,
        skill_ctx(),
        {"route": step({"label": "out_of_scope", "reason": "rules:off_topic"})},
    )
    assert out["status"] == "out_of_scope"
    assert out["reason"]["code"] == "rules:off_topic"
    assert out["reason"]["message"].endswith("tests.")  # one full stop
    assert out["reason"]["hints"][0] in synthetic_profile.router.exemplars["data_query"]  # type: ignore[index]


def test_needs_clarification_asks_a_question_with_options(registry, skill_ctx):
    out = compose(
        registry,
        skill_ctx(),
        {"route": step({"label": "needs_clarification", "reason": "rules:too_short"})},
    )
    assert out["status"] == "needs_clarification"
    assert out["clarification"]["question"]
    assert "approval rate" in out["clarification"]["options"]


def test_an_empty_sliver_abstains(registry, skill_ctx):
    steps = {
        "route": step({"label": "data_query"}),
        "sliver": step(
            {
                "label": "empty",
                "sliver": {
                    "tables": [],
                    "coverage": 0,
                    "path_used": "bypass",
                    "catalog_version": "v",
                },
                "path_used": "bypass",
            }
        ),
    }
    out = compose(registry, skill_ctx(), steps)
    assert out["status"] == "abstained"
    assert out["reason"]["code"] == "nothing_retrievable"


def test_an_unusable_query_abstains_with_the_generators_reason(registry, skill_ctx):
    steps = {
        "route": step({"label": "data_query"}),
        "sliver": sliver_step(registry, skill_ctx),
        "generate": step({"label": "unusable", "reason": "validation_failed_after_repairs"}),
    }
    out = compose(registry, skill_ctx(), steps)
    assert out["status"] == "abstained"
    assert out["reason"]["code"] == "validation_failed_after_repairs"


@pytest.mark.parametrize(
    ("exec_status", "status", "code"),
    [
        ("policy_denied", "denied", "policy_denied"),
        ("access_denied", "denied", "access_denied"),
        ("timeout", "failed", "timeout"),
    ],
)
def test_terminal_executor_outcomes(registry, skill_ctx, exec_status, status, code):
    steps = {
        "route": step({"label": "data_query"}),
        "sliver": sliver_step(registry, skill_ctx),
        "generate": step({"label": "generated", "sql": "SELECT 1", "dialect": "postgres"}),
        "execute": step(
            {
                "label": exec_status,
                "status": exec_status,
                "result_ref": None,
                "row_count": None,
                "columns": [],
            }
        ),
    }
    out = compose(registry, skill_ctx(), steps)
    assert out["status"] == status
    assert out["reason"]["code"] == code
    assert out["reason"]["hints"] == []


def test_a_query_error_that_was_never_fixed_fails(registry, skill_ctx):
    steps = {
        "route": step({"label": "data_query"}),
        "sliver": sliver_step(registry, skill_ctx),
        "generate": step({"label": "generated", "sql": "SELECT 1", "dialect": "postgres"}),
        "execute": step(
            {
                "label": "error",
                "status": "error",
                "result_ref": None,
                "row_count": None,
                "columns": [],
                "detail": "database error (database, 22012)",
            }
        ),
        "assess": step({"label": "escalate", "score": 0.0, "signals": {}}),
    }
    out = compose(registry, skill_ctx(), steps, attempt=2)
    assert out["status"] == "failed"
    assert out["reason"]["code"] == "query_error"


def test_a_run_that_stopped_early_is_failed_not_answered(registry, skill_ctx):
    out = compose(registry, skill_ctx(), {"route": step({"label": "data_query"})})
    assert out["status"] == "failed"
    assert out["reason"]["code"] == "incomplete_run"


# ---- bad input -------------------------------------------------------------------------------


def test_missing_containers_fail_before_the_skill_runs(registry, skill_ctx):
    with pytest.raises(SkillError) as exc:
        registry.invoke(NAME, None, {"question": "q", "steps": {}}, skill_ctx())
    assert exc.value.phase == "input"


def test_wrong_types_are_skill_errors(registry, skill_ctx):
    with pytest.raises(SkillError) as exc:
        registry.invoke(NAME, None, {"question": "q", "steps": [], "refine": {}}, skill_ctx())
    assert exc.value.phase == "execution"


# ---- the narrative ---------------------------------------------------------------------------


def _narrate_on(synthetic_profile):
    policy = ModelPolicy(
        enabled=True,
        model_group="fast",
        temperature=0.2,
        max_tokens=400,
        rows_in_prompt="masked_sample",
        max_sample_rows=2,
    )
    return synthetic_profile.model_copy(
        update={"model_policy": {**synthetic_profile.model_policy, Purpose.NARRATE: policy}}
    )


def test_the_narrative_sees_a_small_masked_sample_marked_as_rows(
    registry, skill_ctx, synthetic_profile, repo
):
    provider = FakeProvider(load_fixtures(repo / "tests" / "fixtures" / "llm"), record_calls=True)
    gateway = LLMGateway(provider, model_for=lambda g: f"fake-{g}")
    results = InMemoryResultStore()
    ctx = skill_ctx(results=results, gateway=gateway, app=_narrate_on(synthetic_profile))
    rows = (("Synthetic Member 00042", 0.5), ("auto", 0.6), ("mortgage", 0.7))
    out = compose(registry, ctx, full_run(registry, skill_ctx, results, rows=rows))
    assert out["status"] == "answered"
    assert out["narrative"].startswith("Approval rates differ")
    call = provider.calls[0]
    user = next(m for m in call.messages if m.role == "user")
    assert user.contains_rows is True
    assert call.no_store is True
    assert "Synthetic Member 00042" not in user.content  # identifying text is masked
    assert "***" in user.content
    assert "auto" in user.content  # a short category value stays
    assert "mortgage" not in user.content  # only max_sample_rows rows
    assert "Rows in total: 3" in user.content


def test_a_failed_narrative_never_fails_the_answer(registry, skill_ctx, synthetic_profile):
    gateway = LLMGateway(FakeProvider([]), model_for=lambda g: f"fake-{g}")
    results = InMemoryResultStore()
    emitted: list = []
    ctx = skill_ctx(
        results=results, gateway=gateway, app=_narrate_on(synthetic_profile), emitted=emitted
    )
    out = compose(registry, ctx, full_run(registry, skill_ctx, results))
    assert out["status"] == "answered"
    assert out["narrative"] is None
    assert ("narrative_unavailable", None) in emitted
