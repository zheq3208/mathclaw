"""Variant generation agent system for math tutoring using Qwen3-VL-Plus."""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from ...constant import WORKING_DIR
from .math_learning import summarize_global_learning_memory_cn
from .math_utils import difficulty_band, estimate_difficulty_score, normalize_problem_text
from .solve_verify_q3vl import _call_qwen_json, _load_solver_config, _resolve_supporting_images

_SIMPLE_VARIANT_SCHEMA = {
    "status": "generated|review",
    "basis": "当前错误|历史薄弱点",
    "judgement": "str",
    "variant_markdown": "str",
    "variants": [
        {
            "variant_type": "相同结构|降低难度|提高一点难度",
            "problem_text": "str",
            "brief_answer": "str",
        }
    ],
}

_SIMPLE_VARIANT_PROMPT = """
你是一名数学练习设计老师。
请根据原题、求解与验证结果、历史薄弱点和用户需求，生成三道直接可做的中文练习题。
要求：
- 只返回一个 JSON 对象。
- 所有自然语言字段都使用简体中文。
- 固定给出三题：相同结构、降低难度、提高一点难度。
- 如果当前结果里有错误，优先围绕当前错误来出题。
- 如果当前结果整体正确，就优先围绕历史薄弱点来出题。
- 不要写英文标题，不要写工具痕迹。
""".strip()


def _variant_runs_dir() -> Path:
    path = Path(WORKING_DIR) / "variant_generation_runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", str(text or "").strip()).strip("-")
    return slug.lower() or "variant"


def _new_run_dir(seed_text: str) -> Path:
    run_dir = _variant_runs_dir() / f"{int(time.time())}-{_slugify(seed_text[:48])}-{uuid.uuid4().hex[:8]}"
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


def build_variant_generation_case(
    problem_text: str,
    variant_request: str = "",
    target_skill: str = "",
    requested_count: int = 3,
    grade_hint: str = "",
    weakness_report: str = "",
    supporting_images: str = "",
    student_id: str = "",
    original_prompt: str = "",
    solve_summary: str = "",
) -> dict[str, Any]:
    memory_payload = summarize_global_learning_memory_cn(student_id)
    return {
        "problem_text": normalize_problem_text(problem_text),
        "variant_request": str(variant_request or original_prompt or "").strip() or "请生成三道变式题。",
        "target_skill": str(target_skill or "").strip(),
        "requested_count": int(requested_count or 3),
        "grade_hint": str(grade_hint or "").strip(),
        "weakness_report": str(weakness_report or "").strip(),
        "supporting_images": str(supporting_images or "").strip(),
        "student_id": str(student_id or "").strip(),
        "original_prompt": str(original_prompt or "").strip(),
        "solve_summary": str(solve_summary or "").strip(),
        "memory_summary": str(memory_payload.get("summary_text") or "当前还没有明显的历史薄弱点记录。"),
    }


def _build_variant_prompt(case: dict[str, Any]) -> str:
    parts = [
        f"用户原始需求：{case.get('original_prompt') or case.get('variant_request') or '未提供'}",
        f"历史薄弱点记忆：\n{case.get('memory_summary') or '当前还没有明显的历史薄弱点记录。'}",
        f"题目内容：\n{case.get('problem_text') or ''}",
    ]
    if case.get("weakness_report"):
        parts.append(f"当前薄弱点诊断：\n{case['weakness_report']}")
    if case.get("solve_summary"):
        parts.append(f"求解与验证结果：\n{case['solve_summary']}")
    if case.get("grade_hint"):
        parts.append(f"年级提示：{case['grade_hint']}")
    parts.append(f"请按这个结构输出：{json.dumps(_SIMPLE_VARIANT_SCHEMA, ensure_ascii=False)}")
    previous = case.get("solve_summary") or case.get("weakness_report")
    return "\n\n".join(parts) + _simple_chain_suffix(previous)


def _normalize_variant_payload(payload: dict[str, Any]) -> dict[str, Any]:
    variants = []
    for item in (payload.get("variants") or []):
        if not isinstance(item, dict):
            continue
        variants.append(
            {
                "variant_type": str(item.get("variant_type") or "").strip(),
                "problem_text": str(item.get("problem_text") or "").strip(),
                "brief_answer": str(item.get("brief_answer") or "").strip(),
            }
        )
    markdown = str(payload.get("variant_markdown") or "").strip()
    if not markdown and variants:
        blocks = []
        for idx, item in enumerate(variants[:3], start=1):
            text = f"{idx}. {item['variant_type']}\n{item['problem_text']}"
            if item['brief_answer']:
                text += f"\n参考答案：{item['brief_answer']}"
            blocks.append(text)
        markdown = "\n\n".join(blocks)
    if not markdown:
        markdown = "这次还不能稳定生成变式题，请把题目再裁清楚一点发给我。"
    return {
        "status": str(payload.get("status") or "generated").strip() or "generated",
        "basis": str(payload.get("basis") or "").strip() or "历史薄弱点",
        "judgement": str(payload.get("judgement") or "").strip(),
        "variant_markdown": markdown,
        "variants": variants,
    }


