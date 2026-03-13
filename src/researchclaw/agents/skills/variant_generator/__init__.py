"""Variant generator skill tools."""


def register():
    from ...tools.math_reasoning import generate_problem_variants

    return {"generate_problem_variants": generate_problem_variants}
