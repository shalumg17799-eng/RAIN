"""Checks against the staging PostgreSQL (skipped when it is not reachable)."""
import shutil

import pytest

from factory.apppack import AppPack
from factory.config import APPPACKS_DIR, ROOT
from factory.tools import REGISTRY as T
from factory.tools import RunContext

APP = "zz_pytest"


@pytest.fixture(scope="module")
def ctx():
    from factory.tools.db import connect, ensure_database
    try:
        ensure_database()
    except Exception as exc:
        pytest.skip(f"PostgreSQL not reachable: {exc}")
    pack = AppPack(APP)
    pack.write_json("inputs/data_source.json", {"path": str(ROOT / "examples/rain/data")})
    yield RunContext(pack=pack, agent="data")
    with connect() as conn:
        conn.execute(f"DROP SCHEMA IF EXISTS app_{APP} CASCADE")
    shutil.rmtree(APPPACKS_DIR / APP, ignore_errors=True)


def test_load_query_and_dq(ctx):
    out = T["load_tables"].fn(ctx, tables=[{"file": "Facility.csv", "table": "Facility", "key": "facility_id"}],
                              note="pytest")
    assert out["tables"][0] == {"table": "facility", "rows": 8, "key": "primary key added"}
    assert T["run_sql"].fn(ctx, sql="select count(*) from facility")["rows"] == [[8]]
    assert T["dq_check"].fn(ctx, name="ids", sql="select count(*) from facility where facility_id is null",
                            severity="blocking")["passed"]


def test_new_load_is_a_new_version(ctx):
    T["load_tables"].fn(ctx, tables=[{"file": "Facility.csv", "table": "facility"}], note="again")
    versions = sorted(p.name for p in ctx.pack.path("data").glob("v*"))
    assert len(versions) >= 2
