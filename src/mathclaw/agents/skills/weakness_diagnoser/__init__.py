"""Weakness diagnoser skill tools."""


def register():
    from ...tools.weakness_diag_q3vl import (
        build_math_weakness_case,
        diagnose_math_weakness,
        draft_math_weakness_candidates,
        run_math_weakness_diagnosis_agent,
        verify_math_weakness_candidates,
    )

    return {
        "build_math_weakness_case": build_math_weakness_case,
        "draft_math_weakness_candidates": draft_math_weakness_candidates,
        "verify_math_weakness_candidates": verify_math_weakness_candidates,
        "run_math_weakness_diagnosis_agent": run_math_weakness_diagnosis_agent,
        "diagnose_math_weakness": diagnose_math_weakness,
    }
