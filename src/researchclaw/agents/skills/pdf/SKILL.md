---
name: pdf
description: Process worksheets, scanned handouts, exam papers, and exported problem sets from PDF files. Use when the user uploads a PDF and you need to extract text, page structure, formulas, or image regions before solving a math problem.
emoji: ""
triggers:
  - pdf
  - worksheet
  - handout
  - scan
  - exam paper
---

# PDF Intake For Math Problems

Use this skill when a user provides a PDF containing exercises, worksheets, screenshots exported as PDF, or scanned pages.

## Goals

- extract the problem statement accurately
- preserve page order, region hints, and equation layout when possible
- separate OCR uncertainty from actual math reasoning
- hand off clean text and page references to downstream math skills

## Workflow

1. Check whether the PDF is born-digital or scanned.
2. Extract text page by page.
3. If layout matters, render pages to images first and compare rendered view with extracted text.
4. Keep page number, bounding region hints, and any OCR uncertainty in your notes.
5. When a page contains multiple problems, split them before solving.

## Output Expectations

Prepare structured notes with:
- page index
- problem text
- formulas or symbols that may have OCR risk
- diagram/table presence
- confidence notes for anything ambiguous

## References

- Read `references/openai_upstream.md` for the upstream PDF workflow that this local version was adapted from.
- Use the bundled scripts in `scripts/` if they already fit the task.
