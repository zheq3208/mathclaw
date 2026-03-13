"""Difficulty calibrator skill tools."""


def register():
    from ...tools.math_reasoning import calibrate_problem_difficulty

    return {"calibrate_problem_difficulty": calibrate_problem_difficulty}
