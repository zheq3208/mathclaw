"""PDF skill – math-oriented PDF intake."""


def register():
    """Register math PDF tools."""
    from ...tools.math_input import read_pdf_document

    return {"read_pdf_document": read_pdf_document}
