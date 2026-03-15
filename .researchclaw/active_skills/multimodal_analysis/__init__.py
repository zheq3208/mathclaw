"""Multimodal analysis skill tools."""


def register():
    from ...tools.math_input import analyze_visual_math_context

    return {"analyze_visual_math_context": analyze_visual_math_context}
