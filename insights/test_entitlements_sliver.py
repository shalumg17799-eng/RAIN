"""The sliver never exceeds the caller's entitlements — for any role, any question, any widening."""

import unittest
from pathlib import Path

from insights.catalog.entitlements import normalize_table, role_tables
from insights.catalog.provider import DirectoryCatalogs
from insights.ci import check_datasource_isolation, check_skills_read_only
from insights.contracts.principal import Principal
from insights.contracts.profile import load_app_profile
from insights.contracts.request import AskContext

ROOT = Path(__file__).resolve().parents[1]
APP = load_app_profile(ROOT / "apps" / "rain" / "app.yaml")

QUESTIONS = (
    "How many patients are currently enrolled?",
    "show RPM transmission completeness by ZIP code",
    "how many transport requests are scheduled today",
    "list every claim, provider, facility, medication fill and telehealth session",
)


def principal_with(roles: tuple[str, ...]) -> Principal:
    return Principal(subject="t", tenant="rain", roles=roles, entitlement_digest="0" * 64)


class SliverNeverExceedsEntitlements(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.retriever = DirectoryCatalogs(ROOT / "apps").for_app(APP).retriever

    def test_every_role_only_sees_its_own_tables_and_columns(self) -> None:
        schema = APP.datasources[0].default_schema
        for role in APP.roles:
            entitled = role_tables(APP, role)
            principal = principal_with((role,))
            for question in QUESTIONS:
                for widen in (0, 2):
                    result = self.retriever.retrieve(
                        question, principal, AskContext(), widen=widen
                    )
                    for table in result.tables:
                        key = normalize_table(table.name, schema)
                        with self.subTest(role=role, question=question, table=table.name):
                            self.assertIn(key, entitled, f"{role} is not entitled to {table.name}")
                            access = entitled[key]
                            if access.columns != "*":
                                allowed = {c.lower() for c in access.columns}
                                for column in table.columns:
                                    self.assertIn(column.name.lower(), allowed)

    def test_no_role_means_no_tables(self) -> None:
        result = self.retriever.retrieve(QUESTIONS[0], principal_with(()), AskContext())
        self.assertEqual(result.tables, ())
        self.assertIn("no_access", result.notes)


class CheckedSqlUsesPhysicalTableNames(unittest.TestCase):
    def test_unquoted_camelcase_table_regenerates_quoted(self) -> None:
        """Model-written `FROM Patient` must execute against the quoted physical "Patient"."""
        from insights.catalog.entitlements import allowed_objects
        from insights.contracts.state import SliverColumn, SliverTable
        from insights.policy.denylist import load_denylist
        from insights.policy.l1 import check_sql

        sliver_tables = [
            SliverTable(
                source_id="main",
                name="Patient",
                columns=(SliverColumn(name="patient_id", type="text"),),
            )
        ]
        allowed = allowed_objects(sliver_tables, APP, principal_with(("maria",)))
        outcome = check_sql(
            "SELECT count(*) AS n FROM Patient",
            allowed=allowed,
            app=APP,
            denylist=load_denylist("postgres"),
            max_rows=100,
            row_predicates={},
        )
        self.assertTrue(outcome.allowed, outcome.rules)
        self.assertIn('"Patient"', outcome.sql)


class DataSourceAndWriteIsolation(unittest.TestCase):
    def test_only_the_governed_executor_imports_data_sources(self) -> None:
        self.assertEqual(check_datasource_isolation(ROOT), [])

    def test_skill_code_never_writes_to_disk(self) -> None:
        self.assertEqual(check_skills_read_only(ROOT), [])


if __name__ == "__main__":
    unittest.main()
