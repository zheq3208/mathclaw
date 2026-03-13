"""Mastery updater skill tools."""


def register():
    from ...tools.math_learning import get_math_mastery_snapshot, update_math_mastery

    return {
        "update_math_mastery": update_math_mastery,
        "get_math_mastery_snapshot": get_math_mastery_snapshot,
    }
