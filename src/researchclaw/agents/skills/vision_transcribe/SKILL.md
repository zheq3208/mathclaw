---
name: vision_transcribe
description: Convert screenshots, phone photos, and cropped problem images into clean math-ready text with explicit OCR uncertainty notes.
emoji: ""
triggers:
  - image input
  - screenshot input
  - photo of problem
---

# Vision Transcribe

Use this skill at the start of image-based problem intake.

## Workflow

1. Read the image visually first.
2. Transcribe the full problem faithfully.
3. Mark uncertain tokens and symbols.
4. Preserve line breaks and region order.
5. Pass the result to `ocr_document_processor` or `problem_json_normalizer`.

## Source References

- https://github.com/openai/skills/tree/main/skills/.curated/transcribe
- https://github.com/openai/skills/tree/main/skills/.curated/screenshot
