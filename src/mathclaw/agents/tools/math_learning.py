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


def _global_learning_memory_path() -> Path:
    return _math_memory_dir() / "global_learning_memory.json"


def _resolve_global_student_key(student_id: str) -> str:
    value = str(student_id or "").strip()
    return value or "__global__"


def _default_global_student_memory(student_key: str) -> dict[str, Any]:
    return {
        "student_id": student_key,
        "updated_at": "",
        "weaknesses": {},
        "mastered_weaknesses": {},
        "knowledge_points": {},
        "mastered_knowledge_points": {},
        "prerequisite_gaps": {},
        "practice_focus": [],
        "recent_events": [],
    }


def _clamp_unit(value: float) -> float:
    return round(max(0.0, min(float(value), 1.0)), 3)


def _global_risk_delta(result: str) -> float:
    mapping = {
        "incorrect": 0.18,
        "quiz_fail": 0.16,
        "partial": 0.08,
        "hinted": 0.04,
        "review": 0.03,
        "correct": -0.12,
        "quiz_pass": -0.14,
    }
    return mapping.get(str(result or "").strip(), 0.0)


def _global_risk_status(score: float) -> str:
    if score >= 0.7:
        return "active"
    if score >= 0.45:
        return "watch"
    if score >= 0.2:
        return "improving"
    return "stable"


def _append_recent_note(existing: list[str], note: str, limit: int = 5) -> list[str]:
    values = [str(note or "").strip()] + [str(item).strip() for item in existing if str(item).strip()]
    return dedupe_list(values)[:limit]


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



def _ensure_global_student_memory_shape(student_memory: dict[str, Any], student_key: str) -> dict[str, Any]:
    merged = _default_global_student_memory(student_key)
    merged.update(student_memory if isinstance(student_memory, dict) else {})
    for key in ("weaknesses", "mastered_weaknesses", "knowledge_points", "mastered_knowledge_points", "prerequisite_gaps"):
        value = merged.get(key)
        if not isinstance(value, dict):
            merged[key] = {}
    if not isinstance(merged.get("practice_focus"), list):
        merged["practice_focus"] = []
    if not isinstance(merged.get("recent_events"), list):
        merged["recent_events"] = []

    for record in merged["knowledge_points"].values():
        if isinstance(record, dict):
            record.setdefault("risk_score", 0.5)
            record.setdefault("status", "watch")
            record.setdefault("history_count", 0)
            record.setdefault("last_result", "")
            record.setdefault("updated_at", "")
            record.setdefault("weakness_links", [])
            record.setdefault("practice_focus", [])
            record.setdefault("mastery_streak", 0)
    for record in merged["mastered_knowledge_points"].values():
        if isinstance(record, dict):
            record.setdefault("risk_score", 0.0)
            record.setdefault("status", "mastered")
            record.setdefault("history_count", 0)
            record.setdefault("last_result", "")
            record.setdefault("updated_at", "")
            record.setdefault("weakness_links", [])
            record.setdefault("practice_focus", [])
            record.setdefault("mastery_streak", 3)
            record.setdefault("mastered_at", record.get("updated_at", ""))
            record.setdefault("archive_reason", "mastered")
    for record in merged["weaknesses"].values():
        if isinstance(record, dict):
            record.setdefault("severity", 0.35)
            record.setdefault("status", "watch")
            record.setdefault("count", 0)
            record.setdefault("last_result", "")
            record.setdefault("last_seen_at", "")
            record.setdefault("knowledge_points", [])
            record.setdefault("prerequisite_gaps", [])
            record.setdefault("practice_focus", [])
            record.setdefault("recent_notes", [])
            record.setdefault("sources", [])
            record.setdefault("mastery_streak", 0)
    for record in merged["mastered_weaknesses"].values():
        if isinstance(record, dict):
            record.setdefault("severity", 0.0)
            record.setdefault("status", "mastered")
            record.setdefault("count", 0)
            record.setdefault("last_result", "")
            record.setdefault("last_seen_at", "")
            record.setdefault("knowledge_points", [])
            record.setdefault("prerequisite_gaps", [])
            record.setdefault("practice_focus", [])
            record.setdefault("recent_notes", [])
            record.setdefault("sources", [])
            record.setdefault("mastery_streak", 3)
            record.setdefault("mastered_at", record.get("last_seen_at", ""))
            record.setdefault("archive_reason", "mastered")
    return merged


def _global_positive_signal(result: str) -> bool:
    return str(result or "").strip() in {"correct", "quiz_pass"}


def _global_negative_signal(result: str) -> bool:
    return str(result or "").strip() in {"incorrect", "quiz_fail", "partial", "hinted", "review", "mastered_reopened"}


def _archive_knowledge_point_if_mastered(
    student_memory: dict[str, Any],
    name: str,
    timestamp: str,
    reason: str,
) -> bool:
    active = student_memory.setdefault("knowledge_points", {})
    mastered = student_memory.setdefault("mastered_knowledge_points", {})
    record = active.get(name)
    if not isinstance(record, dict):
        return False
    if float(record.get("risk_score", 1.0)) > 0.30:
        return False
    if int(record.get("mastery_streak", 0)) < 3:
        return False
    archived = dict(record)
    archived["status"] = "mastered"
    archived["mastered_at"] = timestamp
    archived["archive_reason"] = reason
    archived["risk_score"] = _clamp_unit(min(float(record.get("risk_score", 0.0)), 0.12))
    mastered[name] = archived
    active.pop(name, None)
    return True


def _archive_weakness_if_mastered(
    student_memory: dict[str, Any],
    name: str,
    timestamp: str,
    reason: str,
) -> bool:
    active = student_memory.setdefault("weaknesses", {})
    mastered = student_memory.setdefault("mastered_weaknesses", {})
    record = active.get(name)
    if not isinstance(record, dict):
        return False
    if float(record.get("severity", 1.0)) > 0.28:
        return False
    if int(record.get("mastery_streak", 0)) < 3:
        return False
    archived = dict(record)
    archived["status"] = "mastered"
    archived["mastered_at"] = timestamp
    archived["archive_reason"] = reason
    archived["severity"] = _clamp_unit(min(float(record.get("severity", 0.0)), 0.12))
    mastered[name] = archived
    active.pop(name, None)
    return True


