"""metadata-answerer: facts about the schema/glossary, entitlement-bound, by reference, no SQL."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from insights.contracts.guards import assert_no_rows
from insights.contracts.principal import Principal
from insights.contracts.state import ResultRef
from insights.skills_core.registry import SkillRegistry

NAME = "metadata-answerer"


@pytest.fixture(scope="module")
def registry(repo: Path) -> SkillRegistry:
    reg = SkillRegistry.scan(repo / "skills")
    assert NAME in reg.names(), reg.errors
    return reg


def who(*roles: str) -> Principal:
    return Principal(subject="u-meta", tenant="t", roles=roles, entitlement_digest="a" * 64)


def answer(registry, skill_ctx, query, **extra):
    ctx_kwargs = {k: extra.pop(k) for k in ("who", "app", "emitted", "results") if k in extra}
    return registry.invoke(NAME, None, {"query": query, **extra}, skill_ctx(**ctx_kwargs))


def test_a_metadata_question_returns_entitled_schema_facts_by_reference(registry, skill_ctx):
    out = answer(registry, skill_ctx, "what does approval rate mean in the loan application tables")
    assert out["label"] == "answered"
    assert out["path_used"] == "bypass"  # no KAG configured in the unit fixtures
    assert [c["name"] for c in out["columns"]] == ["aspect", "name", "detail"]
    assert out["row_count"] > 0
    assert set(out["tables"]) <= {"loan_application", "loan_product", "member", "branch"}
    assert "loan_application" in out["tables"]
    assert out["narrative"].startswith("Schema information you can access:")
    # rows live only by reference -- the skill output itself never carries any
    assert "rows" not in out
    assert_no_rows(out, "metadata-answerer output")


def test_the_facts_are_held_in_the_result_store(registry, skill_ctx):
    held: list = []
    from insights.runtime.stores import InMemoryResultStore

    store = InMemoryResultStore()
    out = answer(
        registry,
        skill_ctx,
        "which tables and columns can I query about loan applications",
        who=who("analyst"),
        results=store,
        emitted=held,
    )
    ref = ResultRef(**out["result_ref"])
    stored = store.get(ref, owner="u-meta")
    assert len(stored.rows) == out["row_count"]
    assert any(row[0] == "table" for row in stored.rows)
    assert any(row[0] == "column" for row in stored.rows)
    assert ("rows_held", out["row_count"]) in held


def test_a_caller_with_no_entitled_table_gets_empty_not_a_leak(registry, skill_ctx):
    # a role the app does not know -> no entitled tables -> empty, never revealing hidden tables
    out = answer(registry, skill_ctx, "which tables can I query", who=who("nobody"))
    assert out["label"] == "empty"
    assert out["tables"] == []
    assert "result_ref" not in out


def test_the_output_is_plain_json_and_matches_the_manifest(registry, skill_ctx):
    out = answer(registry, skill_ctx, "what columns are in the loan application table")
    manifest = registry.get(NAME).manifest
    assert set(manifest.validation.required_output) <= set(out)
    assert out["label"] in manifest.labels
    json.dumps(out)


def test_a_non_text_query_is_rejected(registry, skill_ctx):
    from insights.skills_core.errors import SkillError

    with pytest.raises(SkillError):
        registry.invoke(NAME, None, {"query": ["not", "text"]}, skill_ctx())
