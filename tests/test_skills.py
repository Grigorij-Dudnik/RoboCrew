import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from robocrew.core.skills import load_skill, load_skills


class TestSkills(unittest.TestCase):
    def test_load_skill_reads_skill_md_without_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "example_skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: example\n---\n\n## Instructions\nDo the thing.",
                encoding="utf-8",
            )

            prompt, tools = load_skill(skill_dir)

        self.assertEqual(prompt, "## Instructions\nDo the thing.")
        self.assertEqual(tools, [])

    def test_load_skill_loads_optional_tools(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "example_skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("Use the tool.", encoding="utf-8")
            (skill_dir / "tools.py").write_text(
                "def create_tools(context):\n"
                "    return [context]\n",
                encoding="utf-8",
            )

            prompt, tools = load_skill(skill_dir, context="robot-context")

        self.assertEqual(prompt, "Use the tool.")
        self.assertEqual(tools, ["robot-context"])

    def test_load_skills_resolves_names_from_base_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir)
            first = skills_dir / "first"
            second = skills_dir / "second"
            first.mkdir()
            second.mkdir()
            (first / "SKILL.md").write_text("First prompt.", encoding="utf-8")
            (second / "SKILL.md").write_text("Second prompt.", encoding="utf-8")

            prompt, tools = load_skills(["first", "second"], skills_dir=skills_dir)

        self.assertEqual(prompt, "First prompt.\n\nSecond prompt.")
        self.assertEqual(tools, [])


if __name__ == "__main__":
    unittest.main()
