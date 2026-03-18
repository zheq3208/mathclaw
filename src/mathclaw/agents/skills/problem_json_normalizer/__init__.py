"""Problem JSON normalizer skill tools."""


def register():
    from ...tools.math_input import normalize_problem_json

    return {"normalize_problem_json": normalize_problem_json}
