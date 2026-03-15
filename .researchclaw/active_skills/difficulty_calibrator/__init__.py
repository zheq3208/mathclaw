"""Difficulty calibrator skill tools."""


def register():
    from ...tools.variant_generation_q3vl import calibrate_problem_difficulty

    return {"calibrate_problem_difficulty": calibrate_problem_difficulty}
