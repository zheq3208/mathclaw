---
name: weakness_diagnoser
description: Diagnose weak points from the current problem, the student's wrong answer, and incomplete reasoning by combining verification evidence, current dialogue, and curriculum mapping.
emoji: ""
triggers:
  - diagnose weakness
  - why did I get this wrong
  - incomplete solution
  - missing step
  - weak point after grading
---

# Weakness Diagnoser

Use this skill after solving, grading, or reviewing a student's attempt.

## Pipeline

1. Build a case brief from the current problem, current dialogue, and any verification report.
2. Critique the student's process: wrong final answer, first conflicting step, or missing step.
3. Map the issue to knowledge points, prerequisites, and practice focus.
4. Produce a teacher-facing diagnosis report instead of a vague label.

## Prefer These Tools

- `run_math_weakness_diagnosis_agent` for the full diagnosis pipeline
- `diagnose_math_weakness` for a compact summary
- `build_math_weakness_case` when you need to inspect the evidence bundle first

## What Good Output Looks Like

- primary weakness
- whether the answer is wrong
- whether the process is incomplete
- missing steps
- prerequisite gaps
- recommended practice focus

## Cross-Session Memory

- After diagnosis, update the global learning memory file with the primary weakness, linked knowledge points, prerequisite gaps, and practice focus.
- Use the same global file across sessions instead of storing isolated per-chat notes.
