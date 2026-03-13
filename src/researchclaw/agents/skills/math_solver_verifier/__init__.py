"""Math solver verifier skill tools."""


def register():
    from ...tools.math_reasoning import verify_math_solution

    return {"verify_math_solution": verify_math_solution}