def _revive_mastered_knowledge_point(student_memory: dict[str, Any], name: str) -> None:
    mastered = student_memory.setdefault("mastered_knowledge_points", {})
    active = student_memory.setdefault("knowledge_points", {})
    record = mastered.pop(name, None)
    if isinstance(record, dict):
        revived = dict(record)
        revived.pop("mastered_at", None)
        revived.pop("archive_reason", None)
        revived["status"] = "watch"
        revived["risk_score"] = max(0.34, float(revived.get("risk_score", 0.12)))
        revived["mastery_streak"] = 0
        active[name] = revived


def _revive_mastered_weakness(student_memory: dict[str, Any], name: str) -> None:
    mastered = student_memory.setdefault("mastered_weaknesses", {})
    active = student_memory.setdefault("weaknesses", {})
    record = mastered.pop(name, None)
    if isinstance(record, dict):
        revived = dict(record)
        revived.pop("mastered_at", None)
        revived.pop("archive_reason", None)
        revived["status"] = "watch"
        revived["severity"] = max(0.34, float(revived.get("severity", 0.12)))
        revived["mastery_streak"] = 0
        active[name] = revived


def _match_memory_name(options: dict[str, Any], target: str) -> str:
    raw = str(target or "").strip()
    if not raw:
        return ""
    if raw in options:
        return raw
    normalized = normalize_problem_text(raw).lower()
    for candidate in options:
        candidate_norm = normalize_problem_text(candidate).lower()
        if normalized == candidate_norm:
            return candidate
        if normalized and (normalized in candidate_norm or candidate_norm in normalized):
            return candidate
    return ""


def _infer_memory_quiz_question_type(knowledge_point: str, weaknesses: list[str]) -> str:
    text = normalize_problem_text(" ".join([knowledge_point] + list(weaknesses))).lower()
    if any(token in text for token in ("方程", "equation", "代数", "algebra", "二次", "一次")):
        return "equation"
    if any(token in text for token in ("函数", "function", "slope", "斜率", "图像")):
        return "function"
    if any(token in text for token in ("几何", "triangle", "角", "图形", "geometry")):
        return "geometry"
    if any(token in text for token in ("统计", "average", "mean", "median", "概率", "statistics")):
        return "statistics"
    if any(token in text for token in ("公因数", "倍数", "number theory", "整除", "质因数")):
        return "number_theory"
    return "equation"


def _seed_problem_for_memory_target(knowledge_point: str, question_type: str, weaknesses: list[str]) -> str:
    focus = knowledge_point.strip() or "general problem solving"
    weakness_hint = f" Focus on: {', '.join(weaknesses[:2])}." if weaknesses else ""
    if question_type == "function":
        return f"Practice target: {focus}. Given y = 2x + 1, find y when x = 3 and solve y = 9 for x.{weakness_hint}"
    if question_type == "geometry":
        return f"Practice target: {focus}. In a triangle, two angles are 50 and 60 degrees. Find the third angle and explain the reasoning.{weakness_hint}"
    if question_type == "statistics":
        return f"Practice target: {focus}. For the data set 2, 4, 6, compute the mean, median, and range.{weakness_hint}"
    if question_type == "number_theory":
        return f"Practice target: {focus}. Find the greatest common divisor and least common multiple of 12 and 18.{weakness_hint}"
    return f"Practice target: {focus}. Solve 2x + 3 = 11 and show each algebraic step.{weakness_hint}"


def _resolve_micro_quiz_memory_target(
    *,
    student_id: str,
    problem_text: str,
    requested_knowledge_point: str,
) -> dict[str, Any]:
    structure = map_problem_structure(problem_text)
    default_kp = requested_knowledge_point.strip() or structure["knowledge_points"][0]
    if not student_id.strip():
        return {
            "quiz_source": "current_problem",
            "knowledge_point": default_kp,
            "question_type": structure["question_type"],
            "problem_text": problem_text,
            "weaknesses": [],
            "active_knowledge_point_count": 0,
        }

    memory_payload = get_global_learning_memory(student_id)
    student_memory = memory_payload.get("memory", {}) if isinstance(memory_payload, dict) else {}
    student_memory = _ensure_global_student_memory_shape(
        student_memory if isinstance(student_memory, dict) else {},
        _resolve_global_student_key(student_id),
    )
    knowledge_map = student_memory.get("knowledge_points", {})
    weakness_map = student_memory.get("weaknesses", {})
    active_kp_count = len(knowledge_map)

    explicit_match = _match_memory_name(knowledge_map, default_kp)
    if explicit_match:
        weaknesses = list(knowledge_map.get(explicit_match, {}).get("weakness_links", []))
        question_type = _infer_memory_quiz_question_type(explicit_match, weaknesses)
        return {
            "quiz_source": "global_memory",
            "knowledge_point": explicit_match,
            "question_type": question_type,
            "problem_text": _seed_problem_for_memory_target(explicit_match, question_type, weaknesses),
            "weaknesses": weaknesses[:3],
            "active_knowledge_point_count": active_kp_count,
        }

    if knowledge_map:
        ranked = sorted(
            knowledge_map.items(),
            key=lambda item: (
                -float(item[1].get("risk_score", 0.0)),
                -int(item[1].get("history_count", 0)),
                item[0],
            ),
        )
        kp_name, kp_record = ranked[0]
        weaknesses = list(kp_record.get("weakness_links", []))
        question_type = _infer_memory_quiz_question_type(kp_name, weaknesses)
        return {
            "quiz_source": "global_memory",
            "knowledge_point": kp_name,
            "question_type": question_type,
            "problem_text": _seed_problem_for_memory_target(kp_name, question_type, weaknesses),
            "weaknesses": weaknesses[:3],
            "active_knowledge_point_count": active_kp_count,
        }

    if weakness_map:
        ranked = sorted(
            weakness_map.items(),
            key=lambda item: (
                -float(item[1].get("severity", 0.0)),
                -int(item[1].get("count", 0)),
                item[0],
            ),
        )
        weakness_name, weakness_record = ranked[0]
        linked_kps = list(weakness_record.get("knowledge_points", []))
        kp_name = linked_kps[0] if linked_kps else default_kp
        question_type = _infer_memory_quiz_question_type(kp_name, [weakness_name])
        return {
            "quiz_source": "global_memory",
            "knowledge_point": kp_name,
            "question_type": question_type,
            "problem_text": _seed_problem_for_memory_target(kp_name, question_type, [weakness_name]),
            "weaknesses": [weakness_name],
            "active_knowledge_point_count": active_kp_count,
        }

    return {
        "quiz_source": "current_problem",
        "knowledge_point": default_kp,
        "question_type": structure["question_type"],
        "problem_text": problem_text,
        "weaknesses": [],
        "active_knowledge_point_count": active_kp_count,
    }


