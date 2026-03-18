"""Math solver verifier skill tools."""


def register():
    from ...tools.math_reasoning import verify_math_solution
    from ...tools.solve_verify_q3vl import (
        build_math_solution_brief,
        draft_math_solution_candidates,
        run_math_solve_verify_agent,
        solve_and_verify_math_problem,
        verify_math_solution_candidates,
    )

    return {
        "build_math_solution_brief": build_math_solution_brief,
        "draft_math_solution_candidates": draft_math_solution_candidates,
        "verify_math_solution_candidates": verify_math_solution_candidates,
        "run_math_solve_verify_agent": run_math_solve_verify_agent,
        "solve_and_verify_math_problem": solve_and_verify_math_problem,
        "verify_math_solution": verify_math_solution,
    }
