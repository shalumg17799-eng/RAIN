"""Every skill has an agent spec, and spec metadata agrees with the skill's manifest."""

import unittest
from pathlib import Path

from insights.runtime.skill_agent import load_skill_agent_spec
from insights.skills_core.registry import SkillRegistry

ROOT = Path(__file__).resolve().parents[1]


class EverySkillHasAnAgentSpec(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = SkillRegistry.scan(ROOT / "skills")

    def test_spec_exists_loads_and_matches_the_manifest(self) -> None:
        for name in self.registry.names():
            skill = self.registry.get(name)
            with self.subTest(skill=name):
                spec_path = ROOT / "agents" / str(skill.pack) / "skills" / f"{name}.yaml"
                self.assertTrue(spec_path.is_file(), f"missing agent spec {spec_path}")
                spec = load_skill_agent_spec(spec_path)
                self.assertEqual(spec.name, name)
                self.assertEqual(spec.pack, skill.pack)
                self.assertEqual(spec.kind, skill.manifest.kind)
                self.assertEqual(spec.stage, skill.manifest.stage)

    def test_deterministic_specs_name_no_model_surface(self) -> None:
        for name in self.registry.names():
            skill = self.registry.get(name)
            if skill.manifest.kind != "deterministic":
                continue
            spec = load_skill_agent_spec(
                ROOT / "agents" / str(skill.pack) / "skills" / f"{name}.yaml"
            )
            with self.subTest(skill=name):
                self.assertIsNone(spec.purpose)
                self.assertEqual(spec.token_budget, 0)
                self.assertFalse(spec.has_agent_loop)

    def test_agentic_specs_configure_a_full_loop(self) -> None:
        for name in self.registry.names():
            skill = self.registry.get(name)
            if skill.manifest.kind != "agentic":
                continue
            spec = load_skill_agent_spec(
                ROOT / "agents" / str(skill.pack) / "skills" / f"{name}.yaml"
            )
            with self.subTest(skill=name):
                self.assertTrue(spec.has_agent_loop)
                self.assertGreaterEqual(spec.token_budget, 1000)
                self.assertTrue((ROOT / str(spec.prompt)).is_file(), spec.prompt)


if __name__ == "__main__":
    unittest.main()
