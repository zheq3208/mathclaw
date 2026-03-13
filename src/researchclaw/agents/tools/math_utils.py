"""Shared helpers for math learning tools."""

from __future__ import annotations

import re
from typing import Any

_OPERATOR_CHARS = "=+-*/^<>≤≥×÷"
_FULLWIDTH_MAP = str.maketrans(
    {
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "｛": "{",
        "｝": "}",
        "，": ",",
        "。": ".",
        "：": ":",
        "；": ";",
        "？": "?",
        "！": "!",
        "＝": "=",
        "－": "-",
        "＋": "+",
        "×": "*",
        "÷": "/",
    }
)
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")

_QUESTION_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "geometry": (
        "triangle",
        "angle",
        "circle",
        "line",
        "point",
        "polygon",
        "三角形",
        "角",
        "圆",
        "直线",
        "线段",
        "平行",
        "垂直",
        "相似",
        "全等",
        "面积",
        "周长",
    ),
    "function": (
        "function",
        "graph",
        "domain",
        "range",
        "slope",
        "intercept",
        "函数",
        "图像",
        "定义域",
        "值域",
        "斜率",
        "截距",
        "单调",
        "一次函数",
        "二次函数",
    ),
    "statistics": (
        "probability",
        "mean",
        "median",
        "mode",
        "variance",
        "sample",
        "概率",
        "平均数",
        "中位数",
        "众数",
        "方差",
        "统计",
        "抽样",
        "频率",
    ),
    "number_theory": (
        "integer",
        "prime",
        "divisor",
        "multiple",
        "gcd",
        "lcm",
        "整数",
        "质数",
        "因数",
        "倍数",
        "约数",
        "公因数",
        "公倍数",
    ),
    "equation": (
        "equation",
        "inequality",
        "solve",
        "root",
        "方程",
        "不等式",
        "解方程",
        "解不等式",
        "方程组",
        "根",
    ),
    "algebra": (
        "factor",
        "expand",
        "simplify",
        "expression",
        "polynomial",
        "fraction",
        "因式分解",
        "展开",
        "化简",
        "代数式",
        "整式",
        "分式",
        "多项式",
    ),
}

_CHAPTER_NAMES = {
    "geometry": "geometry",
    "function": "function",
    "statistics": "statistics_and_probability",
    "number_theory": "number_theory",
    "equation": "equations_and_inequalities",
    "algebra": "algebra",
    "other": "general_math",
}


def normalize_problem_text(text: str) -> str:
    """Normalize whitespace and common fullwidth punctuation."""
    cleaned = (text or "").translate(_FULLWIDTH_MAP)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def dedupe_list(values: list[str]) -> list[str]:
    """Preserve order while removing duplicates and empty strings."""
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def extract_numbers(text: str) -> list[float]:
    """Extract numeric literals from text."""
    numbers: list[float] = []
    for token in _NUMBER_RE.findall(text or ""):
        try:
            numbers.append(float(token))
        except ValueError:
            continue
    return numbers


def extract_math_expressions(text: str, max_items: int = 12) -> list[str]:
    """Extract math-like expressions and formula lines from text."""
    normalized = normalize_problem_text(text)
    matches: list[str] = []

    for item in re.findall(r"\$([^$]+)\$", normalized):
        matches.append(item.strip())

    for line in re.split(r"[\n;]", normalized):
        chunk = line.strip()
        if len(chunk) < 2:
            continue
        has_math_marker = any(op in chunk for op in _OPERATOR_CHARS)
        has_symbol = bool(re.search(r"[A-Za-z]", chunk)) or bool(
            _NUMBER_RE.search(chunk)
        )
        has_math_word = any(
            token in chunk.lower() for token in ("sqrt", "sin", "cos", "tan", "log")
        ) or any(token in chunk for token in ("函数", "方程", "不等式", "根号"))
        if (has_math_marker and has_symbol) or has_math_word:
            matches.append(chunk)

    return dedupe_list(matches)[:max_items]


