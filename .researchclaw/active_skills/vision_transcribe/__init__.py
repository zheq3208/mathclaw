"""Vision transcribe skill tools."""


def register():
    from ...tools.math_input import inspect_math_media
    from ...tools.mess_to_clean_q3vl import extract_qwen_box_evidence

    return {
        "inspect_math_media": inspect_math_media,
        "extract_qwen_box_evidence": extract_qwen_box_evidence,
    }
