"""OCR document processor skill tools."""


def register():
    from ...tools.math_input import extract_math_document
    from ...tools.mess_to_clean_q3vl import (
        extract_qwen_box_evidence,
        recover_exam_layout_from_box_evidence,
        run_mess_to_clean_q3vl,
    )

    return {
        "extract_math_document": extract_math_document,
        "extract_qwen_box_evidence": extract_qwen_box_evidence,
        "recover_exam_layout_from_box_evidence": recover_exam_layout_from_box_evidence,
        "run_mess_to_clean_q3vl": run_mess_to_clean_q3vl,
    }