def infer_target(text: str) -> str:
    """Infer the target request from a problem statement."""
    normalized = normalize_problem_text(text)
    patterns = [
        r"(?:求|求出|求解|解|计算|化简|证明|求证)([^.?!\n]*)",
        r"(?:find|solve|evaluate|prove|determine)([^.?!\n]*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            target = match.group(1).strip(" :")
            if target:
                return target
    segments = re.split(r"[\n.!?]", normalized)
    return segments[-1].strip() if segments else normalized


def infer_question_type(text: str) -> str:
    """Infer a coarse math question type from text."""
    normalized = normalize_problem_text(text).lower()
    best = "other"
    best_score = 0
    for question_type, keywords in _QUESTION_TYPE_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword.lower() in normalized)
        if score > best_score:
            best = question_type
            best_score = score
    if best_score == 0 and "=" in normalized:
        return "equation"
    return best


def infer_knowledge_points(question_type: str, text: str) -> list[str]:
    """Infer knowledge points from question type and keywords."""
    normalized = normalize_problem_text(text).lower()
    points: list[str] = []

    if question_type == "geometry":
        if "三角形" in normalized or "triangle" in normalized:
            points.append("triangle_properties")
        if "圆" in normalized or "circle" in normalized:
            points.append("circle_properties")
        if "面积" in normalized or "area" in normalized:
            points.append("area_calculation")
        if "相似" in normalized or "similar" in normalized:
            points.append("similarity")
    elif question_type == "function":
        if "一次函数" in normalized:
            points.append("linear_function")
        if "二次函数" in normalized:
            points.append("quadratic_function")
        if "图像" in normalized or "graph" in normalized:
            points.append("graph_interpretation")
        if "斜率" in normalized or "slope" in normalized:
            points.append("slope_intercept")
    elif question_type == "statistics":
        if "概率" in normalized or "probability" in normalized:
            points.append("probability_basics")
        if "平均数" in normalized or "mean" in normalized:
            points.append("mean_and_average")
        if "方差" in normalized or "variance" in normalized:
            points.append("variance")
    elif question_type == "number_theory":
        if "质数" in normalized or "prime" in normalized:
            points.append("prime_numbers")
        if "公因数" in normalized or "gcd" in normalized:
            points.append("greatest_common_divisor")
        if "公倍数" in normalized or "lcm" in normalized:
            points.append("least_common_multiple")
    elif question_type == "equation":
        if "方程组" in normalized:
            points.append("system_of_equations")
        elif "二次" in normalized:
            points.append("quadratic_equation")
        elif "不等式" in normalized:
            points.append("inequality_solving")
        else:
            points.append("linear_equation")
    elif question_type == "algebra":
        if "因式分解" in normalized or "factor" in normalized:
            points.append("factorization")
        if "分式" in normalized:
            points.append("rational_expression")
        if "展开" in normalized or "expand" in normalized:
            points.append("polynomial_expansion")
        if "化简" in normalized or "simplify" in normalized:
            points.append("expression_simplification")

    if not points:
        points.append(
            question_type if question_type != "other" else "general_problem_solving"
        )
    return dedupe_list(points)


def infer_prerequisites(question_type: str, knowledge_points: list[str]) -> list[str]:
    """Infer prerequisite concepts from question type and points."""
    prerequisites: list[str] = ["arithmetic_operations"]
    if question_type in {"algebra", "equation", "function"}:
        prerequisites.extend(["integer_operations", "symbolic_manipulation"])
    if question_type == "function":
        prerequisites.append("coordinate_plane")
    if question_type == "geometry":
        prerequisites.extend(["angle_basics", "length_and_area"])
    if question_type == "statistics":
        prerequisites.append("fraction_and_ratio")
    if question_type == "number_theory":
        prerequisites.append("divisibility")
    for point in knowledge_points:
        if "quadratic" in point:
            prerequisites.append("factorization")
        if "system" in point:
            prerequisites.append("linear_equation")
    return dedupe_list(prerequisites)


