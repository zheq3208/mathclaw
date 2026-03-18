"""Knowledge extractor skill tools."""


def register():
    from ...tools.math_learning import extract_math_knowledge

    return {"extract_math_knowledge": extract_math_knowledge}
