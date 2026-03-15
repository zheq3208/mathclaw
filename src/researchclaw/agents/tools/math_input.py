"""Input, OCR-adjacent, and problem normalization tools for math workflows."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Optional

from ...constant import WORKING_DIR
from .math_utils import (
    dedupe_list,
    extract_math_expressions,
    infer_target,
    map_problem_structure,
    normalize_problem_text,
)
from .mess_to_clean_q3vl import (
    extract_math_document as q3_extract_math_document,
    extract_qwen_box_evidence,
    recover_exam_layout_from_box_evidence,
    render_pdf_pages_for_ocr,
    run_mess_to_clean_q3vl,
)
from .paper_reader import read_paper


def _resolve_source_path(source: str) -> Path:
    path = Path(source)
    if path.is_absolute():
        return path
    return Path(WORKING_DIR) / source


def read_pdf_document(
    source: str,
    max_pages: Optional[int] = None,
    extract_references: bool = False,
) -> dict[str, Any]:
    """Read a PDF document from a local path or URL."""
    result = read_paper(
        source=source,
        extract_references=extract_references,
        max_pages=max_pages,
    )
    if isinstance(result, dict):
        result["document_type"] = "pdf"
    return result


def inspect_math_media(source: str, max_pages: int = 2) -> dict[str, Any]:
    """Inspect an uploaded image or PDF and return usable metadata."""
    path = _resolve_source_path(source)
    if not path.exists():
        return {"error": f"File not found: {path}"}

    suffix = path.suffix.lower()
    mime_type = mimetypes.guess_type(path.name)[0] or ""

    if suffix == ".pdf":
        pdf = read_pdf_document(str(path), max_pages=max_pages)
        rendered = render_pdf_pages_for_ocr(str(path), max_pages=max_pages)
        text = str(pdf.get("text", ""))
        return {
            "media_type": "pdf",
            "path": str(path),
            "page_count": pdf.get("page_count", 0),
            "mime_type": mime_type or "application/pdf",
            "has_extractable_text": bool(text.strip()),
            "text_preview": text[:2000],
            "formula_candidates": extract_math_expressions(text),
            "ocr_ready_page_count": rendered.get("page_count", 0),
            "rendered_pages": rendered.get("rendered_pages", []),
            "ocr_pipeline": "MessToClean-Q3VL",
        }

    try:
        from PIL import Image
    except ImportError:
        return {"error": "Pillow is not available in the runtime."}

    with Image.open(path) as image:
        result: dict[str, Any] = {
            "media_type": "image",
            "path": str(path),
            "mime_type": mime_type or "image/png",
            "format": image.format or "",
            "width": image.width,
            "height": image.height,
            "mode": image.mode,
            "ocr_pipeline": "MessToClean-Q3VL",
            "ocr_available": True,
            "ocr_text_preview": "",
        }
        return result


def extract_math_document(
    source: str,
    max_pages: int = 3,
    mode: str = "full",
    max_questions: Optional[int] = None,
) -> dict[str, Any]:
    """Run the MessToClean-Q3VL OCR pipeline on a math image or PDF."""
    return q3_extract_math_document(
        source=source,
        max_pages=max_pages,
        mode=mode,
        max_questions=max_questions,
    )


def analyze_visual_math_context(
    source: str = "",
    extracted_text: str = "",
    note: str = "",
) -> dict[str, Any]:
    """Analyze whether a problem depends on diagrams, tables, or visual layout."""
    combined = normalize_problem_text(
        "\n".join(item for item in [extracted_text, note] if item)
    )
    tags: list[str] = []
    lowered = combined.lower()
    if any(token in lowered for token in ("triangle", "circle", "?", "??", "?")):
        tags.append("geometry_figure")
    if any(
        token in lowered for token in ("graph", "??", "??", "slope", "??")
    ):
        tags.append("coordinate_graph")
    if any(token in lowered for token in ("table", "??", "??", "???")):
        tags.append("table_or_chart")
    if combined.count("(") >= 2 and combined.count(")") >= 2:
        tags.append("multi_part_layout")

    result = {
        "visual_tags": dedupe_list(tags),
        "recommended_next_tools": [
            "extract_qwen_box_evidence",
            "recover_exam_layout_from_box_evidence",
            "normalize_problem_json",
        ],
    }
    if source:
        result["media_inspection"] = inspect_math_media(source)
    return result


def synthesize_problem_brief(
    problem_text: str,
    givens: Optional[list[str]] = None,
    target: str = "",
    formulas: Optional[list[str]] = None,
    student_context: str = "",
) -> dict[str, Any]:
    """Synthesize a compact reasoning brief before solving."""
    normalized = normalize_problem_text(problem_text)
    structure = map_problem_structure(normalized)
    final_givens = dedupe_list(list(givens or []))
    if not final_givens:
        final_givens = [line.strip() for line in normalized.split("\n") if line.strip()][
            :3
        ]
    final_formulas = dedupe_list(
        list(formulas or []) or extract_math_expressions(normalized)
    )
    final_target = target.strip() or infer_target(normalized)
    return {
        "problem_statement": normalized,
        "givens": final_givens,
        "target": final_target,
        "formulas": final_formulas,
        "question_type": structure["question_type"],
        "knowledge_points": structure["knowledge_points"],
        "ambiguities": [],
        "student_context": student_context.strip(),
        "recommended_next_tools": [
            "normalize_problem_json",
            "sympy_solve_equation",
            "verify_math_solution",
        ],
    }


def normalize_problem_json(
    problem_text: str,
    ocr_confidence: Optional[float] = None,
    source_regions: Optional[list[dict[str, Any]]] = None,
    student_note: str = "",
) -> dict[str, Any]:
    """Normalize raw text into a structured problem JSON payload."""
    normalized = normalize_problem_text(problem_text)
    structure = map_problem_structure(normalized)
    formulas = extract_math_expressions(normalized)
    target = infer_target(normalized)
    givens = [line.strip() for line in normalized.split("\n") if line.strip()]
    ocr_flags = []
    if "??" in normalized or "?" in normalized:
        ocr_flags.append("contains_question_mark_like_uncertainty")
    if any(token in normalized for token in ("O", "0", "l", "1")):
        ocr_flags.append("contains_easy_to_confuse_symbols")

    return {
        "problem_text": normalized,
        "formula_expressions": formulas,
        "givens": givens[:6],
        "target": target,
        "question_type": structure["question_type"],
        "ocr_confidence": ocr_confidence,
        "source_regions": source_regions or [],
        "chapter": structure["chapter"],
        "knowledge_points": structure["knowledge_points"],
        "prerequisites": structure["prerequisites"],
        "difficulty_band": structure["difficulty_band"],
        "ocr_risk_flags": dedupe_list(ocr_flags),
        "student_note": student_note.strip(),
    }

# === SIMPLE_MATH_INPUT_OVERRIDE_20260315 ===
def extract_math_document(
    source: str,
    max_pages: int = 3,
    mode: str = "full",
    max_questions: Optional[int] = None,
    original_prompt: str = "",
) -> dict[str, Any]:
    return q3_extract_math_document(
        source=source,
        max_pages=max_pages,
        mode=mode,
        max_questions=max_questions,
        original_prompt=original_prompt,
    )



# === SIMPLE_MATH_INPUT_OVERRIDE_20260315B ===
def extract_math_document(
    source: str,
    max_pages: int = 3,
    mode: str = "full",
    max_questions: Optional[int] = None,
    original_prompt: str = "",
) -> dict[str, Any]:
    from . import mess_to_clean_q3vl as _ocr_module
    return _ocr_module.extract_math_document(
        source=source,
        max_pages=max_pages,
        mode=mode,
        max_questions=max_questions,
        original_prompt=original_prompt,
    )

