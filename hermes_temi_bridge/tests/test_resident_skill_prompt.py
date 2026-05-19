import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "hermes_resident_server.py"
SPEC = importlib.util.spec_from_file_location("hermes_resident_server", MODULE_PATH)
resident = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(resident)


class ResidentSkillPromptTests(unittest.TestCase):
    def test_read_single_skill_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "SKILL.md"
            skill.write_text("# Skill One\n\nReturn JSON only.", encoding="utf-8")

            prompt = resident._read_skill_prompt([skill])

        self.assertIn("Preloaded Hermes skills", prompt)
        self.assertIn(skill.as_posix(), prompt)
        self.assertIn("Return JSON only.", prompt)

    def test_read_multiple_skill_prompts_preserves_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.md"
            second = Path(tmp) / "second.md"
            first.write_text("FIRST_SKILL", encoding="utf-8")
            second.write_text("SECOND_SKILL", encoding="utf-8")

            prompt = resident._read_skill_prompt([first, second])

        self.assertLess(prompt.index("FIRST_SKILL"), prompt.index("SECOND_SKILL"))
        self.assertIn(first.as_posix(), prompt)
        self.assertIn(second.as_posix(), prompt)

    def test_missing_skill_path_warns_and_skips(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "existing.md"
            missing = Path(tmp) / "missing.md"
            existing.write_text("EXISTING_SKILL", encoding="utf-8")

            with self.assertLogs(level="WARNING") as logs:
                prompt = resident._read_skill_prompt([missing, existing])

        self.assertIn("EXISTING_SKILL", prompt)
        self.assertIn("does not exist", "\n".join(logs.output))

    def test_resolve_skill_paths_uses_default_when_omitted(self):
        self.assertEqual(resident._resolve_skill_paths(None), resident.DEFAULT_SKILL_PATHS)

    def test_resolve_skill_paths_keeps_repeated_args(self):
        paths = resident._resolve_skill_paths(["a/SKILL.md", "b/SKILL.md"])
        self.assertEqual([path.as_posix() for path in paths], ["a/SKILL.md", "b/SKILL.md"])


if __name__ == "__main__":
    unittest.main()
