---
name: ocr_document_processor
description: Run MessToClean-Q3VL for scanned math papers, dirty screenshots, tilted phone photos, and multi-question worksheet pages. Use when OCR must produce box evidence first, then recover question order, figure bindings, and audited Markdown output instead of plain text extraction.
---

# OCR Document Processor

Use this skill as a three-stage OCR agent, not a single transcription step.

## Pipeline

1. Stage 1: extract stable box evidence.
2. Stage 2: recover reading order and question-figure bindings.
3. Stage 3: run Generator, Verifier, and Patcher on question-level crops.

## Required behavior

- Produce box evidence before downstream OCR.
- Keep question boxes, figure boxes, and partial boxes separate.
- Prefer question-level crops over whole-page transcription.
- Preserve uncertainty in the audit log instead of hallucinating missing text.
- Save artifacts for review:
  - `stage1_box_evidence.json`
  - `stage2_layout.json`
  - `Structured.md`
  - `FullAuditLog.json`

## Primary tools

- `extract_qwen_box_evidence`
- `recover_exam_layout_from_box_evidence`
- `run_mess_to_clean_q3vl`
- `extract_math_document`
