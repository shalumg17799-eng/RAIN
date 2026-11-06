"""The platform's static invariants, run as tests: pack isolation, gateway-only LLM, registry."""

import unittest
from pathlib import Path

from insights.ci import check_gateway_only_llm, check_pack_isolation, check_registry
from insights.skills_core.registry import SkillRegistry

ROOT = Path(__file__).resolve().parents[1]


class PackIsolation(unittest.TestCase):
    def test_no_pack_references_the_other(self) -> None:
        self.assertEqual(check_pack_isolation(ROOT), [])

    def test_registry_rejects_cross_pack_dependencies(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for pack, name, deps in (
                ("insights", "alpha-skill", "[beta-skill]"),
                ("data", "beta-skill", "[]"),
            ):
                folder = root / pack / name
                (folder / "scripts").mkdir(parents=True)
                (folder / "SKILL.md").write_text(
                    "---\n"
                    f"name: {name}\nversion: 1.0.0\ndescription: x\npack: {pack}\n"
                    f"dependencies: {deps}\n---\nbody\n",
                    encoding="utf-8",
                )
                (folder / "scripts" / "run.py").write_text(
                    "def run(input, ctx):\n    return {}\n", encoding="utf-8"
                )
            registry = SkillRegistry.scan(root)
            self.assertNotIn("alpha-skill", registry.names())
            self.assertIn("beta-skill", registry.names())
            self.assertTrue(
                any("may not reference the other pack" in e.error for e in registry.errors),
                registry.errors,
            )

    def test_registry_rejects_pack_mismatch(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "insights" / "gamma-skill"
            (folder / "scripts").mkdir(parents=True)
            (folder / "SKILL.md").write_text(
                "---\nname: gamma-skill\nversion: 1.0.0\ndescription: x\npack: data\n---\nbody\n",
                encoding="utf-8",
            )
            (folder / "scripts" / "run.py").write_text(
                "def run(input, ctx):\n    return {}\n", encoding="utf-8"
            )
            registry = SkillRegistry.scan(root)
            self.assertNotIn("gamma-skill", registry.names())
            self.assertTrue(any("declares pack" in e.error for e in registry.errors))


class GatewayOnlyLlm(unittest.TestCase):
    def test_no_direct_sdk_imports(self) -> None:
        self.assertEqual(check_gateway_only_llm(ROOT), [])


class RegistryHealth(unittest.TestCase):
    def test_both_packs_scan_clean_with_full_metadata(self) -> None:
        self.assertEqual(check_registry(ROOT), [])

    def test_pack_listing(self) -> None:
        registry = SkillRegistry.scan(ROOT / "skills")
        self.assertEqual(registry.packs(), ["data", "insights"])
        self.assertIn("skill-router", registry.names("insights"))
        self.assertIn("requirements-interpreter", registry.names("data"))
        self.assertNotIn("skill-router", registry.names("data"))
        self.assertEqual(registry.pack_of("governed-executor"), "insights")
        self.assertEqual(registry.pack_of("build-data-map"), "data")


if __name__ == "__main__":
    unittest.main()
