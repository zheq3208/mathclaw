---
name: sympy
description: Use SymPy as the exact runtime inside the solve-and-verify agent. Use when the system needs symbolic solving, simplification, substitution, or equivalence checks before trusting a math answer.
---

# SymPy Runtime

Treat this skill as the deterministic backend for SolveVerify-Q3VL.

## Workflow

1. Convert expressions into SymPy-safe syntax.
2. Solve or simplify exactly.
3. Compare candidate answers and expressions.
4. Surface the first exact mismatch clearly.

## Primary tools

- `sympy_simplify_expression`
- `sympy_solve_equation`
- `sympy_check_equivalence`
