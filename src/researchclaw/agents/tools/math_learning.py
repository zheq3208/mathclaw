"""Curriculum, tutoring, memory, and mastery tools for math workflows."""

from __future__ import annotations

import json
import math
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4
from zoneinfo import ZoneInfo

from ...constant import MEMORY_DIR
from .cron_jobs import cron_create_job, cron_delete_job, cron_list_jobs
from .math_utils import (
    build_method_tags,
    dedupe_list,
    extract_numbers,
    map_problem_structure,
    normalize_problem_text,
)


def _math_memory_dir() -> Path:
    path = Path(MEMORY_DIR) / "math_learning"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _quiz_dir() -> Path:
    path = _math_memory_dir() / "micro_quizzes"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso_now() -> str:
    return _utc_now().isoformat().replace("+00:00", "Z")


def _render_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(round(value, 4))


def _normalize_answer_text(text: str) -> str:
    return re.sub(r"\s+", "", normalize_problem_text(text)).lower()


def _safe_int(value: float, default: int) -> int:
    candidate = int(round(abs(value))) if value else default
    return candidate if candidate > 0 else default


def _resolve_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo((name or "UTC").strip() or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def _quiz_file(quiz_id: str) -> Path:
    return _quiz_dir() / f"{quiz_id}.json"


def _review_registry_path() -> Path:
    return _math_memory_dir() / "review_reminders.json"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def map_problem_to_curriculum(problem_text: str, grade_hint: str = "") -> dict[str, Any]:
    """Map a problem to chapter, knowledge points, prerequisites, and difficulty."""
    structure = map_problem_structure(problem_text)
    structure["grade_hint"] = grade_hint.strip()
    structure["recommended_review_window_days"] = (
        1 if structure["difficulty_band"] == "hard" else 3
    )
    return structure


def diagnose_math_weakness(
    problem_text: str,
    student_answer: str = "",
    correct_answer: str = "",
    error_description: str = "",
    grade_hint: str = "",
) -> dict[str, Any]:
    """Diagnose likely weak points and error causes for a math problem."""
    curriculum = map_problem_to_curriculum(problem_text, grade_hint)
    causes: list[str] = []
    detail = normalize_problem_text(error_description).lower()
    if any(token in detail for token in ("审题", "看错", "读错", "抄错", "reading")):
        causes.append("reading_or_prompt_misread")
    if any(token in detail for token in ("粗心", "careless", "符号", "sign")):
        causes.append("careless_or_sign_error")
    if not causes and student_answer and correct_answer:
        try:
            student_numbers = extract_numbers(student_answer)
            correct_numbers = extract_numbers(correct_answer)
            if student_numbers and correct_numbers:
                if len(student_numbers) == len(correct_numbers) and all(
                    abs(a + b) < 1e-9 for a, b in zip(student_numbers, correct_numbers)
                ):
                    causes.append("sign_error")
                elif any(
                    abs(a - b) > 0 for a, b in zip(student_numbers, correct_numbers)
                ):
                    causes.append("calculation_error")
        except Exception:
            pass
    if not causes and curriculum["question_type"] in {"equation", "algebra"}:
        causes.append("symbolic_manipulation_gap")
    if not causes and curriculum["question_type"] == "geometry":
        causes.append("diagram_interpretation_gap")
    if not causes:
        causes.append("concept_gap")

    return {
        "chapter": curriculum["chapter"],
        "knowledge_point": curriculum["knowledge_points"][0],
        "prerequisites": curriculum["prerequisites"],
        "difficulty": curriculum["difficulty_band"],
        "likely_error_causes": dedupe_list(causes),
        "question_type": curriculum["question_type"],
    }


def plan_guided_explanation(
    problem_text: str,
    student_attempt: str = "",
    learning_goal: str = "",
    hint_level: int = 1,
) -> dict[str, Any]:
    """Plan a guided explanation instead of directly exposing the full answer."""
    structure = map_problem_structure(problem_text)
    level = max(1, min(int(hint_level), 4))
    focus = {
        1: "help the student notice what the problem is asking",
        2: "point at the breakthrough idea or setup",
        3: "reveal one intermediate step only",
        4: "allow a full worked explanation",
    }[level]
    return {
        "hint_level": level,
        "question_type": structure["question_type"],
        "teacher_focus": focus,
        "next_message_template": (
            f"Ask one focused question about {structure['knowledge_points'][0]} "
            "before revealing more detail."
        ),
        "student_attempt_summary": student_attempt.strip(),
        "learning_goal": learning_goal.strip(),
        "avoid": "Do not jump straight to the final answer unless hint_level is 4.",
    }


def generate_socratic_turn(
    problem_text: str,
    student_attempt: str = "",
    latest_student_reply: str = "",
    hint_level: int = 1,
) -> dict[str, Any]:
    """Generate the next Socratic tutoring turn for a math problem."""
    structure = map_problem_structure(problem_text)
    level = max(1, min(int(hint_level), 4))
    if level == 1:
        question = "先用你自己的话说一下，这道题到底要求什么？"
        action = "restate_goal"
    elif level == 2:
        question = (
            f"这题最关键的突破口更像是 {structure['knowledge_points'][0]} 的哪一步？"
        )
        action = "identify_breakthrough"
    elif level == 3:
        question = "如果只写第一步，你会先列什么式子或条件？"
        action = "write_first_step"
    else:
        question = "现在可以给你完整讲解。先确认你想看完整解答还是关键步骤版？"
        action = "confirm_full_solution"
    return {
        "hint_level": level,
        "question": question,
        "expected_student_action": action,
        "student_attempt": student_attempt.strip(),
        "latest_student_reply": latest_student_reply.strip(),
    }


def choose_hint_level(
    current_level: int = 1,
    attempts: int = 0,
    requested_full_solution: bool = False,
    student_progress: str = "",
) -> dict[str, Any]:
    """Choose the next hint level for a tutoring interaction."""
    current = max(1, min(int(current_level), 4))
    if requested_full_solution:
        next_level = 4
        reason = "student_requested_full_solution"
    elif attempts >= 3 and current < 4:
        next_level = current + 1
        reason = "multiple_attempts_without_progress"
    elif student_progress.strip():
        next_level = current
        reason = "student_is_making_progress"
    else:
        next_level = current
        reason = "hold_current_hint_level"
    return {
        "current_level": current,
        "next_level": next_level,
        "reason": reason,
    }


def remember_student_fact(
    student_id: str,
    fact: str,
    category: str = "general",
    tags: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Persist a durable student fact such as a weak point or preference."""
    record = {
        "student_id": student_id,
        "fact": fact.strip(),
        "category": category.strip() or "general",
        "tags": tags or [],
        "created_at": _iso_now(),
    }
    _append_jsonl(_math_memory_dir() / "student_facts.jsonl", record)
    return record


def list_student_facts(student_id: str, category: str = "") -> list[dict[str, Any]]:
    """List remembered facts for a given student."""
    path = _math_memory_dir() / "student_facts.jsonl"
    if not path.exists():
        return []
    results: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("student_id") != student_id:
            continue
        if category and record.get("category") != category:
            continue
        results.append(record)
    return results


def extract_math_knowledge(
    problem_text: str,
    solution_summary: str = "",
    error_description: str = "",
) -> dict[str, Any]:
    """Extract knowledge-point and method metadata from a math problem."""
    structure = map_problem_structure(problem_text)
    error_tags: list[str] = []
    normalized_error = error_description.lower()
    if "粗心" in normalized_error or "careless" in normalized_error:
        error_tags.append("careless")
    if "审题" in normalized_error or "reading" in normalized_error:
        error_tags.append("reading")
    if "计算" in normalized_error or "calculation" in normalized_error:
        error_tags.append("calculation")
    return {
        "chapter": structure["chapter"],
        "knowledge_points": structure["knowledge_points"],
        "method_tags": build_method_tags(problem_text + "\n" + solution_summary),
        "error_tags": dedupe_list(error_tags),
        "prerequisite_concepts": structure["prerequisites"],
    }


def _result_delta(result: str) -> float:
    mapping = {
        "correct": 0.12,
        "quiz_pass": 0.15,
        "hinted": 0.04,
        "partial": 0.02,
        "incorrect": -0.10,
        "quiz_fail": -0.12,
    }
    return mapping.get(result, 0.0)


def _next_review_days(score: float) -> int:
    if score < 0.25:
        return 1
    if score < 0.5:
        return 3
    if score < 0.7:
        return 7
    if score < 0.85:
        return 14
    return 30


def update_math_mastery(
    student_id: str,
    knowledge_point: str,
    result: str,
    evidence: Optional[list[str]] = None,
    note: str = "",
) -> dict[str, Any]:
    """Update persistent mastery state after solving or review."""
    state_path = _math_memory_dir() / "mastery_state.json"
    state = _load_json(state_path, {})
    student_state = state.setdefault(student_id, {})
    record = student_state.setdefault(
        knowledge_point,
        {
            "score": 0.5,
            "history_count": 0,
            "last_result": "",
            "next_review_at": "",
        },
    )
    old_score = float(record.get("score", 0.5))
    new_score = max(0.0, min(1.0, round(old_score + _result_delta(result), 3)))
    review_at = (
        _utc_now() + timedelta(days=_next_review_days(new_score))
    ).isoformat().replace("+00:00", "Z")

    record.update(
        {
            "score": new_score,
            "history_count": int(record.get("history_count", 0)) + 1,
            "last_result": result,
            "last_note": note.strip(),
            "next_review_at": review_at,
            "updated_at": _iso_now(),
        }
    )
    _write_json(state_path, state)
    event = {
        "student_id": student_id,
        "knowledge_point": knowledge_point,
        "before_score": old_score,
        "after_score": new_score,
        "result": result,
        "evidence": evidence or [],
        "note": note.strip(),
        "created_at": _iso_now(),
        "next_review_at": review_at,
    }
    _append_jsonl(_math_memory_dir() / "mastery_events.jsonl", event)
    return event


def get_math_mastery_snapshot(
    student_id: str,
    knowledge_point: str = "",
) -> dict[str, Any]:
    """Read the current mastery snapshot for a student."""
    state = _load_json(_math_memory_dir() / "mastery_state.json", {})
    student_state = state.get(student_id, {})
    if knowledge_point:
        return {
            "student_id": student_id,
            "knowledge_point": knowledge_point,
            "record": student_state.get(knowledge_point, {}),
        }
    return {
        "student_id": student_id,
        "knowledge_points": student_state,
    }


def _coerce_quiz_count(count: int) -> int:
    try:
        parsed = int(count)
    except Exception:
        parsed = 3
    return max(2, min(parsed, 3))


def _build_equation_quiz_items(
    problem_text: str,
    count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    numbers = extract_numbers(problem_text)
    a = _safe_int(numbers[0] if len(numbers) > 0 else 2, 2)
    solution = _safe_int(numbers[1] if len(numbers) > 1 else 2, 2)
    b = int(round(numbers[2])) if len(numbers) > 2 else 3
    c = a * solution + b
    x_eval = solution + 1
    offset = max(1, solution)

    items = [
        {
            "item_id": "q1",
            "prompt": f"????{a}x + {b} = {c}",
            "skill_focus": "linear_equation",
            "expected_format": "x = value",
            "estimated_minutes": 1,
        },
        {
            "item_id": "q2",
            "prompt": f"? x = {x_eval} ??{a}x + {b} ??????",
            "skill_focus": "substitution",
            "expected_format": "number",
            "estimated_minutes": 1,
        },
        {
            "item_id": "q3",
            "prompt": f"???{a}(x + {offset}) - {a}x",
            "skill_focus": "expression_simplification",
            "expected_format": "number or simplified expression",
            "estimated_minutes": 1,
        },
    ]
    key = [
        {
            "item_id": "q1",
            "answer": _render_number(solution),
            "accepted_answers": [
                _render_number(solution),
                f"x={_render_number(solution)}",
                f"x = {_render_number(solution)}",
            ],
            "expected_number": float(solution),
            "check_type": "numeric",
            "rationale": "Solve the linear equation by isolating x.",
        },
        {
            "item_id": "q2",
            "answer": _render_number(a * x_eval + b),
            "accepted_answers": [_render_number(a * x_eval + b)],
            "expected_number": float(a * x_eval + b),
            "check_type": "numeric",
            "rationale": "Substitute the given x value into the expression.",
        },
        {
            "item_id": "q3",
            "answer": _render_number(a * offset),
            "accepted_answers": [_render_number(a * offset)],
            "expected_number": float(a * offset),
            "check_type": "numeric",
            "rationale": "Distribute and combine like terms.",
        },
    ]
    return items[:count], key[:count]


def _build_function_quiz_items(
    problem_text: str,
    count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    numbers = extract_numbers(problem_text)
    slope = _safe_int(numbers[0] if len(numbers) > 0 else 2, 2)
    intercept = int(round(numbers[1])) if len(numbers) > 1 else 1
    x_value = _safe_int(numbers[2] if len(numbers) > 2 else 3, 3)
    y_value = slope * x_value + intercept
    target_y = y_value + slope
    target_x = x_value + 1

    items = [
        {
            "item_id": "q1",
            "prompt": f"?????? y = {slope}x + {intercept}?? x = {x_value} ??y ?????",
            "skill_focus": "linear_function",
            "expected_format": "number",
            "estimated_minutes": 1,
        },
        {
            "item_id": "q2",
            "prompt": f"?? y = {slope}x + {intercept} ???????",
            "skill_focus": "slope_intercept",
            "expected_format": "number",
            "estimated_minutes": 1,
        },
        {
            "item_id": "q3",
            "prompt": f"? y = {target_y}????? y = {slope}x + {intercept} ? x ?????",
            "skill_focus": "inverse_substitution",
            "expected_format": "number",
            "estimated_minutes": 1,
        },
    ]
    key = [
        {
            "item_id": "q1",
            "answer": _render_number(y_value),
            "accepted_answers": [_render_number(y_value)],
            "expected_number": float(y_value),
            "check_type": "numeric",
            "rationale": "Evaluate the function by substitution.",
        },
        {
            "item_id": "q2",
            "answer": _render_number(slope),
            "accepted_answers": [_render_number(slope)],
            "expected_number": float(slope),
            "check_type": "numeric",
            "rationale": "The slope is the coefficient of x.",
        },
        {
            "item_id": "q3",
            "answer": _render_number(target_x),
            "accepted_answers": [_render_number(target_x)],
            "expected_number": float(target_x),
            "check_type": "numeric",
            "rationale": "Set the function equal to the target y and solve for x.",
        },
    ]
    return items[:count], key[:count]


def _build_geometry_quiz_items(
    problem_text: str,
    count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    numbers = extract_numbers(problem_text)
    angle_a = _safe_int(numbers[0] if len(numbers) > 0 else 50, 50)
    angle_b = _safe_int(numbers[1] if len(numbers) > 1 else 60, 60)
    if angle_a + angle_b >= 175:
        angle_a, angle_b = 50, 60
    length = _safe_int(numbers[2] if len(numbers) > 2 else 6, 6)
    width = _safe_int(numbers[3] if len(numbers) > 3 else 4, 4)
    third_angle = 180 - angle_a - angle_b
    perimeter = 2 * (length + width)
    area = length * width / 2

    items = [
        {
            "item_id": "q1",
            "prompt": f"????????????? {angle_a}? ? {angle_b}????????????",
            "skill_focus": "triangle_properties",
            "expected_format": "number",
            "estimated_minutes": 1,
        },
        {
            "item_id": "q2",
            "prompt": f"???????? {length}??? {width}?????????",
            "skill_focus": "perimeter",
            "expected_format": "number",
            "estimated_minutes": 1,
        },
        {
            "item_id": "q3",
            "prompt": f"???????? {length}??? {width}???????",
            "skill_focus": "area_calculation",
            "expected_format": "number",
            "estimated_minutes": 1,
        },
    ]
    key = [
        {
            "item_id": "q1",
            "answer": _render_number(third_angle),
            "accepted_answers": [_render_number(third_angle)],
            "expected_number": float(third_angle),
            "check_type": "numeric",
            "rationale": "The interior angles of a triangle sum to 180 degrees.",
        },
        {
            "item_id": "q2",
            "answer": _render_number(perimeter),
            "accepted_answers": [_render_number(perimeter)],
            "expected_number": float(perimeter),
            "check_type": "numeric",
            "rationale": "Use 2 x (length + width).",
        },
        {
            "item_id": "q3",
            "answer": _render_number(area),
            "accepted_answers": [_render_number(area)],
            "expected_number": float(area),
            "check_type": "numeric",
            "rationale": "Use base x height / 2.",
        },
    ]
    return items[:count], key[:count]


def _build_statistics_quiz_items(
    problem_text: str,
    count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_numbers = extract_numbers(problem_text)
    if len(raw_numbers) < 3:
        raw_numbers = [2, 4, 6]
    values = [float(raw_numbers[0]), float(raw_numbers[1]), float(raw_numbers[2])]
    ordered = sorted(values)
    mean_value = sum(values) / len(values)
    median_value = ordered[1]
    range_value = ordered[-1] - ordered[0]
    dataset = "?".join(_render_number(value) for value in values)

    items = [
        {
            "item_id": "q1",
            "prompt": f"?? {dataset} ????????",
            "skill_focus": "mean_and_average",
            "expected_format": "number",
            "estimated_minutes": 1,
        },
        {
            "item_id": "q2",
            "prompt": f"?? {dataset} ????????",
            "skill_focus": "median",
            "expected_format": "number",
            "estimated_minutes": 1,
        },
        {
            "item_id": "q3",
            "prompt": f"?? {dataset} ???????",
            "skill_focus": "range",
            "expected_format": "number",
            "estimated_minutes": 1,
        },
    ]
    key = [
        {
            "item_id": "q1",
            "answer": _render_number(mean_value),
            "accepted_answers": [_render_number(mean_value)],
            "expected_number": float(mean_value),
            "check_type": "numeric",
            "rationale": "Average equals total divided by count.",
        },
        {
            "item_id": "q2",
            "answer": _render_number(median_value),
            "accepted_answers": [_render_number(median_value)],
            "expected_number": float(median_value),
            "check_type": "numeric",
            "rationale": "Sort the data and take the middle value.",
        },
        {
            "item_id": "q3",
            "answer": _render_number(range_value),
            "accepted_answers": [_render_number(range_value)],
            "expected_number": float(range_value),
            "check_type": "numeric",
            "rationale": "Range equals max minus min.",
        },
    ]
    return items[:count], key[:count]


def _build_number_theory_quiz_items(
    problem_text: str,
    count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    numbers = extract_numbers(problem_text)
    a = _safe_int(numbers[0] if len(numbers) > 0 else 12, 12)
    b = _safe_int(numbers[1] if len(numbers) > 1 else 18, 18)
    gcd_value = math.gcd(a, b)
    lcm_value = math.lcm(a, b)
    quotient = lcm_value // a

    items = [
        {
            "item_id": "q1",
            "prompt": f"? {a} ? {b} ???????",
            "skill_focus": "greatest_common_divisor",
            "expected_format": "number",
            "estimated_minutes": 1,
        },
        {
            "item_id": "q2",
            "prompt": f"? {a} ? {b} ???????",
            "skill_focus": "least_common_multiple",
            "expected_format": "number",
            "estimated_minutes": 1,
        },
        {
            "item_id": "q3",
            "prompt": f"?? {a} x ? = {lcm_value}?? ? ?????",
            "skill_focus": "factor_relation",
            "expected_format": "number",
            "estimated_minutes": 1,
        },
    ]
    key = [
        {
            "item_id": "q1",
            "answer": _render_number(gcd_value),
            "accepted_answers": [_render_number(gcd_value)],
            "expected_number": float(gcd_value),
            "check_type": "numeric",
            "rationale": "Use common factors or Euclid's algorithm.",
        },
        {
            "item_id": "q2",
            "answer": _render_number(lcm_value),
            "accepted_answers": [_render_number(lcm_value)],
            "expected_number": float(lcm_value),
            "check_type": "numeric",
            "rationale": "Use the relationship with gcd or prime factorization.",
        },
        {
            "item_id": "q3",
            "answer": _render_number(quotient),
            "accepted_answers": [_render_number(quotient)],
            "expected_number": float(quotient),
            "check_type": "numeric",
            "rationale": "Divide the target multiple by the known factor.",
        },
    ]
    return items[:count], key[:count]


def _build_default_quiz_items(
    problem_text: str,
    count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    numbers = extract_numbers(problem_text)
    a = _safe_int(numbers[0] if len(numbers) > 0 else 3, 3)
    b = _safe_int(numbers[1] if len(numbers) > 1 else 4, 4)
    c = _safe_int(numbers[2] if len(numbers) > 2 else 2, 2)
    sum_value = a + b * c
    difference = a * b - c
    fraction = (a + b) / c

    items = [
        {
            "item_id": "q1",
            "prompt": f"???{a} + {b} x {c}",
            "skill_focus": "order_of_operations",
            "expected_format": "number",
            "estimated_minutes": 1,
        },
        {
            "item_id": "q2",
            "prompt": f"???{a} x {b} - {c}",
            "skill_focus": "arithmetic_operations",
            "expected_format": "number",
            "estimated_minutes": 1,
        },
        {
            "item_id": "q3",
            "prompt": f"???({a} + {b}) / {c}",
            "skill_focus": "fraction_and_ratio",
            "expected_format": "number",
            "estimated_minutes": 1,
        },
    ]
    key = [
        {
            "item_id": "q1",
            "answer": _render_number(sum_value),
            "accepted_answers": [_render_number(sum_value)],
            "expected_number": float(sum_value),
            "check_type": "numeric",
            "rationale": "Apply multiplication before addition.",
        },
        {
            "item_id": "q2",
            "answer": _render_number(difference),
            "accepted_answers": [_render_number(difference)],
            "expected_number": float(difference),
            "check_type": "numeric",
            "rationale": "Multiply first, then subtract.",
        },
        {
            "item_id": "q3",
            "answer": _render_number(fraction),
            "accepted_answers": [_render_number(fraction)],
            "expected_number": float(fraction),
            "check_type": "numeric",
            "rationale": "Add first inside the parentheses, then divide.",
        },
    ]
    return items[:count], key[:count]


def _build_micro_quiz(
    problem_text: str,
    question_type: str,
    count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    builder_map = {
        "equation": _build_equation_quiz_items,
        "algebra": _build_equation_quiz_items,
        "function": _build_function_quiz_items,
        "geometry": _build_geometry_quiz_items,
        "statistics": _build_statistics_quiz_items,
        "number_theory": _build_number_theory_quiz_items,
    }
    builder = builder_map.get(question_type, _build_default_quiz_items)
    return builder(problem_text, count)


def generate_micro_quiz(
    problem_text: str,
    knowledge_point: str = "",
    difficulty: str = "auto",
    count: int = 3,
    student_id: str = "",
    include_answer_key: bool = True,
) -> dict[str, Any]:
    """Generate and persist a short 2-3 question mastery-check quiz."""
    structure = map_problem_structure(problem_text)
    quiz_count = _coerce_quiz_count(count)
    items, answer_key = _build_micro_quiz(
        problem_text,
        structure["question_type"],
        quiz_count,
    )
    resolved_knowledge_point = (
        knowledge_point.strip() or structure["knowledge_points"][0]
    )
    resolved_difficulty = (
        structure["difficulty_band"]
        if difficulty.strip().lower() == "auto"
        else difficulty.strip().lower()
    )
    quiz_id = f"mq-{uuid4().hex[:10]}"
    payload = {
        "quiz_id": quiz_id,
        "student_id": student_id.strip(),
        "problem_text": normalize_problem_text(problem_text),
        "question_type": structure["question_type"],
        "knowledge_point": resolved_knowledge_point,
        "difficulty": resolved_difficulty,
        "generated_at": _iso_now(),
        "estimated_minutes": len(items),
        "items": items,
        "answer_key": answer_key,
    }
    _write_json(_quiz_file(quiz_id), payload)

    response = {
        "quiz_id": quiz_id,
        "student_id": payload["student_id"],
        "question_type": payload["question_type"],
        "knowledge_point": resolved_knowledge_point,
        "difficulty": resolved_difficulty,
        "estimated_minutes": len(items),
        "items": items,
    }
    if include_answer_key:
        response["answer_key"] = answer_key
    return response


def _check_micro_quiz_answer(
    answer_spec: dict[str, Any],
    student_answer: str,
) -> dict[str, Any]:
    normalized_student = _normalize_answer_text(student_answer)
    accepted = [
        _normalize_answer_text(item)
        for item in answer_spec.get("accepted_answers", [])
        if str(item).strip()
    ]
    passed = normalized_student in accepted if normalized_student else False
    expected_number = answer_spec.get("expected_number")
    if not passed and expected_number is not None:
        student_numbers = extract_numbers(student_answer)
        if student_numbers:
            passed = abs(float(student_numbers[-1]) - float(expected_number)) <= 1e-6

    if passed:
        feedback = "correct"
    elif answer_spec.get("check_type") == "numeric":
        feedback = f"expected {answer_spec.get('answer', '')}"
    else:
        feedback = "answer does not match the expected form"

    return {
        "correct": passed,
        "feedback": feedback,
        "expected_answer": answer_spec.get("answer", ""),
    }


def grade_micro_quiz(
    quiz_id: str,
    student_answers: Optional[list[str]] = None,
    student_id: str = "",
    update_mastery_record: bool = False,
) -> dict[str, Any]:
    """Grade a persisted micro quiz and optionally update mastery."""
    quiz_record = _load_json(_quiz_file(quiz_id), {})
    if not quiz_record:
        return {"ok": False, "error": f"quiz not found: {quiz_id}"}

    answers = list(student_answers or [])
    per_item: list[dict[str, Any]] = []
    correct_count = 0
    for index, item in enumerate(quiz_record.get("items", [])):
        student_answer = answers[index] if index < len(answers) else ""
        answer_spec = quiz_record.get("answer_key", [])[index]
        checked = _check_micro_quiz_answer(answer_spec, student_answer)
        if checked["correct"]:
            correct_count += 1
        per_item.append(
            {
                "item_id": item.get("item_id", f"q{index + 1}"),
                "prompt": item.get("prompt", ""),
                "student_answer": student_answer,
                "correct": checked["correct"],
                "feedback": checked["feedback"],
                "expected_answer": checked["expected_answer"],
            }
        )

    total = max(len(quiz_record.get("items", [])), 1)
    score = round(correct_count / total, 3)
    result = "quiz_pass" if score >= 0.67 else "quiz_fail"
    resolved_student_id = student_id.strip() or quiz_record.get("student_id", "")

    mastery_event = None
    if update_mastery_record and resolved_student_id:
        mastery_event = update_math_mastery(
            student_id=resolved_student_id,
            knowledge_point=quiz_record.get("knowledge_point", "general_problem_solving"),
            result=result,
            evidence=[f"micro_quiz:{quiz_id}", f"score:{score}"],
            note=f"micro quiz graded with {correct_count}/{total} correct",
        )

    attempt = {
        "quiz_id": quiz_id,
        "student_id": resolved_student_id,
        "knowledge_point": quiz_record.get("knowledge_point", ""),
        "score": score,
        "result": result,
        "correct_count": correct_count,
        "total": total,
        "graded_at": _iso_now(),
        "items": per_item,
    }
    _append_jsonl(_math_memory_dir() / "micro_quiz_attempts.jsonl", attempt)

    return {
        "ok": True,
        "quiz_id": quiz_id,
        "student_id": resolved_student_id,
        "knowledge_point": quiz_record.get("knowledge_point", ""),
        "question_type": quiz_record.get("question_type", "other"),
        "score": score,
        "correct_count": correct_count,
        "total": total,
        "result": result,
        "items": per_item,
        "mastery_event": mastery_event,
    }


def _build_interval_cron(
    frequency_days: int,
    local_hour: int,
    local_minute: int,
) -> tuple[str, str]:
    hour = max(0, min(int(local_hour), 23))
    minute = max(0, min(int(local_minute), 59))
    interval = max(1, int(frequency_days))
    if interval == 1:
        return f"{minute} {hour} * * *", "daily"
    if interval == 7:
        weekday = datetime.now().weekday()
        cron_weekday = [1, 2, 3, 4, 5, 6, 0][weekday]
        return f"{minute} {hour} * * {cron_weekday}", "weekly"
    return f"{minute} {hour} */{interval} * *", "approx_every_n_days"


def _default_review_prompt(
    knowledge_point: str,
    mastery_score: float | None = None,
) -> str:
    score_hint = ""
    if mastery_score is not None:
        score_hint = f"??????? {round(mastery_score, 3)}?"
    return (
        f"?????????? {knowledge_point}?{score_hint}"
        "???????????????????? 1 ??????1 ?????"
        "1 ???? 2 ???????????????????"
    )


def schedule_review_reminder(
    student_id: str,
    knowledge_point: str,
    target_user_id: str = "",
    target_session_id: str = "",
    channel: str = "wecom",
    timezone: str = "Asia/Shanghai",
    local_hour: int = 20,
    local_minute: int = 0,
    frequency_days: int = 0,
    prompt: str = "",
    cron_expression: str = "",
    mode: str = "final",
    replace_existing: bool = True,
    base_url: str = "",
) -> dict[str, Any]:
    """Create a real scheduled review reminder backed by the cron API."""
    sid = student_id.strip()
    kp = knowledge_point.strip()
    if not sid:
        return {"ok": False, "error": "student_id is required"}
    if not kp:
        return {"ok": False, "error": "knowledge_point is required"}

    registry = _load_json(_review_registry_path(), {})
    existing_job_id = ""
    for job_id, record in registry.items():
        if record.get("status") == "cancelled":
            continue
        if record.get("student_id") == sid and record.get("knowledge_point") == kp:
            existing_job_id = job_id
            break

    if existing_job_id and not replace_existing:
        return {
            "ok": False,
            "error": "active reminder already exists",
            "job_id": existing_job_id,
        }

    if existing_job_id and replace_existing:
        cron_delete_job(existing_job_id, base_url=base_url)
        registry[existing_job_id]["status"] = "cancelled"
        registry[existing_job_id]["cancelled_at"] = _iso_now()

    snapshot = get_math_mastery_snapshot(sid, kp).get("record", {})
    mastery_score = snapshot.get("score") if snapshot else None
    parsed_frequency = int(frequency_days or 0)
    interval_days = (
        parsed_frequency
        if parsed_frequency > 0
        else _next_review_days(float(mastery_score if mastery_score is not None else 0.5))
    )
    cron, schedule_mode = (
        (cron_expression.strip(), "custom_cron")
        if cron_expression.strip()
        else _build_interval_cron(interval_days, local_hour, local_minute)
    )

    zone = _resolve_timezone(timezone)
    due_local = datetime.now(zone).replace(
        hour=max(0, min(int(local_hour), 23)),
        minute=max(0, min(int(local_minute), 59)),
        second=0,
        microsecond=0,
    ) + timedelta(days=max(interval_days, 1))

    reminder_prompt = prompt.strip() or _default_review_prompt(
        kp,
        float(mastery_score) if mastery_score is not None else None,
    )
    target_uid = target_user_id.strip() or sid
    target_session = target_session_id.strip() or sid
    job_name = f"math-review::{sid}::{kp}"

    created = cron_create_job(
        name=job_name,
        cron=cron,
        task_type="agent",
        prompt=reminder_prompt,
        channel=channel.strip() or "wecom",
        target_user_id=target_uid,
        target_session_id=target_session,
        timezone=timezone.strip() or "Asia/Shanghai",
        mode=mode,
        enabled=True,
        base_url=base_url,
    )
    if not created.get("ok"):
        return created

    job_spec = created.get("data", {}) if isinstance(created.get("data"), dict) else {}
    job_id = str(job_spec.get("id", "")).strip()
    if not job_id:
        return {
            "ok": False,
            "error": "scheduler did not return a job id",
            "scheduler_response": created,
        }

    registry[job_id] = {
        "student_id": sid,
        "knowledge_point": kp,
        "channel": channel.strip() or "wecom",
        "target_user_id": target_uid,
        "target_session_id": target_session,
        "timezone": timezone.strip() or "Asia/Shanghai",
        "cron": cron,
        "schedule_mode": schedule_mode,
        "frequency_days": interval_days,
        "prompt": reminder_prompt,
        "mastery_score": mastery_score,
        "status": "active",
        "created_at": _iso_now(),
        "due_at_local": due_local.isoformat(),
    }
    _write_json(_review_registry_path(), registry)

    return {
        "ok": True,
        "job_id": job_id,
        "student_id": sid,
        "knowledge_point": kp,
        "cron": cron,
        "schedule_mode": schedule_mode,
        "frequency_days": interval_days,
        "due_at_local": due_local.isoformat(),
        "mastery_score": mastery_score,
        "job": job_spec,
    }


def list_review_reminders(
    student_id: str = "",
    knowledge_point: str = "",
    include_cancelled: bool = False,
    base_url: str = "",
) -> dict[str, Any]:
    """List review reminders from local registry, enriched with scheduler state."""
    registry = _load_json(_review_registry_path(), {})
    jobs_result = cron_list_jobs(base_url=base_url)
    jobs_by_id: dict[str, dict[str, Any]] = {}
    if jobs_result.get("ok"):
        jobs_by_id = {
            str(job.get("id", "")): job
            for job in jobs_result.get("jobs", [])
            if isinstance(job, dict)
        }

    results: list[dict[str, Any]] = []
    for job_id, record in registry.items():
        status = record.get("status", "active")
        if status == "cancelled" and not include_cancelled:
            continue
        if student_id and record.get("student_id") != student_id.strip():
            continue
        if knowledge_point and record.get("knowledge_point") != knowledge_point.strip():
            continue

        merged = dict(record)
        merged["job_id"] = job_id
        scheduler_job = jobs_by_id.get(job_id)
        if scheduler_job:
            merged["job_exists"] = True
            merged["enabled"] = scheduler_job.get("enabled", True)
            merged["schedule"] = scheduler_job.get("schedule", {})
        else:
            merged["job_exists"] = False
            merged["enabled"] = False if status == "cancelled" else None
        results.append(merged)

    results.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return {
        "ok": True,
        "count": len(results),
        "scheduler_ok": jobs_result.get("ok", False),
        "scheduler_error": jobs_result.get("error", ""),
        "reminders": results,
    }


def cancel_review_reminder(job_id: str, base_url: str = "") -> dict[str, Any]:
    """Cancel a scheduled review reminder and mark local metadata inactive."""
    jid = (job_id or "").strip()
    if not jid:
        return {"ok": False, "error": "job_id is required"}

    scheduler_result = cron_delete_job(jid, base_url=base_url)
    registry = _load_json(_review_registry_path(), {})
    metadata_updated = False
    if jid in registry:
        registry[jid]["status"] = "cancelled"
        registry[jid]["cancelled_at"] = _iso_now()
        _write_json(_review_registry_path(), registry)
        metadata_updated = True

    scheduler_ok = bool(scheduler_result.get("ok"))
    if not scheduler_ok and scheduler_result.get("status_code") == 404 and metadata_updated:
        scheduler_ok = True

    return {
        "ok": scheduler_ok,
        "job_id": jid,
        "metadata_updated": metadata_updated,
        "scheduler": scheduler_result,
    }
