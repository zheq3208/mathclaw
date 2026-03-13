"""Socratic math tutor skill tools."""


def register():
    from ...tools.math_learning import generate_socratic_turn

    return {"generate_socratic_turn": generate_socratic_turn}