def get_global_learning_memory(student_id: str = "") -> dict[str, Any]:
    """Read the cross-session learning memory stored in one global JSON file."""
    path = _global_learning_memory_path()
    payload = _load_json(path, {"version": 1, "updated_at": "", "students": {}})
    students = payload.get("students") if isinstance(payload, dict) else {}
    if not isinstance(students, dict):
        students = {}
    normalized_students = {
        key: _ensure_global_student_memory_shape(value, key)
        for key, value in students.items()
    }
    if student_id.strip():
        student_key = _resolve_global_student_key(student_id)
        memory = normalized_students.get(student_key, _default_global_student_memory(student_key))
        return {
            "memory_path": str(path),
            "student_id": student_key,
            "memory": memory,
            "students": sorted(normalized_students.keys()),
            "updated_at": payload.get("updated_at", "") if isinstance(payload, dict) else "",
        }
    return {
        "memory_path": str(path),
        "students": normalized_students,
        "student_ids": sorted(normalized_students.keys()),
        "updated_at": payload.get("updated_at", "") if isinstance(payload, dict) else "",
    }


def update_global_learning_memory(
    student_id: str = "",
    primary_weakness: str = "",
    secondary_weaknesses: Optional[list[str]] = None,
    knowledge_points: Optional[list[str]] = None,
    prerequisite_gaps: Optional[list[str]] = None,
    practice_focus: Optional[list[str]] = None,
    result: str = "",
    note: str = "",
    evidence: Optional[list[str]] = None,
    source: str = "",
    conversation_id: str = "",
) -> dict[str, Any]:
    """Update the single-file global memory with weakness and review signals."""
    path = _global_learning_memory_path()
    payload = _load_json(path, {"version": 1, "updated_at": "", "students": {}})
    if not isinstance(payload, dict):
        payload = {"version": 1, "updated_at": "", "students": {}}
    students = payload.setdefault("students", {})
    if not isinstance(students, dict):
        students = {}
        payload["students"] = students

    student_key = _resolve_global_student_key(student_id)
    student_memory = _ensure_global_student_memory_shape(
        students.get(student_key, {}),
        student_key,
    )
    students[student_key] = student_memory

    timestamp = _iso_now()
    primary = str(primary_weakness or "").strip()
    weakness_names = dedupe_list(([primary] if primary else []) + [str(item).strip() for item in (secondary_weaknesses or []) if str(item).strip()])
    kp_names = dedupe_list([str(item).strip() for item in (knowledge_points or []) if str(item).strip()])
    gap_names = dedupe_list([str(item).strip() for item in (prerequisite_gaps or []) if str(item).strip()])
    focus_items = dedupe_list([str(item).strip() for item in (practice_focus or []) if str(item).strip()])
    evidence_items = dedupe_list([str(item).strip() for item in (evidence or []) if str(item).strip()])

    delta = _global_risk_delta(result)
    if not result and weakness_names:
        delta = 0.14
    elif not result and kp_names:
        delta = 0.06

    knowledge_map = student_memory.setdefault("knowledge_points", {})
    mastered_knowledge_map = student_memory.setdefault("mastered_knowledge_points", {})
    weakness_map = student_memory.setdefault("weaknesses", {})
    gap_map = student_memory.setdefault("prerequisite_gaps", {})
    student_memory["practice_focus"] = dedupe_list(focus_items + student_memory.get("practice_focus", []))[:12]

    if _global_negative_signal(result) or weakness_names:
        for kp in kp_names:
            if kp in student_memory.get("mastered_knowledge_points", {}):
                _revive_mastered_knowledge_point(student_memory, kp)
        for weakness in weakness_names:
            if weakness in student_memory.get("mastered_weaknesses", {}):
                _revive_mastered_weakness(student_memory, weakness)

    archived_items: dict[str, list[str]] = {"weaknesses": [], "knowledge_points": [], "revived": []}

    for kp in kp_names:
        if _global_positive_signal(result) and kp in mastered_knowledge_map:
            archived = mastered_knowledge_map[kp]
            archived["last_result"] = str(result or archived.get("last_result") or "").strip()
            archived["updated_at"] = timestamp
            archived["mastery_streak"] = int(archived.get("mastery_streak", 3)) + 1
            archived["practice_focus"] = dedupe_list(focus_items + archived.get("practice_focus", []))[:10]
            archived["weakness_links"] = dedupe_list(weakness_names + archived.get("weakness_links", []))[:10]
            continue
        record = knowledge_map.setdefault(
            kp,
            {
                "risk_score": 0.5,
                "status": "watch",
                "history_count": 0,
                "last_result": "",
                "updated_at": "",
                "weakness_links": [],
                "practice_focus": [],
                "mastery_streak": 0,
            },
        )
        base_score = float(record.get("risk_score", 0.5))
        kp_delta = delta if delta else (0.08 if weakness_names else 0.0)
        record["risk_score"] = _clamp_unit(base_score + kp_delta)
        record["status"] = _global_risk_status(record["risk_score"])
        record["history_count"] = int(record.get("history_count", 0)) + 1
        record["last_result"] = str(result or record.get("last_result") or "").strip()
        record["updated_at"] = timestamp
        record["weakness_links"] = dedupe_list(weakness_names + record.get("weakness_links", []))[:10]
        record["practice_focus"] = dedupe_list(focus_items + record.get("practice_focus", []))[:10]
        if _global_positive_signal(result):
            record["mastery_streak"] = int(record.get("mastery_streak", 0)) + 1
        elif _global_negative_signal(result) or weakness_names:
            record["mastery_streak"] = 0
        if _archive_knowledge_point_if_mastered(student_memory, kp, timestamp, "auto_mastered"):
            archived_items["knowledge_points"].append(kp)

    for idx, weakness in enumerate(weakness_names):
        record = weakness_map.setdefault(
            weakness,
            {
                "severity": 0.35,
                "status": "watch",
                "count": 0,
                "last_result": "",
                "last_seen_at": "",
                "knowledge_points": [],
                "prerequisite_gaps": [],
                "practice_focus": [],
                "recent_notes": [],
                "sources": [],
                "mastery_streak": 0,
            },
        )
        weight = 1.0 if idx == 0 else 0.7
        base_delta = delta if delta else 0.14
        severity = _clamp_unit(float(record.get("severity", 0.35)) + (base_delta * weight))
        record["severity"] = severity
        record["status"] = _global_risk_status(severity)
        record["count"] = int(record.get("count", 0)) + 1
        record["last_result"] = str(result or record.get("last_result") or "").strip()
        record["last_seen_at"] = timestamp
        record["knowledge_points"] = dedupe_list(kp_names + record.get("knowledge_points", []))[:10]
        record["prerequisite_gaps"] = dedupe_list(gap_names + record.get("prerequisite_gaps", []))[:10]
        record["practice_focus"] = dedupe_list(focus_items + record.get("practice_focus", []))[:10]
        record["sources"] = dedupe_list(([source] if source else []) + record.get("sources", []))[:10]
        if note.strip():
            record["recent_notes"] = _append_recent_note(record.get("recent_notes", []), note)
        record["mastery_streak"] = 0

    if not weakness_names and kp_names and delta:
        kp_set = set(kp_names)
        for weakness, record in list(weakness_map.items()):
            linked = set(record.get("knowledge_points", []))
            if not kp_set.intersection(linked):
                continue
            severity = _clamp_unit(float(record.get("severity", 0.35)) + (delta * 0.7))
            record["severity"] = severity
            record["status"] = _global_risk_status(severity)
            record["last_result"] = str(result or record.get("last_result") or "").strip()
            record["last_seen_at"] = timestamp
            if note.strip():
                record["recent_notes"] = _append_recent_note(record.get("recent_notes", []), note)
            if _global_positive_signal(result):
                record["mastery_streak"] = int(record.get("mastery_streak", 0)) + 1
            elif _global_negative_signal(result):
                record["mastery_streak"] = 0
            if _archive_weakness_if_mastered(student_memory, weakness, timestamp, "auto_mastered"):
                archived_items["weaknesses"].append(weakness)

    for gap in gap_names:
        record = gap_map.setdefault(
            gap,
            {"count": 0, "updated_at": "", "knowledge_points": [], "weakness_links": []},
        )
        record["count"] = int(record.get("count", 0)) + 1
        record["updated_at"] = timestamp
        record["knowledge_points"] = dedupe_list(kp_names + record.get("knowledge_points", []))[:10]
        record["weakness_links"] = dedupe_list(weakness_names + record.get("weakness_links", []))[:10]

    recent_event = {
        "timestamp": timestamp,
        "conversation_id": str(conversation_id or "").strip(),
        "source": str(source or "manual").strip() or "manual",
        "result": str(result or "").strip(),
        "primary_weakness": primary,
        "secondary_weaknesses": weakness_names[1:] if len(weakness_names) > 1 else [],
        "knowledge_points": kp_names,
        "prerequisite_gaps": gap_names,
        "practice_focus": focus_items,
        "note": str(note or "").strip(),
        "evidence": evidence_items,
        "archived": archived_items,
    }
    recent_events = student_memory.setdefault("recent_events", [])
    recent_events.append(recent_event)
    student_memory["recent_events"] = recent_events[-30:]
    student_memory["updated_at"] = timestamp
    payload["updated_at"] = timestamp
    _write_json(path, payload)

    active_weaknesses = [
        name
        for name, record in student_memory.get("weaknesses", {}).items()
        if float(record.get("severity", 0.0)) >= 0.45
    ]
    return {
        "memory_path": str(path),
        "student_id": student_key,
        "updated_at": timestamp,
        "event": recent_event,
        "summary": {
            "active_weaknesses": dedupe_list(active_weaknesses)[:8],
            "knowledge_points": sorted(student_memory.get("knowledge_points", {}).keys()),
            "mastered_knowledge_points": sorted(student_memory.get("mastered_knowledge_points", {}).keys()),
            "mastered_weaknesses": sorted(student_memory.get("mastered_weaknesses", {}).keys()),
        },
    }


