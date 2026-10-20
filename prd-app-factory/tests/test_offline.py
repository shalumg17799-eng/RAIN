"""Checks that need no database and no model calls."""
from pathlib import Path

import pytest
from pydantic import ValidationError

from factory import tools
from factory.agents import AGENTS
from factory.apppack import Manifest
from factory.conformance import matches
from factory.prd_text import extract
from factory.tools.db import check_select, returns_literal

ROOT = Path(__file__).resolve().parent.parent


def test_every_agent_builds_its_prompt_and_tools():
    for spec in AGENTS.values():
        tools.get(spec.tools)
        prompt = spec.system_prompt()
        for skill in spec.skills + spec.optional_skills:
            assert f'name="{skill}"' in prompt, f"{spec.name}: skill {skill} not loaded"


def test_only_release_agent_can_deploy():
    holders = [a.name for a in AGENTS.values() if "deploy_to_azure" in a.tools]
    assert holders == ["release"]


def test_agents_get_no_write_sql():
    for spec in AGENTS.values():
        assert not {"execute_sql", "run_write_sql"} & set(spec.tools)


def test_sql_guard():
    assert check_select("select count(*) from t") == ["t"]
    for bad in ("delete from t", "select 1", "drop table t", "select 1; select 2 from t"):
        with pytest.raises(ValueError):
            check_select(bad)
    assert returns_literal("select 47 from t")
    assert not returns_literal("select count(*) from t")


def test_conformance_tolerances():
    assert matches(61.4, 61, "percent") and not matches(62, 61, "percent")
    assert matches(47, 47, "count") and not matches(48, 47, "count")
    assert matches(1_405_000, 1_400_000, "currency") and not matches(1_500_000, 1_400_000, "currency")


def test_manifest_rejects_bad_ids_and_dangling_personas():
    base = {"app": {"id": "demo", "name": "D", "domain": "d", "description": "d"},
            "personas": [{"id": "ana", "name": "Ana", "role": "r"}]}
    Manifest.model_validate({**base, "kpis": [{"id": "k1", "persona": "ana", "label": "L", "value": "5", "definition": "d"}]})
    with pytest.raises(ValidationError):
        Manifest.model_validate({**base, "kpis": [{"id": "k1", "persona": "bob", "label": "L", "value": "5", "definition": "d"}]})
    with pytest.raises(ValidationError):
        Manifest.model_validate({**base, "app": {**base["app"], "id": "Bad-Id"}})


def test_prd_extraction_keeps_tables_as_rows():
    text = extract(ROOT / "examples/rain/RAIN_Prototype_Spec_v1.docx")
    assert "Active Pregnancies in Service Area | 126 |" in text
