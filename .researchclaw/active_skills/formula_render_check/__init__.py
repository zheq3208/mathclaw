"""Formula render check skill tools."""


def register():
    from ...tools.math_reasoning import check_formula_render_issues

    return {"check_formula_render_issues": check_formula_render_issues}
