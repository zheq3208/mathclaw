"""Mastery updater skill tools."""


def register():
    from ...tools.math_learning import (
        get_global_learning_memory,
        get_math_mastery_snapshot,
        mark_global_memory_mastered,
        update_global_learning_memory,
        update_math_mastery,
    )

    return {
        "update_math_mastery": update_math_mastery,
        "get_math_mastery_snapshot": get_math_mastery_snapshot,
        "get_global_learning_memory": get_global_learning_memory,
        "update_global_learning_memory": update_global_learning_memory,
        "mark_global_memory_mastered": mark_global_memory_mastered,
    }
