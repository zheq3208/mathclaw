---
name: sympy
description: Use SymPy as a symbolic checker for simplification, solving, factoring, expansion, and equivalence checks.
emoji: ""
triggers:
  - sympy
  - simplify
  - solve equation
  - factor
  - expand
---

# SymPy Quickcheck

Use SymPy to validate algebraic steps instead of trusting prose.

## Workflow

1. Translate the expression into SymPy-safe syntax.
2. Run the exact operation.
3. Compare the symbolic result with the proposed step.
4. Report the first parsing or equivalence failure clearly.

## Script

- `scripts/sympy_quickcheck.py`