def mark_global_memory_mastered(
    student_id: str = "",
    item_type: str = "knowledge_point",
    item_name: str = "",
    note: str = "",
) -> dict[str, Any]:
    """Archive an active memory item after the user or teacher confirms mastery."""
    path = _global_learning_memory_path()
    payload = _load_json(path, {"version": 1, "updated_at": "", "students": {}})
    if not isinstance(payload, dict):
        payload = {"version": 1, "updated_at": "", "students": {}}
    students = payload.setdefault("students", {})
    if not isinstance(students, dict):
        students = {}
        payload["students"] = students

    student_key = _resolve_global_student_key(student_id)
    student_memory = _ensure_global_student_memory_shape(students.get(student_key, {}), student_key)
    students[student_key] = student_memory
    timestamp = _iso_now()
    name = str(item_name or "").strip()
    if not name:
        return {"ok": False, "error": "item_name is required", "memory_path": str(path)}

    normalized_type = "weakness" if "weak" in str(item_type or "").lower() else "knowledge_point"
    archive_bucket_key = "mastered_weaknesses" if normalized_type == "weakness" else "mastered_knowledge_points"
    active_bucket_key = "weaknesses" if normalized_type == "weakness" else "knowledge_points"
    active_bucket = student_memory.get(active_bucket_key, {})
    archive_bucket = student_memory.get(archive_bucket_key, {})
    matched_name = _match_memory_name(active_bucket, name) or _match_memory_name(archive_bucket, name) or name

    if matched_name in active_bucket:
        record = dict(active_bucket.pop(matched_name))
        record["status"] = "mastered"
        record["mastered_at"] = timestamp
        record["archive_reason"] = "manual_mastered"
        if normalized_type == "knowledge_point":
            record["risk_score"] = _clamp_unit(min(float(record.get("risk_score", 0.0)), 0.12))
            record["mastery_streak"] = max(int(record.get("mastery_streak", 0)), 3)
        else:
            record["severity"] = _clamp_unit(min(float(record.get("severity", 0.0)), 0.12))
            record["mastery_streak"] = max(int(record.get("mastery_streak", 0)), 3)
        archive_bucket[matched_name] = record
    elif matched_name in archive_bucket:
        archive_bucket[matched_name]["mastered_at"] = timestamp
        archive_bucket[matched_name]["archive_reason"] = "manual_mastered"
    else:
        archive_bucket[matched_name] = {
            "status": "mastered",
            "mastered_at": timestamp,
            "archive_reason": "manual_mastered",
            "mastery_streak": 3,
            "risk_score": 0.1 if normalized_type == "knowledge_point" else 0.0,
            "severity": 0.1 if normalized_type == "weakness" else 0.0,
            "practice_focus": [],
            "weakness_links": [] if normalized_type == "knowledge_point" else [],
            "knowledge_points": [] if normalized_type == "weakness" else [],
            "recent_notes": _append_recent_note([], note) if note.strip() else [],
        }

    event = {
        "timestamp": timestamp,
        "conversation_id": "",
        "source": "manual_mastered",
        "result": "mastered",
        "primary_weakness": matched_name if normalized_type == "weakness" else "",
        "secondary_weaknesses": [],
        "knowledge_points": [matched_name] if normalized_type == "knowledge_point" else [],
        "prerequisite_gaps": [],
        "practice_focus": [],
        "note": str(note or "").strip(),
        "evidence": [],
        "archived": {
            "weaknesses": [matched_name] if normalized_type == "weakness" else [],
            "knowledge_points": [matched_name] if normalized_type == "knowledge_point" else [],
        },
    }
    recent_events = student_memory.setdefault("recent_events", [])
    recent_events.append(event)
    student_memory["recent_events"] = recent_events[-30:]
    student_memory["updated_at"] = timestamp
    payload["updated_at"] = timestamp
    _write_json(path, payload)
    return {
        "ok": True,
        "memory_path": str(path),
        "student_id": student_key,
        "item_type": normalized_type,
        "item_name": matched_name,
        "updated_at": timestamp,
    }


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
    global_memory_event = update_global_learning_memory(
        student_id=student_id,
        knowledge_points=[knowledge_point],
        result=result,
        note=note,
        evidence=evidence or [],
        source="mastery_update",
    )
    event["global_memory_event"] = global_memory_event
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
    memory_target = _resolve_micro_quiz_memory_target(
        student_id=student_id.strip(),
        problem_text=problem_text,
        requested_knowledge_point=knowledge_point,
    )
    quiz_problem_text = str(memory_target.get("problem_text") or problem_text)
    quiz_question_type = str(memory_target.get("question_type") or structure["question_type"])
    resolved_knowledge_point = str(
        memory_target.get("knowledge_point")
        or knowledge_point.strip()
        or structure["knowledge_points"][0]
    )

    quiz_count = _coerce_quiz_count(count)
    items, answer_key = _build_micro_quiz(
        quiz_problem_text,
        quiz_question_type,
        quiz_count,
    )
    resolved_difficulty = (
        structure["difficulty_band"]
        if difficulty.strip().lower() == "auto"
        else difficulty.strip().lower()
    )
    quiz_id = f"mq-{uuid4().hex[:10]}"
    memory_context = {
        "student_id": student_id.strip(),
        "quiz_source": str(memory_target.get("quiz_source") or "current_problem"),
        "targeted_knowledge_point": resolved_knowledge_point,
        "targeted_weaknesses": list(memory_target.get("weaknesses") or [])[:3],
        "active_knowledge_point_count": int(memory_target.get("active_knowledge_point_count") or 0),
    }
    payload = {
        "quiz_id": quiz_id,
        "student_id": student_id.strip(),
        "problem_text": normalize_problem_text(quiz_problem_text),
        "source_problem_text": normalize_problem_text(problem_text),
        "question_type": quiz_question_type,
        "knowledge_point": resolved_knowledge_point,
        "difficulty": resolved_difficulty,
        "generated_at": _iso_now(),
        "estimated_minutes": len(items),
        "items": items,
        "answer_key": answer_key,
        "memory_context": memory_context,
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
        "memory_context": memory_context,
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
    global_memory_event = None
    if update_mastery_record and resolved_student_id:
        mastery_event = update_math_mastery(
            student_id=resolved_student_id,
            knowledge_point=quiz_record.get("knowledge_point", "general_problem_solving"),
            result=result,
            evidence=[f"micro_quiz:{quiz_id}", f"score:{score}"],
            note=f"micro quiz graded with {correct_count}/{total} correct",
        )
        global_memory_event = mastery_event.get("global_memory_event") if isinstance(mastery_event, dict) else None
    else:
        global_memory_event = update_global_learning_memory(
            student_id=resolved_student_id,
            knowledge_points=[quiz_record.get("knowledge_point", "general_problem_solving")],
            result=result,
            note=f"micro quiz graded with {correct_count}/{total} correct",
            evidence=[f"micro_quiz:{quiz_id}", f"score:{score}"],
            source="micro_quiz",
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
        "global_memory_event": global_memory_event,
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



# === SIMPLE_MEMORY_CN_NORMALIZATION_20260315 ===
_ORIGINAL_GET_GLOBAL_LEARNING_MEMORY_20260315 = get_global_learning_memory
_ORIGINAL_UPDATE_GLOBAL_LEARNING_MEMORY_20260315 = update_global_learning_memory
_ORIGINAL_MARK_GLOBAL_MEMORY_MASTERED_20260315 = mark_global_memory_mastered

_CN_MEMORY_LABELS = {
    'incomplete_reasoning': '???????',
    'symbolic_manipulation_gap': '???????',
    'diagram_or_theorem_gap': '???????????',
    'linear_equation procedural execution': '?????????????',
    'step documentation': '???????',
    'reading_or_prompt_misread': '????',
    'sign_error': '????',
    'calculation_or_careless_error': '???????',
    'prerequisite_gap': '??????',
    'linear_equation': '??????',
    'linear equation': '??????',
    'derivatives': '??',
    'derivative computation': '????',
    'derivative_computation': '????',
    'kinematics': '???',
    'geometry': '??',
    'showing_intermediate_steps': '??????',
    'showing all intermediate steps when solving linear equations': '????????????????',
    'demonstrate each algebraic manipulation step explicitly': '???????????',
    'relating displacement functions to velocity via derivatives': '???????????????',
    'verifying derivative calculations step-by-step': '????????',
    'calculus concept: derivative as instantaneous velocity': '????????????',
    'arithmetic verification in derivative evaluation': '?????????',
    'factoring': '????',
    'quadratic_equation': '??????',
    'equations_and_inequalities': '??????',
    'integer_operations': '????',
    'arithmetic_operations': '????',
    'weakness_diag': '?????',
    'manual_seed': 'æå¨æ·»å ',
    'micro_quiz': '????',
    'mastery_update': '?????',
    'manual_mastered': '???????',
    'mastered_reopened': '????????',
    'incorrect': '??',
    'partial': '????',
    'correct': '??',
    'quiz_fail': '?????',
    'quiz_pass': '????',
    'hinted': '?????',
    'review': '????',
    'pass': '??',
    'conflict': '????',
}


def _normalize_memory_text_cn(value: Any) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    lowered = text.lower().replace('-', '_')
    if lowered in _CN_MEMORY_LABELS:
        return _CN_MEMORY_LABELS[lowered]
    normalized = text
    for source, target in _CN_MEMORY_LABELS.items():
        normalized = normalized.replace(source, target)
        normalized = normalized.replace(source.replace('_', ' '), target)
        normalized = normalized.replace(source.replace('_', '-'), target)
    return normalized.strip()


def _normalize_memory_list_cn(values: Any) -> list[Any]:
    if not isinstance(values, list):
        return values
    normalized = []
    for item in values:
        if isinstance(item, str):
            text = _normalize_memory_text_cn(item)
            if text:
                normalized.append(text)
        elif isinstance(item, dict):
            normalized.append(_normalize_memory_dict_cn(item))
        else:
            normalized.append(item)
    return normalized


def _normalize_memory_dict_cn(values: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in values.items():
        new_key = key
        if key in {'weaknesses', 'mastered_weaknesses', 'knowledge_points', 'mastered_knowledge_points', 'prerequisite_gaps'} and isinstance(value, dict):
            bucket: dict[str, Any] = {}
            for item_key, item_value in value.items():
                bucket[_normalize_memory_text_cn(item_key)] = _normalize_memory_dict_cn(item_value) if isinstance(item_value, dict) else item_value
            normalized[new_key] = bucket
            continue
        if isinstance(value, dict):
            normalized[new_key] = _normalize_memory_dict_cn(value)
        elif isinstance(value, list):
            normalized[new_key] = _normalize_memory_list_cn(value)
        elif isinstance(value, str):
            if new_key in {'source', 'result', 'status', 'primary_weakness', 'note'}:
                normalized[new_key] = _normalize_memory_text_cn(value)
            else:
                normalized[new_key] = _normalize_memory_text_cn(value)
        else:
            normalized[new_key] = value
    return normalized


def _persist_normalized_global_memory_cn() -> dict[str, Any]:
    path = _global_learning_memory_path()
    payload = _load_json(path, {'version': 1, 'updated_at': '', 'students': {}})
    if not isinstance(payload, dict):
        payload = {'version': 1, 'updated_at': '', 'students': {}}
    students = payload.get('students') if isinstance(payload.get('students'), dict) else {}
    normalized_students = {}
    for student_key, student_memory in students.items():
        normalized_students[student_key] = _normalize_memory_dict_cn(_ensure_global_student_memory_shape(student_memory, student_key))
    payload['students'] = normalized_students
    _write_json(path, payload)
    return payload


def get_global_learning_memory(student_id: str = '') -> dict[str, Any]:
    _persist_normalized_global_memory_cn()
    return _ORIGINAL_GET_GLOBAL_LEARNING_MEMORY_20260315(student_id)


def update_global_learning_memory(
    student_id: str = '',
    primary_weakness: str = '',
    secondary_weaknesses: Optional[list[str]] = None,
    knowledge_points: Optional[list[str]] = None,
    prerequisite_gaps: Optional[list[str]] = None,
    practice_focus: Optional[list[str]] = None,
    result: str = '',
    note: str = '',
    evidence: Optional[list[str]] = None,
    source: str = '',
    conversation_id: str = '',
) -> dict[str, Any]:
    response = _ORIGINAL_UPDATE_GLOBAL_LEARNING_MEMORY_20260315(
        student_id=student_id,
        primary_weakness=_normalize_memory_text_cn(primary_weakness),
        secondary_weaknesses=[_normalize_memory_text_cn(item) for item in (secondary_weaknesses or []) if _normalize_memory_text_cn(item)],
        knowledge_points=[_normalize_memory_text_cn(item) for item in (knowledge_points or []) if _normalize_memory_text_cn(item)],
        prerequisite_gaps=[_normalize_memory_text_cn(item) for item in (prerequisite_gaps or []) if _normalize_memory_text_cn(item)],
        practice_focus=[_normalize_memory_text_cn(item) for item in (practice_focus or []) if _normalize_memory_text_cn(item)],
        result=result,
        note=_normalize_memory_text_cn(note),
        evidence=[_normalize_memory_text_cn(item) for item in (evidence or []) if _normalize_memory_text_cn(item)],
        source=source,
        conversation_id=conversation_id,
    )
    _persist_normalized_global_memory_cn()
    return response


def mark_global_memory_mastered(
    student_id: str = '',
    item_type: str = 'knowledge_point',
    item_name: str = '',
    note: str = '',
) -> dict[str, Any]:
    response = _ORIGINAL_MARK_GLOBAL_MEMORY_MASTERED_20260315(
        student_id=student_id,
        item_type=item_type,
        item_name=_normalize_memory_text_cn(item_name),
        note=_normalize_memory_text_cn(note),
    )
    _persist_normalized_global_memory_cn()
    return response


def summarize_global_learning_memory_cn(student_id: str = '') -> dict[str, Any]:
    payload = get_global_learning_memory(student_id)
    memory = payload.get('memory') if isinstance(payload.get('memory'), dict) else None
    if memory is None:
        students = payload.get('students') if isinstance(payload.get('students'), dict) else {}
        memory = students.get('__global__') if isinstance(students, dict) else None
    if not isinstance(memory, dict):
        return {'summary_text': '??????????', 'weaknesses': [], 'knowledge_points': []}
    weakness_items = []
    for name, record in (memory.get('weaknesses') or {}).items():
        if not isinstance(record, dict):
            continue
        weakness_items.append((float(record.get('severity', 0.0) or 0.0), str(name).strip()))
    knowledge_items = []
    for name, record in (memory.get('knowledge_points') or {}).items():
        if not isinstance(record, dict):
            continue
        knowledge_items.append((float(record.get('risk_score', 0.0) or 0.0), str(name).strip()))
    weaknesses = [name for _, name in sorted(weakness_items, reverse=True)[:4] if name]
    knowledge_points = [name for _, name in sorted(knowledge_items, reverse=True)[:4] if name]
    focus_items = [str(item).strip() for item in (memory.get('practice_focus') or []) if str(item).strip()][:4]
    lines = []
    if weaknesses:
        lines.append('??????' + '?'.join(weaknesses))
    if knowledge_points:
        lines.append('?????????' + '?'.join(knowledge_points))
    if focus_items:
        lines.append('???????' + '?'.join(focus_items))
    return {'summary_text': '\n'.join(lines) if lines else '??????????', 'weaknesses': weaknesses, 'knowledge_points': knowledge_points, 'practice_focus': focus_items}

# === SIMPLE_MEMORY_CN_OVERRIDE_20260315 ===
_CN_MEMORY_LABELS_20260315 = {
    'incomplete_reasoning': '推理不完整',
    'reading_or_prompt_misread': '审题不清',
    'sign_error': '符号错误',
    'calculation_or_careless_error': '计算粗心',
    'diagram_or_theorem_gap': '图形或定理理解薄弱',
    'symbolic_manipulation_gap': '代数变形薄弱',
    'linear_equation': '一元一次方程',
    'quadratic_equation': '一元二次方程',
    'geometry': '几何',
    'derivatives': '导数',
    'equations_and_inequalities': '方程与不等式',
    'arithmetic_operations': '四则运算',
    'integer_operations': '整数运算',
    'symbolic_manipulation': '代数变形',
    'showing_intermediate_steps': '中间步骤书写',
    'derivative_computation': '导数计算',
    'factoring': '因式分解',
    'correct': '正确',
    'incorrect': '错误',
    'partial': '部分正确',
    'hinted': '需要提示',
    'review': '需要复习',
    'quiz_pass': '小测通过',
    'quiz_fail': '小测未通过',
    'mastered': '已掌握',
    'watch': '继续观察',
    'active': '当前薄弱',
    'improving': '正在改善',
    'stable': '相对稳定',
    'manual_mastered': '手动标记已掌握',
    'mastery_update': '掌握度更新',
    'micro_quiz': '微测复查',
    'weakness_diag': '薄弱点诊断',
}
_BASE_GET_GLOBAL_MEMORY_20260315 = _ORIGINAL_GET_GLOBAL_LEARNING_MEMORY_20260315
_BASE_UPDATE_GLOBAL_MEMORY_20260315 = _ORIGINAL_UPDATE_GLOBAL_LEARNING_MEMORY_20260315
_BASE_MARK_GLOBAL_MEMORY_MASTERED_20260315 = _ORIGINAL_MARK_GLOBAL_MEMORY_MASTERED_20260315

def _normalize_memory_text_cn_20260315(value: Any) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    if re.search(r'[一-鿿]', text):
        return text
    normalized = text.lower().replace('-', '_').replace(' ', '_')
    return _CN_MEMORY_LABELS_20260315.get(normalized, text)

def _normalize_memory_list_cn_20260315(items: Any) -> list[str]:
    result = []
    for item in items or []:
        text = _normalize_memory_text_cn_20260315(item)
        if text:
            result.append(text)
    return dedupe_list(result)

def _normalize_memory_payload_cn_20260315(payload: dict[str, Any]) -> dict[str, Any]:
    students = payload.get('students') if isinstance(payload, dict) else {}
    if isinstance(payload.get('memory'), dict):
        students = {payload.get('student_id') or '__global__': payload.get('memory')}
    if not isinstance(students, dict):
        return payload
    for student_memory in students.values():
        if not isinstance(student_memory, dict):
            continue
        for bucket_key in ('weaknesses', 'mastered_weaknesses', 'knowledge_points', 'mastered_knowledge_points', 'prerequisite_gaps'):
            bucket = student_memory.get(bucket_key)
            if not isinstance(bucket, dict):
                continue
            normalized_bucket = {}
            for name, record in bucket.items():
                new_name = _normalize_memory_text_cn_20260315(name)
                if isinstance(record, dict):
                    new_record = dict(record)
                    for field in ('status', 'last_result'):
                        new_record[field] = _normalize_memory_text_cn_20260315(new_record.get(field)) or new_record.get(field, '')
                    for field in ('knowledge_points', 'prerequisite_gaps', 'practice_focus', 'weakness_links'):
                        if field in new_record:
                            new_record[field] = _normalize_memory_list_cn_20260315(new_record.get(field) or [])
                    if 'recent_notes' in new_record:
                        new_record['recent_notes'] = [_normalize_memory_text_cn_20260315(item) or str(item).strip() for item in (new_record.get('recent_notes') or []) if str(item).strip()]
                    normalized_bucket[new_name] = new_record
                else:
                    normalized_bucket[new_name] = record
            student_memory[bucket_key] = normalized_bucket
        student_memory['practice_focus'] = _normalize_memory_list_cn_20260315(student_memory.get('practice_focus') or [])
        recent_events = []
        for event in student_memory.get('recent_events') or []:
            if not isinstance(event, dict):
                continue
            new_event = dict(event)
            for field in ('source', 'result', 'primary_weakness', 'note'):
                new_event[field] = _normalize_memory_text_cn_20260315(new_event.get(field)) or str(new_event.get(field) or '').strip()
            for field in ('secondary_weaknesses', 'knowledge_points', 'prerequisite_gaps', 'practice_focus'):
                new_event[field] = _normalize_memory_list_cn_20260315(new_event.get(field) or [])
            new_event['evidence'] = [_normalize_memory_text_cn_20260315(item) or str(item).strip() for item in (new_event.get('evidence') or []) if str(item).strip()]
            recent_events.append(new_event)
        student_memory['recent_events'] = recent_events[-30:]
    return payload

def _persist_normalized_global_memory_cn_20260315() -> None:
    path = _global_learning_memory_path(); payload = _load_json(path, {'version': 1, 'updated_at': '', 'students': {}})
    if not isinstance(payload, dict):
        return
    payload = _normalize_memory_payload_cn_20260315(payload)
    _write_json(path, payload)

def get_global_learning_memory(student_id: str = '') -> dict[str, Any]:
    payload = _BASE_GET_GLOBAL_MEMORY_20260315(student_id=student_id)
    payload = _normalize_memory_payload_cn_20260315(payload)
    _persist_normalized_global_memory_cn_20260315()
    return payload

def update_global_learning_memory(student_id: str = '', primary_weakness: str = '', secondary_weaknesses: Optional[list[str]] = None, knowledge_points: Optional[list[str]] = None, prerequisite_gaps: Optional[list[str]] = None, practice_focus: Optional[list[str]] = None, result: str = '', note: str = '', evidence: Optional[list[str]] = None, source: str = '', conversation_id: str = '') -> dict[str, Any]:
    payload = _BASE_UPDATE_GLOBAL_MEMORY_20260315(student_id=student_id, primary_weakness=_normalize_memory_text_cn_20260315(primary_weakness), secondary_weaknesses=_normalize_memory_list_cn_20260315(secondary_weaknesses or []), knowledge_points=_normalize_memory_list_cn_20260315(knowledge_points or []), prerequisite_gaps=_normalize_memory_list_cn_20260315(prerequisite_gaps or []), practice_focus=_normalize_memory_list_cn_20260315(practice_focus or []), result=_normalize_memory_text_cn_20260315(result), note=_normalize_memory_text_cn_20260315(note) or str(note or '').strip(), evidence=[_normalize_memory_text_cn_20260315(item) or str(item).strip() for item in (evidence or []) if str(item).strip()], source=_normalize_memory_text_cn_20260315(source) or str(source or '').strip(), conversation_id=conversation_id)
    _persist_normalized_global_memory_cn_20260315()
    return _normalize_memory_payload_cn_20260315(payload)

def mark_global_memory_mastered(student_id: str = '', item_type: str = 'knowledge_point', item_name: str = '', note: str = '') -> dict[str, Any]:
    payload = _BASE_MARK_GLOBAL_MEMORY_MASTERED_20260315(student_id=student_id, item_type=item_type, item_name=_normalize_memory_text_cn_20260315(item_name) or item_name, note=_normalize_memory_text_cn_20260315(note) or note)
    _persist_normalized_global_memory_cn_20260315()
    return payload

def summarize_global_learning_memory_cn(memory_payload: dict[str, Any]) -> str:
    if not isinstance(memory_payload, dict):
        return ''
    memory = memory_payload.get('memory') if isinstance(memory_payload.get('memory'), dict) else None
    if memory is None:
        students = memory_payload.get('students') if isinstance(memory_payload.get('students'), dict) else {}
        if isinstance(students, dict) and students:
            memory = students.get('__global__') if isinstance(students.get('__global__'), dict) else next(iter(students.values()))
    if not isinstance(memory, dict):
        return ''
    weakness_items = []
    for name, record in (memory.get('weaknesses') or {}).items():
        if isinstance(record, dict):
            weakness_items.append((float(record.get('severity', 0.0) or 0.0), str(name).strip()))
    knowledge_items = []
    for name, record in (memory.get('knowledge_points') or {}).items():
        if isinstance(record, dict):
            knowledge_items.append((float(record.get('risk_score', 0.0) or 0.0), str(name).strip()))
    focus_items = [str(item).strip() for item in (memory.get('practice_focus') or []) if str(item).strip()]
    lines = []
    if weakness_items:
        lines.append('历史薄弱点：' + '、'.join(name for _, name in sorted(weakness_items, reverse=True)[:4] if name))
    if knowledge_items:
        lines.append('当前高风险知识点：' + '、'.join(name for _, name in sorted(knowledge_items, reverse=True)[:4] if name))
    if focus_items:
        lines.append('当前训练重点：' + '、'.join(focus_items[:4]))
    return '\n'.join(lines).strip()

_persist_normalized_global_memory_cn_20260315()
