from researchclaw.app.services.skill_creator import (
    _coerce_json_object,
    _infer_categories,
    _normalize_skill_payload,
)


def test_coerce_json_object_from_fenced_payload() -> None:
    payload = _coerce_json_object(
        '```json\n{"skills": [{"title": "Equation Coach", "description": "Guide equations", "markdown": "# Role\nHelp"}]}\n```',
    )
    assert payload["skills"][0]["title"] == "Equation Coach"


def test_normalize_skill_payload_adds_frontmatter_and_unique_slugs() -> None:
    payload = {
        "skills": [
            {
                "title": "Equation Coach",
                "description": "Guide linear equations",
                "markdown": "---\nname: Old\n---\n# Role\nTeach carefully",
            },
            {
                "title": "Equation Coach",
                "description": "Guide harder equations",
                "markdown": "# Role\nCheck mastery",
            },
        ],
    }

    drafts = _normalize_skill_payload(
        payload,
        requirements="Need a teacher-facing equation tutoring workflow",
        model_name="qwen/qwen3-vl-8b-instruct",
        existing_slugs={"equation-coach"},
    )

    assert [draft.slug for draft in drafts] == [
        "equation-coach-2",
        "equation-coach-3",
    ]
    assert drafts[0].markdown.startswith("---\n")
    assert "generated: true" in drafts[0].markdown
    assert 'name: "Equation Coach"' in drafts[0].markdown
    assert "# Role" in drafts[0].markdown


def test_infer_categories_from_requirement() -> None:
    categories = _infer_categories("错题讲解与复习提醒")
    assert "讲解" in categories
    assert "复习" in categories
