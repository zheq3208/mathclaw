"""Reasoning and verification tools for math workflows."""

from __future__ import annotations

import re
from typing import Any

import sympy as sp

from .math_utils import (
    difficulty_band,
    estimate_difficulty_score,
    extract_numbers,
    infer_question_type,
    replace_numbers_for_variant,
)


def _normalize_expression(expr: str) -> str:
    replacements = {
        "^": "**",
        "×": "*",
        "÷": "/",
        "−": "-",
        "–": "-",
        "＝": "=",
        "，": ",",
        "。": ".",
        "√": "sqrt",
    }
    normalized = (expr or "").strip()
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    normalized = re.sub(r"(?<=\d)(?=[A-Za-z(])", "*", normalized)
    normalized = re.sub(r"(?<=[A-Za-z)])(?=\d)", "*", normalized)
    normalized = re.sub(r"(?<=\))(?=\()", "*", normalized)
    return normalized


def _sympy_locals(variable_names: str = "x,y,z") -> dict[str, Any]:
    names = [item.strip() for item in variable_names.split(",") if item.strip()]
    locals_dict = {name: sp.symbols(name) for name in names}
    locals_dict.update(
        {
            "sqrt": sp.sqrt,
            "sin": sp.sin,
            "cos": sp.cos,
            "tan": sp.tan,
            "log": sp.log,
            "pi": sp.pi,
            "E": sp.E,
        }
    )
    for char in "abcdefghijklmnopqrstuvwxyz":
        locals_dict.setdefault(char, sp.symbols(char))
    return locals_dict


def _parse_expression(expr: str, variable_names: str = "x,y,z") -> sp.Expr:
    normalized = _normalize_expression(expr)
    return sp.sympify(normalized, locals=_sympy_locals(variable_names))


def _parse_equation(
    equation: str,
    variable_names: str = "x,y,z",
) -> tuple[sp.Expr, str]:
    normalized = _normalize_expression(equation)
    if "=" in normalized:
        left, right = normalized.split("=", 1)
        return (
            _parse_expression(left, variable_names)
            - _parse_expression(right, variable_names),
            normalized,
        )
    return _parse_expression(normalized, variable_names), normalized


def _serialize_solution(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_serialize_solution(item) for item in value)
    return str(sp.simplify(value))


def _extract_equation_from_text(problem_text: str) -> str:
    normalized = _normalize_expression(problem_text)
    pattern = r"([A-Za-z0-9_().+\-*/\s]+=[A-Za-z0-9_().+\-*/\s]+)"
    match = re.search(pattern, normalized)
    if match:
        return match.group(1).strip()
    for line in re.split(r"[\n;]", normalized):
        if "=" in line and any(ch.isalpha() for ch in line):
            return line.strip()
    return ""


def _parse_solution_tokens(text: str, variable: str) -> list[str]:
    normalized = _normalize_expression(text)
    segments: list[str] = []
    if f"{variable}=" in normalized.replace(" ", ""):
        pattern = rf"{re.escape(variable)}\s*=\s*([^,;，； ]+)"
        segments.extend(match.group(1) for match in re.finditer(pattern, normalized))
    if not segments:
        segments = re.split(r"[,;，；\s]+", normalized)
    results: list[str] = []
    for segment in segments:
        piece = segment.strip("[]() ")
        if not piece:
            continue
        try:
            results.append(_serialize_solution(_parse_expression(piece, variable)))
        except Exception:
            results.append(piece)
    ordered: list[str] = []
    seen: set[str] = set()
    for item in results:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def sympy_simplify_expression(expression: str) -> dict[str, Any]:
    """Simplify a symbolic expression with SymPy."""
    expr = _parse_expression(expression)
    simplified = sp.simplify(expr)
    return {
        "input": expression,
        "normalized_input": _normalize_expression(expression),
        "simplified": str(simplified),
    }


def sympy_solve_equation(equation: str, variable: str = "x") -> dict[str, Any]:
    """Solve an equation or zero-equality expression with SymPy."""
    expr, normalized = _parse_equation(equation, variable)
    symbol = sp.symbols(variable)
    solutions = sp.solve(expr, symbol)
    return {
        "equation": normalized,
        "variable": variable,
        "solutions": [_serialize_solution(item) for item in solutions],
    }


def sympy_check_equivalence(
    expression_a: str,
    expression_b: str,
    variables: str = "x,y,z",
) -> dict[str, Any]:
    """Check whether two expressions are symbolically equivalent."""
    expr_a = _parse_expression(expression_a, variables)
    expr_b = _parse_expression(expression_b, variables)
    difference = sp.simplify(expr_a - expr_b)
    equivalent = difference == 0
    return {
        "expression_a": _normalize_expression(expression_a),
        "expression_b": _normalize_expression(expression_b),
        "equivalent": bool(equivalent),
        "difference": str(difference),
    }


