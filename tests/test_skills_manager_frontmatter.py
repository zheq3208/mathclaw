from pathlib import Path

from researchclaw.agents.skills_manager import _parse_skill_md, _read_skill_info


def test_parse_skill_md_yaml_frontmatter() -> None:
    text = (
        "---\n"
        "name: browser_visible\n"
        "description: launch visible browser\n"
        "triggers:\n"
        "  - visible browser\n"
        "  - headed\n"
        "---\n\n"
        "# Skill\n"
    )
    meta = _parse_skill_md(text)
    assert meta.get("name") == "browser_visible"
    assert meta.get("description") == "launch visible browser"
    triggers = meta.get("triggers")
    assert isinstance(triggers, list)
    assert "headed" in triggers


def test_parse_skill_md_bullet_fallback() -> None:
    text = (
        "- name: cron\n"
        "- description: schedule jobs\n"
        "- triggers: cron, schedule\n"
    )
    meta = _parse_skill_md(text)
    assert meta.get("name") == "cron"
    assert meta.get("description") == "schedule jobs"



def test_read_skill_info_generated_flags(tmp_path: Path) -> None:
    skill_dir = tmp_path / "creator-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        'name: "Creator Skill"\n'
        "description: generated skill\n"
        "generated: true\n"
        "deletable: true\n"
        "created_by: skill_creator\n"
        "categories:\n"
        "  - 讲解\n"
        "  - 练习\n"
        "---\n\n"
        "# Role\n",
        encoding="utf-8",
    )

    info = _read_skill_info(skill_dir, source="customized")
    assert info.generated is True
    assert info.deletable is True
    assert info.created_by == "skill_creator"
    assert info.categories == ["讲解", "练习"]
    assert info.name == "Creator Skill"
