---
name: problem_json_normalizer
description: Normalize raw OCR or user text into a standard math problem JSON structure.
emoji: ""
triggers:
  - problem json
  - normalize problem
  - structured parse
---

# Problem JSON Normalizer

Use this skill to convert raw question input into a consistent `problem_json`.

## Required Fields

- `problem_text`
- `formula_expressions`
- `givens`
- `target`
- `question_type`
- `ocr_confidence`
- `source_regions`

## Rules

- never silently repair uncertain OCR
- keep original text separate from normalized math notation
- leave ambiguous fields explicit instead of guessing
