"""Guided explanation agent system for math tutoring using Qwen3-VL-Plus."""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from ...constant import WORKING_DIR
from .math_learning import summarize_global_learning_memory_cn
from .math_utils import normalize_problem_text
from .solve_verify_q3vl import _call_qwen_json, _load_solver_config, _resolve_supporting_images

_SIMPLE_GUIDED_SCHEMA = {
    "status": "guided|review",
    "teacher_response_markdown": "str",
    "core_breakthrough_points": ["str"],
    "next_step_question": "str",
    "memory_focus": ["str"],
    "hint_level": 1,
}

_SIMPLE_GUIDED_PROMPT = """
你是一名擅长讲题的数学老师。
请读取原题、求解与验证结果、历史薄弱点和当前需求，生成一段可以直接发给学生的中文讲解。
要求：
- 只返回一个 JSON 对象。
- 所有自然语言字段都使用简体中文。
- 讲解必须建立在现有求解过程之上，再补充几句核心突破点。
- 讲解要自然，不要写英文标题，不要写工具痕迹。
- 如果信息不足，就明确指出还缺什么，不要假装已经完全看懂。
""".strip()


def _guided_runs_dir() -> Path:
    path = Path(WORKING_DIR) / "guided_explanation_runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", str(text or "").strip()).strip("-")
    return slug.lower() or "guided"


def _new_run_dir(seed_text: str) -> Path:
    run_dir = _guided_runs_dir() / f"{int(time.time())}-{_slugify(seed_text[:48])}-{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _simple_chain_suffix(previous_output: Any) -> str:
    if previous_output in (None, "", [], {}):
        return ""
    if isinstance(previous_output, (dict, list)):
        text = json.dumps(previous_output, ensure_ascii=False)
    else:
        text = str(previous_output)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    if len(text) > 8000:
        text = text[:8000].rstrip() + "..."
    return f"\n\n这是基于上一次跟你讨论总结的内容{text}"


def choose_hint_level(
    current_level: int | None = None,
    attempts: int | None = None,
    requested_full_solution: bool = False,
    student_progress: str = "",
    student_reply: str = "",
    latest_student_reply: str = "",
    requested_hint_level: int = 1,
    **_: Any,
) -> dict[str, Any]:
    level = int(current_level or requested_hint_level or 1)
    level = max(1, min(level, 4))
    text = f"{student_progress}\n{student_reply}\n{latest_student_reply}".strip()
    if requested_full_solution:
        level = 4
        reason = "用户明确要求完整讲解。"
    elif any(token in text for token in ["还是不会", "不会", "卡住", "没思路", "看不懂"]):
        bump = 2 if int(attempts or 0) >= 3 else 1
        level = min(4, max(level, 1) + bump)
        reason = "学生当前卡住，需要提高提示层级。"
    elif any(token in text for token in ["我懂了", "明白了", "我会了"]):
        level = max(1, level - 1)
        reason = "学生已有进展，可以保持轻提示。"
    else:
        reason = "保持当前提示层级。"
    return {"hint_level": level, "reason": reason}


def build_guided_explanation_case(
    problem_text: str,
    student_attempt: str = "",
    learning_goal: str = "",
    requested_hint_level: int = 1,
    latest_student_reply: str = "",
    conversation_excerpt: str = "",
    verification_report: str = "",
    weakness_report: str = "",
    supporting_images: str = "",
    student_id: str = "",
    original_prompt: str = "",
) -> dict[str, Any]:
    hint_meta = choose_hint_level(
        requested_hint_level=requested_hint_level,
        latest_student_reply=latest_student_reply,
        student_reply=student_attempt,
    )
    memory_payload = summarize_global_learning_memory_cn(student_id)
    return {
        "problem_text": normalize_problem_text(problem_text),
        "student_attempt": str(student_attempt or "").strip(),
        "learning_goal": str(learning_goal or "").strip() or "请基于已有求解过程做引导式讲解。",
        "hint_level": int(hint_meta["hint_level"]),
        "hint_reason": str(hint_meta["reason"]),
        "latest_student_reply": str(latest_student_reply or "").strip(),
        "conversation_excerpt": str(conversation_excerpt or "").strip(),
        "verification_report": str(verification_report or "").strip(),
        "weakness_report": str(weakness_report or "").strip(),
        "supporting_images": str(supporting_images or "").strip(),
        "student_id": str(student_id or "").strip(),
        "original_prompt": str(original_prompt or "").strip(),
        "memory_summary": str(memory_payload.get("summary_text") or "当前还没有明显的历史薄弱点记录。"),
    }


