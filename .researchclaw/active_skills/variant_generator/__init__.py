"""Variant generator skill tools."""


def register():
    from ...tools.variant_generation_q3vl import (
        build_variant_generation_case,
        draft_problem_variants,
        generate_problem_variants,
        run_problem_variant_agent,
        verify_problem_variants,
    )

    return {
        "build_variant_generation_case": build_variant_generation_case,
        "draft_problem_variants": draft_problem_variants,
        "verify_problem_variants": verify_problem_variants,
        "run_problem_variant_agent": run_problem_variant_agent,
        "generate_problem_variants": generate_problem_variants,
    }
