"""Guiding users skill tools."""


def register():
    from ...tools.math_learning import plan_guided_explanation

    return {"plan_guided_explanation": plan_guided_explanation}
