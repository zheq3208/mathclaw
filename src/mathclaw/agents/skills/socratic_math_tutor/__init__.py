"""Socratic math tutor skill tools."""


def register():
    from ...tools.guided_explanation_q3vl import (
        compose_guided_explanation_turn,
        generate_socratic_turn,
    )

    return {
        "compose_guided_explanation_turn": compose_guided_explanation_turn,
        "generate_socratic_turn": generate_socratic_turn,
    }
