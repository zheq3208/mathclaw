"""Guided users skill tools."""


def register():
    from ...tools.guided_explanation_q3vl import (
        build_guided_explanation_case,
        draft_guided_explanation_plan,
        plan_guided_explanation,
        run_guided_explanation_agent,
    )

    return {
        "build_guided_explanation_case": build_guided_explanation_case,
        "draft_guided_explanation_plan": draft_guided_explanation_plan,
        "run_guided_explanation_agent": run_guided_explanation_agent,
        "plan_guided_explanation": plan_guided_explanation,
    }
