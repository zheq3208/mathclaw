---
name: vision_transcribe
description: Inspect screenshots, phone photos, and cropped worksheet images before OCR. Use when a math problem arrives as image input and the system must decide whether to run Stage 1 evidence extraction or continue from existing crops.
---

# Vision Intake

Use this skill to decide whether the image is ready for OCR evidence extraction.

## Workflow

1. Inspect format, size, and likely page quality.
2. Decide whether the image should go straight to Stage 1 box extraction.
3. Keep the image path and metadata for downstream OCR.

## Primary tools

- `inspect_math_media`
- `extract_qwen_box_evidence`