def draft_problem_variants(
    problem_text: str,
    variant_request: str = "",
    target_skill: str = "",
    requested_count: int = 3,
    grade_hint: str = "",
    weakness_report: str = "",
    supporting_images: str = "",
    student_id: str = "",
    original_prompt: str = "",
    solve_summary: str = "",
) -> dict[str, Any]:
    case = build_variant_generation_case(
        problem_text=problem_text,
        variant_request=variant_request,
        target_skill=target_skill,
        requested_count=requested_count,
        grade_hint=grade_hint,
        weakness_report=weakness_report,
        supporting_images=supporting_images,
        student_id=student_id,
        original_prompt=original_prompt,
        solve_summary=solve_summary,
    )
    cfg = _load_solver_config()
    return _call_qwen_json(
        cfg=cfg,
        system_prompt=_SIMPLE_VARIANT_PROMPT,
        user_prompt=_build_variant_prompt(case),
        enable_thinking=True,
        supporting_images=_resolve_supporting_images(supporting_images),
    )


def verify_problem_variants(problem_text: str = "", variant_payload: Any = None, **_: Any) -> dict[str, Any]:
    payload = variant_payload if isinstance(variant_payload, dict) else {}
    return _normalize_variant_payload(payload)


def calibrate_problem_difficulty(problem_text: str = "", variant_payload: Any = None, reference_problem: str = "", **_: Any) -> dict[str, Any]:
    source_score = estimate_difficulty_score(problem_text)
    reference_score = estimate_difficulty_score(reference_problem or problem_text)
    relation = "差不多"
    if source_score > reference_score + 0.12:
        relation = "更难"
    elif source_score < reference_score - 0.12:
        relation = "更简单"
    return {
        "source_score": source_score,
        "reference_score": reference_score,
        "difficulty_relation": relation,
        "difficulty_band": difficulty_band(source_score),
    }


def run_problem_variant_agent(
    problem_text: str,
    variant_request: str = "",
    target_skill: str = "",
    requested_count: int = 3,
    grade_hint: str = "",
    weakness_report: str = "",
    supporting_images: str = "",
    student_id: str = "",
    original_prompt: str = "",
    solve_summary: str = "",
) -> dict[str, Any]:
    run_dir = _new_run_dir(problem_text or variant_request or "variant")
    case = build_variant_generation_case(
        problem_text=problem_text,
        variant_request=variant_request,
        target_skill=target_skill,
        requested_count=requested_count,
        grade_hint=grade_hint,
        weakness_report=weakness_report,
        supporting_images=supporting_images,
        student_id=student_id,
        original_prompt=original_prompt,
        solve_summary=solve_summary,
    )
    raw = draft_problem_variants(
        problem_text=problem_text,
        variant_request=variant_request,
        target_skill=target_skill,
        requested_count=requested_count,
        grade_hint=grade_hint,
        weakness_report=weakness_report,
        supporting_images=supporting_images,
        student_id=student_id,
        original_prompt=original_prompt,
        solve_summary=solve_summary,
    )
    payload = _normalize_variant_payload(raw if isinstance(raw, dict) else {})
    md_path = run_dir / 'VariantSet.md'
    md_path.write_text(payload['variant_markdown'], encoding='utf-8')
    bundle_path = run_dir / 'VariantBundle.json'
    audit_path = run_dir / 'VariantAudit.json'
    _write_json(bundle_path, {**payload, 'raw': raw, 'case': case})
    _write_json(audit_path, {'pipeline': 'VariantGen-Q3VL', 'run_dir': str(run_dir), 'basis': payload['basis'], 'variant_count': len(payload['variants']), 'VariantSet_md_path': str(md_path), 'VariantBundle_json_path': str(bundle_path)})
    return {
        'run_dir': str(run_dir),
        'VariantSet_md_path': str(md_path),
        'VariantBundle_json_path': str(bundle_path),
        'VariantAudit_json_path': str(audit_path),
        **payload,
    }


def generate_problem_variants(
    problem_text: str,
    variant_request: str = "",
    target_skill: str = "",
    requested_count: int = 3,
    grade_hint: str = "",
    weakness_report: str = "",
    supporting_images: str = "",
    student_id: str = "",
    original_prompt: str = "",
    solve_summary: str = "",
) -> dict[str, Any]:
    return run_problem_variant_agent(
        problem_text=problem_text,
        variant_request=variant_request,
        target_skill=target_skill,
        requested_count=requested_count,
        grade_hint=grade_hint,
        weakness_report=weakness_report,
        supporting_images=supporting_images,
        student_id=student_id,
        original_prompt=original_prompt,
        solve_summary=solve_summary,
    )
