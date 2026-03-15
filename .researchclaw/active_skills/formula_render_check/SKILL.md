---
name: formula_render_check
description: Check notation risk before or during solving. Use when OCR, markdown, or latex may have changed a formula's meaning and the solve-and-verify agent needs to know whether symbols are safe to trust.
---

# Formula Risk Gate

Use this skill to guard the solve-and-verify pipeline from notation errors.

## Watch for

- superscripts or subscripts collapsing
- minus sign vs dash
- implicit multiplication ambiguity
- fullwidth punctuation or mixed unicode symbols

## Primary tool

- `check_formula_render_issues`
