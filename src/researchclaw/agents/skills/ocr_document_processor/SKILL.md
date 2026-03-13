---
name: ocr_document_processor
description: Extract text blocks, formulas, and OCR confidence hints from images or PDFs of math problems before solving.
emoji: ""
triggers:
  - ocr
  - scan
  - photo
  - screenshot
---

# OCR Document Processor

Use this skill to extract math problem text from images and PDFs while preserving uncertainty.

## Workflow

1. Extract text by region.
2. Flag low-confidence tokens, especially digits and operators.
3. Preserve reading order and page or region hints.
4. Hand off to `problem_json_normalizer`.

## Upstream Sources

- https://skills.sh/dkyazzentwatwa/chatgpt-skills/ocr-document-processor
- https://github.com/dkyazzentwatwa/chatgpt-skills/tree/main/ocr-document-processor
