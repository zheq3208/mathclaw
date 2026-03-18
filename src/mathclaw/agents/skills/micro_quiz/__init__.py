"""Micro quiz skill tools."""


def register():
    from ...tools.math_learning import generate_micro_quiz, grade_micro_quiz

    return {
        "generate_micro_quiz": generate_micro_quiz,
        "grade_micro_quiz": grade_micro_quiz,
    }
