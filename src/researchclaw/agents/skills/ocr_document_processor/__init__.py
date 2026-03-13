"""OCR document processor skill tools."""


def register():
    from ...tools.math_input import extract_math_document

    return {"extract_math_document": extract_math_document}
