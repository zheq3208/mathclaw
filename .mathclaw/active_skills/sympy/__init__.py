"""SymPy skill tools."""


def register():
    from ...tools.math_reasoning import (
        sympy_check_equivalence,
        sympy_simplify_expression,
        sympy_solve_equation,
    )

    return {
        "sympy_simplify_expression": sympy_simplify_expression,
        "sympy_solve_equation": sympy_solve_equation,
        "sympy_check_equivalence": sympy_check_equivalence,
    }
