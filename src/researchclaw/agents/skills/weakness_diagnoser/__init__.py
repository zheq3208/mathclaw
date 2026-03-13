"""Weakness diagnoser skill tools."""


def register():
    from ...tools.math_learning import diagnose_math_weakness

    return {"diagnose_math_weakness": diagnose_math_weakness}
