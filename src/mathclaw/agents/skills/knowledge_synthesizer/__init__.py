"""Knowledge synthesizer skill tools."""


def register():
    from ...tools.math_input import synthesize_problem_brief

    return {"synthesize_problem_brief": synthesize_problem_brief}
