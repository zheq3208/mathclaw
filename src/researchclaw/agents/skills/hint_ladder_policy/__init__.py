"""Hint ladder skill tools."""


def register():
    from ...tools.math_learning import choose_hint_level

    return {"choose_hint_level": choose_hint_level}
