"""Weakness diagnosis agent system for math tutoring using Qwen3-VL-Plus."""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from ...constant import WORKING_DIR
from .math_learning import (
    extract_math_knowledge,
    map_problem_to_curriculum,
    update_global_learning_memory,
)
from .math_reasoning import verify_math_solution
from .math_utils import build_method_tags, dedupe_list, normalize_problem_text
from .solve_verify_q3vl import (
    _call_qwen_json,
    _load_solver_config,
    _resolve_supporting_images,
    run_math_solve_verify_agent,
)

_DEFAULT_DIAG_MODEL = "qwen3-vl-plus"

_CASE_SCHEMA = {
    "problem_summary": "str",
    "student_state": "str",
    "question_type": "str",
    "chapter": "str",
    "knowledge_points": ["str"],
    "target": "str",
    "observed_signals": ["str"],
    "diagnosis_focus": ["str"],
    "evidence_gaps": ["str"],
    "needs_solution_bootstrap": True,
    "difficulty_band": "str",
}

_PROCESS_SCHEMA = {
    "primary_error_stage": "setup|execution|reasoning|final_answer|unknown",
    "wrong_answer": True,
    "process_incomplete": True,
    "missing_steps": ["str"],
    "evidence_items": ["str"],
    "likely_error_causes": ["str"],
    "confidence": 0.0,
}

_LEARNING_SCHEMA = {
    "primary_weakness": "str",
    "secondary_weaknesses": ["str"],
    "knowledge_points": ["str"],
    "prerequisite_gaps": ["str"],
    "recommended_practice_focus": ["str"],
    "teacher_watchouts": ["str"],
    "confidence": 0.0,
}

_ARBITER_SCHEMA = {
    "status": "diagnosed|review",
    "problem_summary": "str",
    "primary_weakness": "str",
    "secondary_weaknesses": ["str"],
    "wrong_answer": True,
    "process_incomplete": True,
    "missing_steps": ["str"],
    "evidence_items": ["str"],
    "chapter": "str",
    "question_type": "str",
    "knowledge_points": ["str"],
    "prerequisite_gaps": ["str"],
    "likely_error_causes": ["str"],
    "recommended_practice_focus": ["str"],
    "teacher_feedback_markdown": "str",
    "mastery_update_suggestion": {
        "result": "incorrect|partial|hinted",
        "knowledge_points": ["str"],
        "note": "str",
    },
    "confidence": 0.0,
}

_COMBINED_ANALYSIS_SCHEMA = {
    "process": _PROCESS_SCHEMA,
    "learning": _LEARNING_SCHEMA,
    "arbiter": _ARBITER_SCHEMA,
}

_COMBINED_ANALYSIS_PROMPT = """
你是数学学习诊断系统中的“薄弱点诊断器”。
请基于题目、学生作答、求解与验证结果、历史记忆和当前对话，判断学生当前最关键的薄弱点。
要求：
- 只返回一个 JSON 对象。
- 所有自然语言字段必须使用简体中文。
- 先找最先暴露问题的步骤，再映射到知识点、前置缺口和训练重点。
- 如果证据不足，要保守诊断，不要夸大结论。
- teacher_feedback_markdown 必须是给老师或家长直接可读的中文内容。
""".strip()


def _resolve_source_path(source: str) -> Path:
    path = Path(str(source or "")).expanduser()
    if path.is_absolute():
        return path
    return Path(WORKING_DIR) / path


def _weakness_runs_dir() -> Path:
    path = Path(WORKING_DIR) / "weakness_diag_runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", str(text or "").strip()).strip("-")
    return slug.lower() or "weakness"


def _new_run_dir(seed_text: str) -> Path:
    stem = _slugify(seed_text[:48])
    run_dir = _weakness_runs_dir() / f"{int(time.time())}-{stem}-{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _coerce_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _trim_text(text: str, limit: int = 2400) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _load_json_input(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    text = str(value).strip()
    if not text:
        return {}
    path = _resolve_source_path(text)
    if path.exists() and path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    try:
        payload = json.loads(text)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalized_answer(text: str) -> str:
    return re.sub(r"\s+", "", normalize_problem_text(text)).lower()


def _question_type_requires_process(question_type: str) -> bool:
    return str(question_type or "").strip().lower() in {
        "equation",
        "algebra",
        "geometry",
        "proof",
        "classification",
        "word_problem",
    }


