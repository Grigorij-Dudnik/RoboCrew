"""Load RoboCrew skills from SKILL.md folders."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re


def load_skills(skill_names, skills_dir=None, context=None):
    prompts = []
    tools = []

    for skill_name in skill_names:
        prompt, skill_tools = load_skill(skill_name, skills_dir=skills_dir, context=context)
        prompts.append(prompt)
        tools.extend(skill_tools)

    return "\n\n".join(prompts), tools


def load_skill(skill_name, skills_dir=None, context=None):
    skill_dir = Path(skill_name)
    if not skill_dir.exists() and skills_dir is not None:
        skill_dir = Path(skills_dir) / str(skill_name)
    prompt = _read_skill_md(skill_dir / "SKILL.md")
    return prompt, _load_skill_tools(skill_dir, context)


def _read_skill_md(path):
    text = path.read_text(encoding="utf-8").strip()
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].strip()
    return text


def _load_skill_tools(skill_dir, context):
    tools_path = skill_dir / "tools.py"
    if not tools_path.exists():
        return []

    module_name = "robocrew_skill_" + re.sub(r"\W+", "_", str(skill_dir.resolve()))
    spec = spec_from_file_location(module_name, tools_path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.create_tools(context))
