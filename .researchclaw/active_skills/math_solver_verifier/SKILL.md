---
name: math_solver_verifier
description: Run the full SolveVerify-Q3VL pipeline for math problems. Use when the system must draft multiple independent solution paths, run exact symbolic checks, compare conflicts, and deliver a verified or review-marked final answer instead of trusting a single draft.
---

# Math Solve And Verify

Use this skill as a four-stage agent system.

## Pipeline

1. Planner: build a stable solving brief and exact-check plan.
2. Dual Solver: generate two independent solution candidates with different prompts.
3. Tool Verifier + Critic: run exact symbolic checks, compare candidates, and find the first conflict.
4. Arbiter/Patcher: produce the final answer, status, and concise student-facing solution.

## Required behavior

- Never trust a single free-form draft.
- Run exact checks before finalizing the answer.
- Mark unresolved cases as `review` or `conflict`.
- Save artifacts for review:
  - `planner.json`
  - `candidates.json`
  - `critic.json`
  - `Solved.md`
  - `VerificationReport.json`
  - `SolutionAudit.json`

## Primary tools

- `build_math_solution_brief`
- `draft_math_solution_candidates`
- `verify_math_solution_candidates`
- `run_math_solve_verify_agent`
- `solve_and_verify_math_problem`