def _build_guided_prompt(case: dict[str, Any]) -> str:
    parts = [
        f"用户原始需求：{case.get('original_prompt') or '未提供'}",
        f"引导目标：{case.get('learning_goal') or '请做引导式讲解'}",
        f"当前提示层级：{case.get('hint_level')}",
        f"层级原因：{case.get('hint_reason')}",
        f"历史薄弱点记忆：\n{case.get('memory_summary') or '当前还没有明显的历史薄弱点记录。'}",
        f"题目内容：\n{case.get('problem_text') or ''}",
    ]
    if case.get("student_attempt"):
        parts.append(f"学生当前作答：\n{case['student_attempt']}")
    if case.get("verification_report"):
        parts.append(f"求解与验证结果：\n{case['verification_report']}")
    if case.get("weakness_report"):
        parts.append(f"当前薄弱点诊断：\n{case['weakness_report']}")
    if case.get("conversation_excerpt"):
        parts.append(f"当前对话摘要：\n{case['conversation_excerpt']}")
    parts.append(f"请按这个结构输出：{json.dumps(_SIMPLE_GUIDED_SCHEMA, ensure_ascii=False)}")
    previous = case.get("weakness_report") or case.get("verification_report")
    return "\n\n".join(parts) + _simple_chain_suffix(previous)


def _normalize_guided_payload(payload: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    response = str(payload.get("teacher_response_markdown") or payload.get("user_text") or "").strip()
    if not response:
        response = "这次还不能稳定生成讲解，请把题目再裁清楚一点发给我。"
    return {
        "status": str(payload.get("status") or "guided").strip() or "guided",
        "teacher_response_markdown": response,
        "core_breakthrough_points": [str(v).strip() for v in (payload.get("core_breakthrough_points") or []) if str(v).strip()],
        "next_step_question": str(payload.get("next_step_question") or "").strip(),
        "memory_focus": [str(v).strip() for v in (payload.get("memory_focus") or []) if str(v).strip()],
        "hint_level": int(payload.get("hint_level") or case.get("hint_level") or 1),
    }


def plan_guided_explanation(**kwargs: Any) -> dict[str, Any]:
    return build_guided_explanation_case(**kwargs)


def generate_socratic_turn(problem_text: str = "", guided_payload: Any = None, **kwargs: Any) -> dict[str, Any]:
    if isinstance(guided_payload, dict):
        case = {"hint_level": guided_payload.get("hint_level") or 1}
        return _normalize_guided_payload(guided_payload, case)
    return run_guided_explanation_agent(problem_text=problem_text, **kwargs)


def run_guided_explanation_agent(
    problem_text: str,
    student_attempt: str = "",
    learning_goal: str = "",
    requested_hint_level: int = 1,
    latest_student_reply: str = "",
    conversation_excerpt: str = "",
    verification_report: str = "",
    weakness_report: str = "",
    supporting_images: str = "",
    student_id: str = "",
    original_prompt: str = "",
) -> dict[str, Any]:
    run_dir = _new_run_dir(problem_text or learning_goal or "guided")
    case = build_guided_explanation_case(
        problem_text=problem_text,
        student_attempt=student_attempt,
        learning_goal=learning_goal,
        requested_hint_level=requested_hint_level,
        latest_student_reply=latest_student_reply,
        conversation_excerpt=conversation_excerpt,
        verification_report=verification_report,
        weakness_report=weakness_report,
        supporting_images=supporting_images,
        student_id=student_id,
        original_prompt=original_prompt,
    )
    cfg = _load_solver_config()
    payload = _call_qwen_json(
        cfg=cfg,
        system_prompt=_SIMPLE_GUIDED_PROMPT,
        user_prompt=_build_guided_prompt(case),
        enable_thinking=True,
        supporting_images=_resolve_supporting_images(supporting_images),
    )
    result = _normalize_guided_payload(payload if isinstance(payload, dict) else {}, case)
    md_path = run_dir / 'GuidedExplanation.md'
    md_path.write_text(result['teacher_response_markdown'], encoding='utf-8')
    payload_path = run_dir / 'GuidedPayload.json'
    audit_path = run_dir / 'GuidedAudit.json'
    _write_json(payload_path, {**result, 'raw': payload, 'case': case})
    _write_json(audit_path, {'pipeline': 'GuidedExplain-Q3VL', 'run_dir': str(run_dir), 'hint_level': result['hint_level'], 'GuidedExplanation_md_path': str(md_path), 'GuidedPayload_json_path': str(payload_path)})
    return {
        'run_dir': str(run_dir),
        'GuidedExplanation_md_path': str(md_path),
        'GuidedPayload_json_path': str(payload_path),
        'GuidedAudit_json_path': str(audit_path),
        **result,
    }
