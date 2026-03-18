from mathclaw.agents.skill_compat import SkillDoc, select_relevant_skills


def test_select_relevant_skills_prefers_executable_tooling() -> None:
    skills = [
        SkillDoc(
            name='math-guidance',
            description='guided math workflow',
            content='# guide',
            path='/tmp/math-guidance/SKILL.md',
            executable=False,
            aliases={'math-guidance', 'math_guidance'},
            keywords={'math', 'equation', 'solve'},
        ),
        SkillDoc(
            name='math-tools',
            description='math tool workflow',
            content='# tools',
            path='/tmp/math-tools/SKILL.md',
            executable=True,
            aliases={'math-tools', 'math_tools'},
            keywords={'math', 'equation', 'solve'},
        ),
    ]

    selected = select_relevant_skills('solve this math equation', skills)
    assert selected[0].name == 'math-tools'
