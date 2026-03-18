---
name: guiding_users
description: Run a staged tutoring flow that plans the next hint and writes one guided teacher turn.
emoji: ""
triggers:
  - hint
  - guide me
  - step by step
  - don't give answer
  - learning mode
---

# Guiding Users

Use this skill when the student asks for help without wanting the final answer immediately.

## Pipeline

1. Build a tutoring case from the problem, student attempt, and dialogue context.
2. Plan the next hint with a strict hint ladder.
3. Compose one teacher turn and patch answer leakage before sending it.

## Policy

- default to one checkpoint question per turn
- reveal only the minimum allowed by the current hint level
- escalate only when the student remains stuck
- keep the student in learning mode until they explicitly request the full solution