def verify_math_solution(
    problem_text: str,
    proposed_answer: str,
    expected_answer: str = "",
    variable: str = "x",
) -> dict[str, Any]:
    """Verify a proposed answer against an expected answer or solved equation."""
    equation = _extract_equation_from_text(problem_text)
    expected_solutions: list[str] = []
    notes: list[str] = []

    if expected_answer.strip():
        expected_solutions = _parse_solution_tokens(expected_answer, variable)
    elif equation:
        try:
            solved = sympy_solve_equation(equation, variable)
            expected_solutions = list(solved.get("solutions", []))
        except Exception as exc:
            notes.append(f"failed_to_solve_equation: {exc}")

    proposed_solutions = _parse_solution_tokens(proposed_answer, variable)

    if expected_solutions:
        status = (
            "pass"
            if set(expected_solutions) == set(proposed_solutions)
            else "conflict"
        )
    else:
        status = "uncertain"
        notes.append("no_expected_solution_available")

    return {
        "status": status,
        "equation": equation,
        "variable": variable,
        "expected_solutions": expected_solutions,
        "proposed_solutions": proposed_solutions,
        "notes": notes,
    }


def check_formula_render_issues(formula_text: str) -> dict[str, Any]:
    """Check whether OCR or formatting likely changed formula meaning."""
    replacements = {
        "−": "-",
        "–": "-",
        "×": "*",
        "÷": "/",
        "＝": "=",
    }
    normalized = formula_text or ""
    issues: list[dict[str, str]] = []
    if any(ch in normalized for ch in "⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉"):
        issues.append(
            {
                "type": "unicode_super_subscript",
                "message": "Contains unicode superscript or subscript characters.",
            }
        )
    if any(ch in normalized for ch in "−–"):
        issues.append(
            {
                "type": "dash_variant",
                "message": "Contains a unicode minus-like dash.",
            }
        )
    if any(ch in normalized for ch in "（）：，；【】"):
        issues.append(
            {
                "type": "fullwidth_punctuation",
                "message": "Contains fullwidth punctuation that may confuse parsing.",
            }
        )
    if re.search(r"\d[xyabcmn]", normalized):
        issues.append(
            {
                "type": "implicit_multiplication",
                "message": "Contains implicit multiplication such as 2x.",
            }
        )
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    return {
        "original": formula_text,
        "normalized_formula": normalized,
        "issue_count": len(issues),
        "issues": issues,
    }


def generate_problem_variants(
    problem_text: str,
    question_type: str = "",
    target_skill: str = "",
) -> dict[str, Any]:
    """Generate shallow same-structure, easier, and harder variants."""
    inferred_type = question_type or infer_question_type(problem_text)
    isomorphic_text, isomorphic_changes = replace_numbers_for_variant(
        problem_text,
        "isomorphic",
    )
    easier_text, easier_changes = replace_numbers_for_variant(problem_text, "easier")
    harder_text, harder_changes = replace_numbers_for_variant(problem_text, "harder")

    harder_suffix = {
        "geometry": " Also explain the geometric relationship you used.",
        "function": " Also describe one extra graph property.",
        "statistics": " Also explain what the result means.",
    }.get(inferred_type, " Also verify the final result.")

    return {
        "question_type": inferred_type,
        "target_skill": target_skill,
        "variants": [
            {
                "variant_type": "isomorphic",
                "problem_text": isomorphic_text,
                "changes": isomorphic_changes,
                "intent": "same_concept_same_solution_frame",
            },
            {
                "variant_type": "easier",
                "problem_text": easier_text,
                "changes": easier_changes,
                "intent": "reduced_prerequisite_load",
            },
            {
                "variant_type": "harder",
                "problem_text": harder_text + harder_suffix,
                "changes": harder_changes,
                "intent": "deeper_transfer_or_extra_constraint",
            },
        ],
    }


def calibrate_problem_difficulty(
    problem_text: str,
    reference_problem_text: str = "",
) -> dict[str, Any]:
    """Estimate problem difficulty and compare it with an optional reference."""
    score = estimate_difficulty_score(problem_text)
    result = {
        "score": score,
        "band": difficulty_band(score),
        "signals": {
            "question_type": infer_question_type(problem_text),
            "formula_count": len(re.findall(r"[=<>+\-*/^]", problem_text or "")),
            "number_count": len(extract_numbers(problem_text)),
        },
    }
    if reference_problem_text.strip():
        ref_score = estimate_difficulty_score(reference_problem_text)
        if abs(score - ref_score) < 0.4:
            relation = "about_the_same"
        elif score > ref_score:
            relation = "harder"
        else:
            relation = "easier"
        result["reference"] = {
            "score": ref_score,
            "band": difficulty_band(ref_score),
            "relation": relation,
        }
    return result
