"""PDF skill - PDF intake for OCR and question crops."""


def register():
    from ...tools.math_input import read_pdf_document
    from ...tools.mess_to_clean_q3vl import render_pdf_pages_for_ocr

    return {
        "read_pdf_document": read_pdf_document,
        "render_pdf_pages_for_ocr": render_pdf_pages_for_ocr,
    }
