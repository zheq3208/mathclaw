---
name: pdf
description: Render and inspect math PDFs before OCR. Use when a worksheet, scan, handout, or exam paper arrives as PDF and the OCR agent needs page images, page order, or layout-preserving intake.
---

# PDF Intake For OCR

Use this skill as Stage 0 for MessToClean-Q3VL.

## Workflow

1. Detect whether the PDF already has extractable text.
2. Render pages to images for OCR evidence extraction.
3. Keep page numbers and rendered image paths for later question crops.
4. Hand page images to `ocr_document_processor`.

## Primary tools

- `read_pdf_document`
- `render_pdf_pages_for_ocr`
