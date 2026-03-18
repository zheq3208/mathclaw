"""Hint ladder skill tools."""


def register():
    from ...tools.guided_explanation_q3vl import choose_hint_level

    return {"choose_hint_level": choose_hint_level}