def estimate_difficulty_score(text: str) -> float:
    """Estimate a coarse difficulty score in the range [1, 5]."""
    normalized = normalize_problem_text(text)
    clauses = [
        item for item in re.split(r"[\n,.!?;]", normalized) if item.strip()
    ]
    expressions = extract_math_expressions(normalized)
    numbers = extract_numbers(normalized)
    question_type = infer_question_type(normalized)
    variable_count = len(set(re.findall(r"[a-zA-Z]", normalized)))

    score = 1.0
    score += min(len(clauses), 6) * 0.2
    score += min(len(expressions), 4) * 0.25
    score += min(max(len(numbers) - 1, 0), 5) * 0.1
    score += min(variable_count, 4) * 0.15
    if question_type in {"geometry", "function", "statistics"}:
        score += 0.4
    if any(
        token in normalized.lower()
        for token in ("证明", "prove", "综合", "classification", "讨论")
    ):
        score += 0.6
    return round(max(1.0, min(score, 5.0)), 2)


def difficulty_band(score: float) -> str:
    """Convert a numeric difficulty score into a band."""
    if score < 2.0:
        return "easy"
    if score < 3.5:
        return "medium"
    return "hard"


def map_problem_structure(text: str) -> dict[str, Any]:
    """Infer reusable curriculum structure from a math problem."""
    normalized = normalize_problem_text(text)
    question_type = infer_question_type(normalized)
    knowledge_points = infer_knowledge_points(question_type, normalized)
    prerequisites = infer_prerequisites(question_type, knowledge_points)
    score = estimate_difficulty_score(normalized)
    return {
        "chapter": _CHAPTER_NAMES.get(question_type, "general_math"),
        "question_type": question_type,
        "knowledge_points": knowledge_points,
        "prerequisites": prerequisites,
        "difficulty_score": score,
        "difficulty_band": difficulty_band(score),
    }


def build_method_tags(text: str) -> list[str]:
    """Infer method tags from problem wording."""
    normalized = normalize_problem_text(text).lower()
    tags: list[str] = []
    if any(token in normalized for token in ("factor", "因式分解")):
        tags.append("factorization")
    if any(token in normalized for token in ("代入", "substitute")):
        tags.append("substitution")
    if any(token in normalized for token in ("图像", "graph")):
        tags.append("graph_analysis")
    if any(token in normalized for token in ("证明", "prove")):
        tags.append("proof")
    if any(token in normalized for token in ("方程", "equation")):
        tags.append("equation_solving")
    if any(token in normalized for token in ("概率", "probability")):
        tags.append("probability_reasoning")
    return dedupe_list(tags)


def replace_numbers_for_variant(
    text: str,
    mode: str,
) -> tuple[str, list[dict[str, str]]]:
    """Create a shallow variant by modifying a few numbers."""
    changes: list[dict[str, str]] = []
    counter = {"value": 0}

    def repl(match: re.Match[str]) -> str:
        original = match.group(0)
        counter["value"] += 1
        if counter["value"] > 3:
            return original
        value = float(original)
        if mode == "easier":
            new_value = (
                max(1.0, value / 2.0) if abs(value) > 4 else max(1.0, value - 1.0)
            )
        elif mode == "harder":
            new_value = (
                value * 2.0 if abs(value) < 10 else value + max(2.0, abs(value) * 0.5)
            )
        else:
            new_value = value + 2.0 if value >= 0 else value - 2.0
        rendered = (
            str(int(new_value))
            if float(new_value).is_integer()
            else str(round(new_value, 2))
        )
        changes.append({"from": original, "to": rendered})
        return rendered

    updated = _NUMBER_RE.sub(repl, text, count=3)
    return updated, changes