def _extract_answer_from_context(text: str) -> str:
    value = str(text or '').strip()
    if not value:
        return ''
    patterns = (
        r"(?:student\s*answer|answer|\u5b66\u751f\u7b54\u6848|\u6211\u7684\u7b54\u6848)\s*[:\uff1a]?\s*([^\n]+)",
        r"(?:=|\u662f)\s*([A-Za-z0-9_.,; +\-*/^()]+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, value, re.IGNORECASE)
        if match:
            return str(match.group(1)).strip()[:120]
    return ''


def _extract_conflict_notes(verification_payload: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if not isinstance(verification_payload, dict):
        return notes
    arbiter = verification_payload.get("arbiter") if isinstance(verification_payload.get("arbiter"), dict) else {}
    critic = verification_payload.get("critic") if isinstance(verification_payload.get("critic"), dict) else {}
    tool_checks = verification_payload.get("tool_checks") if isinstance(verification_payload.get("tool_checks"), dict) else {}
    notes.extend(str(item).strip() for item in arbiter.get("unresolved_risks", []) or [] if str(item).strip())
    notes.extend(str(item).strip() for item in critic.get("conflict_summary", []) or [] if str(item).strip())
    for review in critic.get("candidate_reviews", []) or []:
        if not isinstance(review, dict):
            continue
        first = str(review.get("first_conflicting_step") or "").strip()
        if first:
            notes.append(first)
        for issue in review.get("issues", []) or []:
            issue_text = str(issue).strip()
            if issue_text:
                notes.append(issue_text)
    for check in tool_checks.get("candidate_checks", []) or []:
        if not isinstance(check, dict):
            continue
        verification = check.get("verification") if isinstance(check.get("verification"), dict) else {}
        notes.extend(str(item).strip() for item in verification.get("notes", []) or [] if str(item).strip())
    return dedupe_list(notes)


def _infer_error_causes(*, detail_text: str, question_type: str, wrong_answer: bool, process_incomplete: bool) -> list[str]:
    text = normalize_problem_text(detail_text).lower()
    causes: list[str] = []
    if any(token in text for token in ("看错", "读错", "漏看", "审题", "reading")):
        causes.append("reading_or_prompt_misread")
    if any(token in text for token in ("符号", "正负", "变号", "minus")):
        causes.append("sign_error")
    if any(token in text for token in ("算错", "计算", "粗心", "抄错", "careless")):
        causes.append("calculation_or_careless_error")
    if any(token in text for token in ("不会", "没思路", "卡住", "无从下手", "stuck")):
        causes.append("strategy_gap")
    if process_incomplete:
        causes.append("incomplete_reasoning")
    lowered_qtype = str(question_type or "").strip().lower()
    if wrong_answer and lowered_qtype in {"equation", "algebra"}:
        causes.append("symbolic_manipulation_gap")
    if lowered_qtype == "geometry":
        causes.append("diagram_or_theorem_gap")
    if lowered_qtype in {"proof", "classification"}:
        causes.append("proof_structure_gap")
    if not causes:
        causes.append("concept_gap")
    return dedupe_list(causes)


def _infer_missing_steps(*, question_type: str, student_work: str, conversation_excerpt: str, conflict_notes: list[str]) -> tuple[bool, list[str]]:
    work = normalize_problem_text(student_work)
    excerpt = normalize_problem_text(conversation_excerpt)
    missing_steps: list[str] = []
    if not work.strip():
        missing_steps.append("Student attempt does not show explicit intermediate steps.")
    else:
        step_markers = work.count("=") + work.count("\n") + work.count("->") + work.count("=>")
        if _question_type_requires_process(question_type) and step_markers < 1 and len(work) < 80:
            missing_steps.append("The attempt jumps too quickly and does not expose the first derivation step.")
        if str(question_type or "").strip().lower() in {"geometry", "proof", "classification"} and len(work) < 40:
            missing_steps.append("The proof or justification chain is not explicit enough to check.")
    for note in conflict_notes:
        lowered = note.lower()
        if any(token in lowered for token in ("missing", "lack", "not provided", "without")):
            missing_steps.append(note)
    if not missing_steps and not work.strip() and excerpt:
        missing_steps.append("Current dialogue does not yet contain a step-by-step student solution.")
    return bool(missing_steps), dedupe_list(missing_steps)

def _load_or_bootstrap_verification(
    problem_text: str,
    reference_answer: str,
    verification_report: str,
    supporting_images: str,
    conversation_excerpt: str = "",
) -> tuple[dict[str, Any], dict[str, Any], str]:
    payload = _load_json_input(verification_report)
    bootstrap: dict[str, Any] = {}
    resolved_reference = str(reference_answer or "").strip() or _extract_answer_from_context(conversation_excerpt)
    if payload:
        arbiter = payload.get("arbiter") if isinstance(payload.get("arbiter"), dict) else {}
        if not resolved_reference:
            resolved_reference = str(arbiter.get("final_answer") or "").strip()
        return bootstrap, payload, resolved_reference
    if resolved_reference or not normalize_problem_text(problem_text):
        return bootstrap, payload, resolved_reference
    try:
        bootstrap = run_math_solve_verify_agent(
            problem_text=problem_text,
            expected_answer=resolved_reference,
            supporting_images=supporting_images,
        )
        payload = _load_json_input(bootstrap.get("VerificationReport_json_path"))
        if not resolved_reference:
            resolved_reference = str(bootstrap.get("final_answer") or "").strip()
        if not resolved_reference and isinstance(payload.get("arbiter"), dict):
            resolved_reference = str(payload["arbiter"].get("final_answer") or "").strip()
    except Exception as exc:
        bootstrap = {"error": str(exc)}
    return bootstrap, payload, resolved_reference


def _build_local_checks(
    *,
    problem_text: str,
    student_answer: str,
    student_work: str,
    error_description: str,
    reference_answer: str,
    verification_payload: dict[str, Any],
    conversation_excerpt: str,
    grade_hint: str,
) -> dict[str, Any]:
    normalized_problem = normalize_problem_text(problem_text or conversation_excerpt)
    curriculum = map_problem_to_curriculum(normalized_problem, grade_hint)
    knowledge = extract_math_knowledge(
        normalized_problem,
        solution_summary=student_work or student_answer,
        error_description=f"{error_description}\n{conversation_excerpt}",
    )
    resolved_student_answer = str(student_answer or "").strip() or _extract_answer_from_context(error_description) or _extract_answer_from_context(conversation_excerpt)
    compare = (
        verify_math_solution(
            problem_text=normalized_problem,
            proposed_answer=resolved_student_answer,
            expected_answer=reference_answer,
            variable="x",
        )
        if resolved_student_answer.strip() and (reference_answer.strip() or normalized_problem)
        else {}
    )

    verification_status = ""
    if isinstance(compare, dict):
        verification_status = str(compare.get("status") or "").strip()
    if not verification_status and isinstance(verification_payload.get("arbiter"), dict):
        verification_status = str(verification_payload["arbiter"].get("status") or "").strip()

    wrong_answer = verification_status == "conflict"
    if not wrong_answer and resolved_student_answer.strip() and reference_answer.strip():
        wrong_answer = _normalized_answer(resolved_student_answer) != _normalized_answer(reference_answer)

    conflict_notes = _extract_conflict_notes(verification_payload)
    process_incomplete, missing_steps = _infer_missing_steps(
        question_type=str(curriculum.get("question_type") or ""),
        student_work=student_work,
        conversation_excerpt=conversation_excerpt,
        conflict_notes=conflict_notes,
    )
    causes = _infer_error_causes(
        detail_text="\n".join(filter(None, [error_description, conversation_excerpt, "\n".join(conflict_notes)])),
        question_type=str(curriculum.get("question_type") or ""),
        wrong_answer=wrong_answer,
        process_incomplete=process_incomplete,
    )
    evidence_items: list[str] = []
    if wrong_answer:
        evidence_items.append("学生的最终答案与核验结果或精确检查不一致。")
    if process_incomplete:
        evidence_items.append("当前缺少足够的学生作答步骤，暂时只能做保守诊断。")
    if reference_answer:
        evidence_items.append(f"参考答案： {reference_answer}")
    evidence_items.extend(conflict_notes[:4])
    if isinstance(compare, dict):
        for note in compare.get("notes", []) or []:
            note_text = str(note).strip()
            if note_text:
                evidence_items.append(note_text)

    return {
        "curriculum": curriculum,
        "knowledge": knowledge,
        "verification_compare": compare,
        "verification_status": verification_status or ("review" if process_incomplete else ""),
        "wrong_answer": bool(wrong_answer),
        "process_incomplete": bool(process_incomplete),
        "missing_steps": missing_steps,
        "likely_error_causes": causes,
        "evidence_items": dedupe_list([item for item in evidence_items if item]),
        "method_tags": build_method_tags(f"{normalized_problem}\n{student_work}"),
    }


def _fallback_process(case_brief: dict[str, Any], local_checks: dict[str, Any]) -> dict[str, Any]:
    primary_stage = "reasoning" if local_checks.get("process_incomplete") else ("final_answer" if local_checks.get("wrong_answer") else "unknown")
    return {
        "primary_error_stage": primary_stage,
        "wrong_answer": bool(local_checks.get("wrong_answer")),
        "process_incomplete": bool(local_checks.get("process_incomplete")),
        "missing_steps": list(local_checks.get("missing_steps") or []),
        "evidence_items": list(local_checks.get("evidence_items") or []),
        "likely_error_causes": list(local_checks.get("likely_error_causes") or []),
        "confidence": 0.82 if (local_checks.get("wrong_answer") or local_checks.get("process_incomplete")) else 0.55,
    }


def _fallback_learning(case_brief: dict[str, Any], local_checks: dict[str, Any]) -> dict[str, Any]:
    curriculum = local_checks.get("curriculum") if isinstance(local_checks.get("curriculum"), dict) else {}
    knowledge = local_checks.get("knowledge") if isinstance(local_checks.get("knowledge"), dict) else {}
    knowledge_points = _coerce_list(knowledge.get("knowledge_points") or curriculum.get("knowledge_points"))
    prerequisites = _coerce_list(knowledge.get("prerequisite_concepts") or curriculum.get("prerequisites"))
    causes = _coerce_list(local_checks.get("likely_error_causes"))
    primary = causes[0] if causes else (knowledge_points[0] if knowledge_points else "concept_gap")
    return {
        "primary_weakness": primary,
        "secondary_weaknesses": causes[1:3] if len(causes) > 1 else knowledge_points[1:3],
        "knowledge_points": knowledge_points,
        "prerequisite_gaps": prerequisites[:4],
        "recommended_practice_focus": knowledge_points[:2] or ["rebuild the first derivation step"],
        "teacher_watchouts": ["Ask the student to restate the target and show the first algebraic step."],
        "confidence": 0.78 if knowledge_points else 0.58,
    }


def _merge_candidate_with_fallback(candidate: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    merged = dict(fallback)
    if isinstance(candidate, dict):
        for key, value in candidate.items():
            if key == "value":
                continue
            if value in (None, "", [], {}):
                continue
            merged[key] = value
    for key, value in fallback.items():
        if key not in merged or merged.get(key) in (None, "", [], {}):
            merged[key] = value
    return merged


def _fallback_arbiter(case_brief: dict[str, Any], process: dict[str, Any], learning: dict[str, Any], local_checks: dict[str, Any]) -> dict[str, Any]:
    knowledge_points = dedupe_list(_coerce_list(learning.get("knowledge_points")) + _coerce_list(local_checks.get("knowledge", {}).get("knowledge_points")))
    prerequisite_gaps = dedupe_list(_coerce_list(learning.get("prerequisite_gaps")) + _coerce_list(local_checks.get("curriculum", {}).get("prerequisites")))
    likely_causes = dedupe_list(_coerce_list(process.get("likely_error_causes")) + _coerce_list(local_checks.get("likely_error_causes")))
    missing_steps = dedupe_list(_coerce_list(process.get("missing_steps")) + _coerce_list(local_checks.get("missing_steps")))
    evidence_items = dedupe_list(_coerce_list(process.get("evidence_items")) + _coerce_list(local_checks.get("evidence_items")))
    primary_weakness = str(learning.get("primary_weakness") or (likely_causes[0] if likely_causes else "insufficient_evidence")).strip()
    status = "diagnosed" if (local_checks.get("wrong_answer") or local_checks.get("process_incomplete") or primary_weakness != "insufficient_evidence") else "review"
    mastery_result = "incorrect" if local_checks.get("wrong_answer") else ("partial" if local_checks.get("process_incomplete") else "hinted")
    teacher_feedback = (
        "# Weakness Diagnosis\n\n"
        f"- Primary weakness: {primary_weakness or 'insufficient_evidence'}\n"
        f"- Wrong answer: {'yes' if local_checks.get('wrong_answer') else 'no'}\n"
        f"- Process incomplete: {'yes' if local_checks.get('process_incomplete') else 'no'}\n"
        + ("- Missing steps:\n" + "\n".join(f"  - {item}" for item in missing_steps) + "\n" if missing_steps else "")
        + ("- Practice focus:\n" + "\n".join(f"  - {item}" for item in _coerce_list(learning.get("recommended_practice_focus"))) + "\n" if learning.get("recommended_practice_focus") else "")
    ).strip()
    return {
        "status": status,
        "problem_summary": str(case_brief.get("problem_summary") or "").strip(),
        "primary_weakness": primary_weakness,
        "secondary_weaknesses": dedupe_list(_coerce_list(learning.get("secondary_weaknesses")) + likely_causes[1:3]),
        "wrong_answer": bool(local_checks.get("wrong_answer")),
        "process_incomplete": bool(local_checks.get("process_incomplete")),
        "missing_steps": missing_steps,
        "evidence_items": evidence_items,
        "chapter": str(case_brief.get("chapter") or local_checks.get("curriculum", {}).get("chapter") or "").strip(),
        "question_type": str(case_brief.get("question_type") or local_checks.get("curriculum", {}).get("question_type") or "").strip(),
        "knowledge_points": knowledge_points,
        "prerequisite_gaps": prerequisite_gaps,
        "likely_error_causes": likely_causes,
        "recommended_practice_focus": dedupe_list(_coerce_list(learning.get("recommended_practice_focus")) + knowledge_points[:2]),
        "teacher_feedback_markdown": teacher_feedback,
        "mastery_update_suggestion": {
            "result": mastery_result,
            "knowledge_points": knowledge_points[:2],
            "note": primary_weakness or "Need more evidence before a precise mastery update.",
        },
        "confidence": max(float(process.get("confidence") or 0.0), float(learning.get("confidence") or 0.0), 0.55),
    }

def _build_analysis_prompt(
    *,
    case_brief: dict[str, Any],
    local_checks: dict[str, Any],
    verification_payload: dict[str, Any],
) -> str:
    verification_summary = {
        "arbiter": verification_payload.get("arbiter", {}),
        "critic": verification_payload.get("critic", {}),
        "tool_checks": verification_payload.get("tool_checks", {}),
    }
    sections = [
        "case_brief:",
        json.dumps(
            {k: v for k, v in case_brief.items() if k not in ("local_checks", "verification_payload", "bootstrap_result")},
            ensure_ascii=False,
        ),
        "",
        "local_checks:",
        json.dumps(
            {k: v for k, v in local_checks.items() if k not in ("curriculum", "knowledge")},
            ensure_ascii=False,
        ),
        "",
        "curriculum:",
        json.dumps(local_checks.get("curriculum", {}), ensure_ascii=False),
        "",
        "knowledge:",
        json.dumps(local_checks.get("knowledge", {}), ensure_ascii=False),
        "",
        "verification_summary:",
        json.dumps(verification_summary, ensure_ascii=False),
        "",
        f"请严格返回一个 JSON 对象，字段结构必须匹配：{_COMBINED_ANALYSIS_SCHEMA}",
    ]
    return "\n".join(sections)


def _build_local_case_brief(
    *,
    normalized_problem: str,
    local_checks: dict[str, Any],
    bootstrap: dict[str, Any],
    resolved_reference: str,
) -> dict[str, Any]:
    curriculum = local_checks.get("curriculum") if isinstance(local_checks.get("curriculum"), dict) else {}
    knowledge = local_checks.get("knowledge") if isinstance(local_checks.get("knowledge"), dict) else {}
    evidence_items = _coerce_list(local_checks.get("evidence_items"))
    diagnosis_focus = ["wrong answer"] if local_checks.get("wrong_answer") else []
    if local_checks.get("process_incomplete"):
        diagnosis_focus.append("过程不完整")
    if _coerce_list(local_checks.get("likely_error_causes")):
        diagnosis_focus.append("存在明显错因")
    return {
        "problem_summary": normalized_problem[:240],
        "student_state": "需要结合当前作答和核验结果判断学生状态",
        "question_type": curriculum.get("question_type", "unknown"),
        "chapter": curriculum.get("chapter", ""),
        "knowledge_points": knowledge.get("knowledge_points") or curriculum.get("knowledge_points") or [],
        "target": curriculum.get("target", ""),
        "observed_signals": evidence_items[:6],
        "diagnosis_focus": diagnosis_focus or ["答案错误", "过程不完整", "存在明显错因"],
        "evidence_gaps": ["学生过程没有完整展开"] if local_checks.get("process_incomplete") else [],
        "needs_solution_bootstrap": bool(bootstrap),
        "difficulty_band": curriculum.get("difficulty_band", ""),
        "local_checks": local_checks,
        "bootstrap_result": bootstrap,
        "reference_answer": resolved_reference,
    }


def build_math_weakness_case(
    problem_text: str,
    student_answer: str = "",
    student_work: str = "",
    reference_answer: str = "",
    error_description: str = "",
    verification_report: str = "",
    conversation_excerpt: str = "",
    grade_hint: str = "",
    supporting_images: str = "",
    student_id: str = "",
    conversation_id: str = "",
) -> dict[str, Any]:
    normalized_problem = normalize_problem_text(problem_text or conversation_excerpt)
    bootstrap, verification_payload, resolved_reference = _load_or_bootstrap_verification(
        normalized_problem,
        reference_answer,
        verification_report,
        supporting_images,
        conversation_excerpt=conversation_excerpt,
    )
    local_checks = _build_local_checks(
        problem_text=normalized_problem,
        student_answer=student_answer,
        student_work=student_work,
        error_description=error_description,
        reference_answer=resolved_reference,
        verification_payload=verification_payload,
        conversation_excerpt=conversation_excerpt,
        grade_hint=grade_hint,
    )
    case_brief = _build_local_case_brief(
        normalized_problem=normalized_problem,
        local_checks=local_checks,
        bootstrap=bootstrap,
        resolved_reference=resolved_reference,
    )
    case_brief["verification_payload"] = verification_payload
    return case_brief


def draft_math_weakness_candidates(
    problem_text: str,
    student_answer: str = "",
    student_work: str = "",
    reference_answer: str = "",
    error_description: str = "",
    verification_report: str = "",
    conversation_excerpt: str = "",
    grade_hint: str = "",
    supporting_images: str = "",
) -> dict[str, Any]:
    cfg = _load_solver_config()
    case_brief = build_math_weakness_case(
        problem_text=problem_text,
        student_answer=student_answer,
        student_work=student_work,
        reference_answer=reference_answer,
        error_description=error_description,
        verification_report=verification_report,
        conversation_excerpt=conversation_excerpt,
        grade_hint=grade_hint,
        supporting_images=supporting_images,
    )
    analysis_prompt = _build_analysis_prompt(
        case_brief=case_brief,
        local_checks=case_brief["local_checks"],
        verification_payload=case_brief["verification_payload"],
    )
    analysis_candidate = _call_qwen_json(
        cfg=cfg,
        system_prompt=_COMBINED_ANALYSIS_PROMPT,
        user_prompt=analysis_prompt,
        enable_thinking=cfg.get("critic_enable_thinking", True),
        supporting_images=_resolve_supporting_images(supporting_images),
    )
    return {
        "case_brief": case_brief,
        "analysis_candidate": analysis_candidate,
    }


def verify_math_weakness_candidates(
    problem_text: str,
    student_answer: str = "",
    student_work: str = "",
    reference_answer: str = "",
    error_description: str = "",
    verification_report: str = "",
    conversation_excerpt: str = "",
    grade_hint: str = "",
    supporting_images: str = "",
) -> dict[str, Any]:
    drafted = draft_math_weakness_candidates(
        problem_text=problem_text,
        student_answer=student_answer,
        student_work=student_work,
        reference_answer=reference_answer,
        error_description=error_description,
        verification_report=verification_report,
        conversation_excerpt=conversation_excerpt,
        grade_hint=grade_hint,
        supporting_images=supporting_images,
    )
    case_brief = drafted["case_brief"]
    local_checks = case_brief.get("local_checks", {})
    analysis_candidate = drafted.get("analysis_candidate", {}) if isinstance(drafted.get("analysis_candidate", {}), dict) else {}
    process = _merge_candidate_with_fallback(
        analysis_candidate.get("process", {}),
        _fallback_process(case_brief, local_checks),
    )
    learning = _merge_candidate_with_fallback(
        analysis_candidate.get("learning", {}),
        _fallback_learning(case_brief, local_checks),
    )
    arbiter = _merge_candidate_with_fallback(
        analysis_candidate.get("arbiter", {}),
        _fallback_arbiter(case_brief, process, learning, local_checks),
    )
    return {
        "case_brief": case_brief,
        "process": process,
        "learning": learning,
        "arbiter": arbiter,
        "local_checks": local_checks,
    }


def _build_teacher_feedback(problem_text: str, arbiter: dict[str, Any]) -> str:
    body = str(arbiter.get("teacher_feedback_markdown") or "").strip()
    if body:
        return body
    return (
        "# Weakness Diagnosis\n\n"
        f"## Problem\n{normalize_problem_text(problem_text)}\n\n"
        f"## Primary weakness\n{arbiter.get('primary_weakness', '')}\n\n"
        f"## Missing steps\n"
        + "\n".join(f"- {item}" for item in arbiter.get("missing_steps", []))
        + "\n\n## Practice focus\n"
        + "\n".join(f"- {item}" for item in arbiter.get("recommended_practice_focus", []))
    )


def run_math_weakness_diagnosis_agent(
    problem_text: str,
    student_answer: str = "",
    student_work: str = "",
    reference_answer: str = "",
    error_description: str = "",
    verification_report: str = "",
    conversation_excerpt: str = "",
    grade_hint: str = "",
    supporting_images: str = "",
    student_id: str = "",
    conversation_id: str = "",
) -> dict[str, Any]:
    cfg = _load_solver_config()
    run_dir = _new_run_dir(problem_text or conversation_excerpt or "weakness")
    verified = verify_math_weakness_candidates(
        problem_text=problem_text,
        student_answer=student_answer,
        student_work=student_work,
        reference_answer=reference_answer,
        error_description=error_description,
        verification_report=verification_report,
        conversation_excerpt=conversation_excerpt,
        grade_hint=grade_hint,
        supporting_images=supporting_images,
    )
    case_brief = verified["case_brief"]
    process = verified["process"]
    learning = verified["learning"]
    local_checks = verified["local_checks"]
    arbiter = verified["arbiter"]
    mastery_update = arbiter.get("mastery_update_suggestion") if isinstance(arbiter.get("mastery_update_suggestion"), dict) else {}
    global_memory_event = update_global_learning_memory(
        student_id=student_id,
        primary_weakness=str(arbiter.get("primary_weakness") or "").strip(),
        secondary_weaknesses=_coerce_list(arbiter.get("secondary_weaknesses")),
        knowledge_points=_coerce_list(mastery_update.get("knowledge_points")) or _coerce_list(arbiter.get("knowledge_points")),
        prerequisite_gaps=_coerce_list(arbiter.get("prerequisite_gaps")),
        practice_focus=_coerce_list(arbiter.get("recommended_practice_focus")),
        result=str(
            mastery_update.get("result")
            or ("incorrect" if arbiter.get("wrong_answer") else ("partial" if arbiter.get("process_incomplete") else "hinted"))
        ).strip(),
        note=str(mastery_update.get("note") or arbiter.get("primary_weakness") or "").strip(),
        evidence=_coerce_list(arbiter.get("evidence_items")),
        source="weakness_diag",
        conversation_id=conversation_id,
    )
    teacher_feedback = _build_teacher_feedback(problem_text or conversation_excerpt, arbiter)
    teacher_feedback_path = run_dir / "TeacherFeedback.md"
    teacher_feedback_path.write_text(teacher_feedback, encoding="utf-8")

    weakness_report = {
        "pipeline": "WeaknessDiag-Q3VL",
        "problem_text": normalize_problem_text(problem_text or conversation_excerpt),
        "case_brief": {k: v for k, v in case_brief.items() if k not in {"local_checks", "verification_payload", "bootstrap_result"}},
        "process": process,
        "learning": learning,
        "arbiter": arbiter,
        "global_memory_event": global_memory_event,
    }
    weakness_report_path = run_dir / "WeaknessReport.json"
    _write_json(weakness_report_path, weakness_report)

    diagnosis_audit = {
        "pipeline": "WeaknessDiag-Q3VL",
        "run_dir": str(run_dir),
        "model": cfg.get("model_name", _DEFAULT_DIAG_MODEL),
        "status": arbiter.get("status", "review"),
        "primary_weakness": arbiter.get("primary_weakness", ""),
        "CaseBrief_json_path": _write_json(run_dir / "case_brief.json", {k: v for k, v in case_brief.items() if k not in {"local_checks", "verification_payload", "bootstrap_result"}}),
        "LocalChecks_json_path": _write_json(run_dir / "local_checks.json", {k: v for k, v in local_checks.items() if k not in {"curriculum", "knowledge"}}),
        "Process_json_path": _write_json(run_dir / "process.json", process),
        "Learning_json_path": _write_json(run_dir / "learning.json", learning),
        "TeacherFeedback_md_path": str(teacher_feedback_path),
        "WeaknessReport_json_path": str(weakness_report_path),
        "GlobalLearningMemory_json_path": str(global_memory_event.get("memory_path") or "").strip(),
        "global_memory_event": global_memory_event,
    }
    bootstrap_result = case_brief.get("bootstrap_result") if isinstance(case_brief.get("bootstrap_result"), dict) else {}
    if bootstrap_result:
        diagnosis_audit["bootstrap_result"] = bootstrap_result
    if case_brief.get("verification_payload"):
        diagnosis_audit["BootstrapVerification_json_path"] = _write_json(run_dir / "bootstrap_verification.json", case_brief["verification_payload"])
    diagnosis_audit_path = run_dir / "DiagnosisAudit.json"
    _write_json(diagnosis_audit_path, diagnosis_audit)
    diagnosis_audit["DiagnosisAudit_json_path"] = str(diagnosis_audit_path)
    diagnosis_audit["status"] = arbiter.get("status", "review")
    diagnosis_audit["primary_weakness"] = arbiter.get("primary_weakness", "")
    return diagnosis_audit


def diagnose_math_weakness(
    problem_text: str,
    student_answer: str = "",
    correct_answer: str = "",
    error_description: str = "",
    grade_hint: str = "",
    student_work: str = "",
    conversation_excerpt: str = "",
    verification_report: str = "",
    supporting_images: str = "",
    student_id: str = "",
    conversation_id: str = "",
) -> dict[str, Any]:
    result = run_math_weakness_diagnosis_agent(
        problem_text=problem_text,
        student_answer=student_answer,
        student_work=student_work,
        reference_answer=correct_answer,
        error_description=error_description,
        verification_report=verification_report,
        conversation_excerpt=conversation_excerpt,
        grade_hint=grade_hint,
        supporting_images=supporting_images,
        student_id=student_id,
        conversation_id=conversation_id,
    )
    report = _load_json_input(result.get("WeaknessReport_json_path"))
    arbiter = report.get("arbiter") if isinstance(report.get("arbiter"), dict) else {}
    return {
        "chapter": str(arbiter.get("chapter") or "").strip(),
        "knowledge_point": (_coerce_list(arbiter.get("knowledge_points")) or [""])[0],
        "prerequisites": _coerce_list(arbiter.get("prerequisite_gaps")),
        "difficulty": str((report.get("case_brief") or {}).get("difficulty_band") or "").strip(),
        "likely_error_causes": _coerce_list(arbiter.get("likely_error_causes")),
        "question_type": str(arbiter.get("question_type") or "").strip(),
        "primary_weakness": str(arbiter.get("primary_weakness") or "").strip(),
        "secondary_weaknesses": _coerce_list(arbiter.get("secondary_weaknesses")),
        "wrong_answer": bool(arbiter.get("wrong_answer")),
        "process_incomplete": bool(arbiter.get("process_incomplete")),
        "missing_steps": _coerce_list(arbiter.get("missing_steps")),
        "evidence_items": _coerce_list(arbiter.get("evidence_items")),
        "recommended_practice_focus": _coerce_list(arbiter.get("recommended_practice_focus")),
        "TeacherFeedback_md_path": str(result.get("TeacherFeedback_md_path") or "").strip(),
        "WeaknessReport_json_path": str(result.get("WeaknessReport_json_path") or "").strip(),
        "DiagnosisAudit_json_path": str(result.get("DiagnosisAudit_json_path") or "").strip(),
        "GlobalLearningMemory_json_path": str(result.get("GlobalLearningMemory_json_path") or "").strip(),
        "status": str(result.get("status") or arbiter.get("status") or "review").strip(),
    }
