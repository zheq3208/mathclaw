---
name: mastery_updater
description: Update the student's mastery state after a solve, review, or quiz result.
emoji: ""
triggers:
  - update mastery
  - progress update
  - wrong question archive
---

# Mastery Updater

Use this skill after enough evidence is available.

## Update

- question outcome
- confidence level
- knowledge point deltas
- recommended next review time
- whether the problem stays active in the wrong-question queue

## Cross-Session Memory

- Persist major weakness and mastery signals into one global learning memory file.
- Read the global memory before deciding whether a weak point is already active or improving.
- Prefer updating the existing memory record over creating per-conversation notes.
