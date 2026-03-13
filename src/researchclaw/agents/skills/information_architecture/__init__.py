"""Information architecture skill tools."""


def register():
    from ...tools.math_learning import map_problem_to_curriculum

    return {"map_problem_to_curriculum": map_problem_to_curriculum}
