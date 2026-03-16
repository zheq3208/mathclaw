from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any

import fitz

from ..constant import WORKING_DIR
from .tools.math_learning import get_global_learning_memory, summarize_global_learning_memory_cn
from .tools.mess_to_clean_q3vl import _call_vl_json, _load_ocr_config
from .tools.solve_verify_q3vl import (
    _call_qwen_json,
    _client_from_config,
    _image_to_data_url,
    _load_solver_config,
    _message_to_text,
    _model_candidates,
)

logger = logging.getLogger(__name__)

_CHAIN_SENTENCE = "这是基于上一次跟你讨论总结的内容{}"

_OCR_STAGE1_SCHEMA = {
    "type": "object",
    "properties": {
        "boxes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "kind": {"type": "string"},
                    "bbox": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
                    "text_hint": {"type": "string"},
                },
                "required": ["kind", "bbox"],
            },
        },
        "page_note": {"type": "string"},
    },
    "required": ["boxes"],
}

_OCR_STAGE2_SCHEMA = {
    "type": "object",
    "properties": {
        "paper_title": {"type": "string"},
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question_id": {"type": "string"},
                    "question_text": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "student_answer": {"type": "string"},
                },
                "required": ["question_id", "question_text"],
            },
        },
        "page_summary": {"type": "string"},
    },
    "required": ["questions"],
}

_SOLVE_STAGE1_SCHEMA = {
    "problem_overview": "字符串",
    "problems": [
        {
            "question_id": "字符串",
            "problem_text": "字符串",
            "student_answer": "字符串",
            "candidate_methods": ["字符串"],
            "verification_plan": ["字符串"],
        }
    ],
}

_SOLVE_STAGE2_SCHEMA = {
    "all_correct": True,
    "overall_comment": "字符串",
    "knowledge_points": ["字符串"],
    "current_weaknesses": ["字符串"],
    "problems": [
        {
            "question_id": "字符串",
            "judgement": "正确/错误/存疑",
            "student_answer": "字符串",
            "correct_answer": "字符串",
            "why": "字符串",
            "solution": "字符串",
            "knowledge_point": "字符串",
            "is_wrong": False,
        }
    ],
}

_WEAKNESS_SCHEMA = {
    "all_correct": True,
    "correct_points": ["字符串"],
    "error_points": ["字符串"],
    "primary_weakness": "字符串",
    "knowledge_points": ["字符串"],
    "practice_focus": ["字符串"],
    "user_text": "直接发给用户的一段中文",
}

_GUIDED_SCHEMA = {
    "hint_level": 1,
    "core_breakthrough_points": ["字符串"],
    "user_text": "直接发给用户的一段中文",
}

_VARIANT_SCHEMA = {
    "user_text": "\u76f4\u63a5\u53d1\u7ed9\u5b66\u751f\u7684\u5b8c\u6574\u4e2d\u6587\u7ec3\u4e60\u5185\u5bb9\uff0c\u5fc5\u987b\u76f4\u63a5\u5199\u51fa\u4e09\u9053\u9898\u3002",
}


def _contains_search_request(message: str) -> bool:
    return "搜索" in str(message or "")


def _contains_grading_request(message: str) -> bool:
    text = str(message or "")
    return any(token in text for token in ("批改", "判卷", "阅卷", "改卷", "批阅", "分析试卷"))


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _contains_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", str(text or "")))


def _looks_garbled(text: str) -> bool:
    value = str(text or "").strip()
    if not value:
        return True
    if not _contains_chinese(value) and value.count("?") >= max(3, len(value) // 4):
        return True
    only_noise = re.sub(r"[?？\s\n\r]+", "", value)
    if not only_noise:
        return True
    return False


def _chain_suffix(previous_content: Any) -> str:
    if previous_content is None:
        return ""
    if isinstance(previous_content, (dict, list)):
        text = json.dumps(previous_content, ensure_ascii=False)
    else:
        text = str(previous_content).strip()
    text = text.strip()
    if not text:
        return ""
    return "\n\n" + _CHAIN_SENTENCE.format(text)


def _pipeline_runs_dir() -> Path:
    path = Path(WORKING_DIR) / "exam_pipeline_v2_runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", str(text or "").strip()).strip("-")
    return slug.lower() or "exam"


def _new_run_dir(source: str, session_id: str = "") -> Path:
    stem = _slugify(Path(str(source or "input")).stem)
    suffix = _slugify(session_id)[:24] if session_id else uuid.uuid4().hex[:8]
    run_dir = _pipeline_runs_dir() / f"{int(time.time())}-{stem}-{suffix}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(text or "").strip(), encoding="utf-8")
    return str(path)




def _call_qwen_text(*, cfg: dict[str, Any], system_prompt: str, user_prompt: str, enable_thinking: bool, supporting_images: list[Path] | None = None) -> str:
    client = _client_from_config(cfg)
    content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
    for image_path in list(supporting_images or []):
        content.append({"type": "image_url", "image_url": {"url": _image_to_data_url(Path(image_path))}})
    last_error: Exception | None = None
    for model_name in _model_candidates(cfg):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content},
                ],
                temperature=cfg.get("temperature", 0.2),
                extra_body={"enable_thinking": bool(enable_thinking)},
            )
            message = response.choices[0].message if response.choices else None
            return _message_to_text(getattr(message, "content", None)).strip()
        except Exception as exc:
            last_error = exc
            logger.debug("qwen text call failed for model=%s", model_name, exc_info=True)
    raise RuntimeError(f"Qwen text call failed: {last_error}") from last_error

def _prepare_visual_source(source: str, run_dir: Path) -> Path:
    path = Path(str(source or "").strip())
    if not path.exists():
        raise FileNotFoundError(f"visual source not found: {path}")
    if path.suffix.lower() != ".pdf":
        return path
    doc = fitz.open(str(path))
    try:
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        out = run_dir / "source_page_1.png"
        pix.save(str(out))
        return out
    finally:
        doc.close()


def _coerce_boxes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    boxes: list[dict[str, Any]] = []
    for idx, item in enumerate(payload.get("boxes") or [], start=1):
        if not isinstance(item, dict):
            continue
        bbox = item.get("bbox") or []
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        try:
            coords = [int(round(float(v))) for v in bbox]
        except Exception:
            continue
        boxes.append(
            {
                "id": str(item.get("id") or f"b{idx}").strip() or f"b{idx}",
                "kind": str(item.get("kind") or "文本块").strip() or "文本块",
                "bbox": coords,
                "text_hint": str(item.get("text_hint") or "").strip(),
            }
        )
    return boxes


def _coerce_questions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for idx, item in enumerate(payload.get("questions") or [], start=1):
        if not isinstance(item, dict):
            continue
        question_text = _first_non_empty(item.get("question_text"), item.get("question"), item.get("stem"))
        if not question_text:
            continue
        options = [str(v).strip() for v in (item.get("options") or []) if str(v).strip()]
        questions.append(
            {
                "question_id": str(item.get("question_id") or item.get("id") or idx).strip() or str(idx),
                "question_text": question_text,
                "options": options,
                "student_answer": str(item.get("student_answer") or "").strip(),
            }
        )
    return questions


def _questions_brief(questions: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in questions:
        line = f"题号：{item['question_id']}\n题目：{item['question_text']}"
        if item.get("options"):
            line += "\n选项：" + "；".join(item["options"])
        if item.get("student_answer"):
            line += "\n学生作答：" + item["student_answer"]
        lines.append(line)
    return "\n\n".join(lines).strip()


def _fallback_plan_from_questions(questions: list[dict[str, Any]]) -> dict[str, Any]:
    problems = []
    for item in questions:
        problems.append(
            {
                "question_id": item["question_id"],
                "problem_text": item["question_text"],
                "student_answer": item.get("student_answer", ""),
                "candidate_methods": ["先判断题型，再求出正确答案，最后和学生作答对比"],
                "verification_plan": ["先独立解题，再核对学生答案和关键步骤是否一致"],
            }
        )
    return {"problem_overview": "根据 OCR 结果整理出的待批改题目", "problems": problems}


def _coerce_solve_result(payload: dict[str, Any]) -> dict[str, Any]:
    problems: list[dict[str, Any]] = []
    for idx, item in enumerate(payload.get("problems") or [], start=1):
        if not isinstance(item, dict):
            continue
        problems.append(
            {
                "question_id": str(item.get("question_id") or idx).strip() or str(idx),
                "judgement": str(item.get("judgement") or "存疑").strip() or "存疑",
                "student_answer": str(item.get("student_answer") or "").strip(),
                "correct_answer": str(item.get("correct_answer") or "").strip(),
                "why": str(item.get("why") or "").strip(),
                "solution": str(item.get("solution") or "").strip(),
                "knowledge_point": str(item.get("knowledge_point") or "").strip(),
                "is_wrong": bool(item.get("is_wrong")),
            }
        )
    return {
        "all_correct": bool(payload.get("all_correct")),
        "overall_comment": str(payload.get("overall_comment") or "").strip(),
        "knowledge_points": [str(v).strip() for v in (payload.get("knowledge_points") or []) if str(v).strip()],
        "current_weaknesses": [str(v).strip() for v in (payload.get("current_weaknesses") or []) if str(v).strip()],
        "problems": problems,
    }


def _render_weakness_fallback(solve_result: dict[str, Any], memory_summary: str) -> str:
    wrong = [item for item in solve_result.get("problems") or [] if item.get("is_wrong")]
    correct = [item for item in solve_result.get("problems") or [] if not item.get("is_wrong")]
    parts: list[str] = []
    overall = str(solve_result.get("overall_comment") or "").strip()
    if overall:
        parts.append(overall)
    if correct:
        parts.append("这次做对的部分：" + "；".join(f"第{item['question_id']}题{item.get('judgement') or ''}" for item in correct[:3]))
    if wrong:
        parts.append("这次需要重点回看的部分：" + "；".join(f"第{item['question_id']}题{item.get('why') or item.get('judgement') or '存在错误'}" for item in wrong[:3]))
    weaknesses = [str(v).strip() for v in (solve_result.get("current_weaknesses") or []) if str(v).strip()]
    if weaknesses:
        parts.append("当前最核心的薄弱点：" + "、".join(weaknesses[:3]))
    if memory_summary:
        parts.append(memory_summary)
    return "\n\n".join(part for part in parts if part).strip() or "这次已经完成批改，但还没有稳定总结出薄弱点。"


def _render_guided_fallback(solve_result: dict[str, Any], memory_summary: str) -> str:
    target = None
    for item in solve_result.get("problems") or []:
        if item.get("is_wrong"):
            target = item
            break
    if target is None:
        target = (solve_result.get("problems") or [{}])[0]
    solution = str(target.get("solution") or "").strip()
    why = str(target.get("why") or "").strip()
    parts = []
    if solution:
        parts.append(solution)
    if why:
        parts.append("真正的突破点在于：" + why)
    if memory_summary:
        parts.append("结合你之前的薄弱点，做这类题时要特别注意：" + memory_summary.replace("\n", "；"))
    return "\n\n".join(part for part in parts if part).strip() or "这次还没有稳定生成引导式讲解。"


def _render_variant_fallback(solve_result: dict[str, Any], memory_summary: str) -> str:
    base = None
    for item in solve_result.get("problems") or []:
        if item.get("is_wrong"):
            base = item
            break
    if base is None:
        base = (solve_result.get("problems") or [{}])[0]
    base_text = str(base.get("solution") or base.get("why") or "").strip() or "请围绕刚才同类题的核心方法继续练习。"
    lines = [
        "相同结构：围绕同一解法框架再做一道换数题。",
        "降低难度：先做一道只保留核心步骤的基础题。",
        "提高一点难度：在同一方法基础上增加一步推理或多一个条件。",
    ]
    if memory_summary:
        lines.append("优先照顾的历史薄弱点：" + memory_summary.replace("\n", "；"))
    lines.append("出题依据：" + base_text)
    return "\n\n".join(lines)


def _ocr_stage_one(image_path: Path, original_prompt: str, run_dir: Path) -> dict[str, Any]:
    cfg = _load_ocr_config()
    system_prompt = "你是一名试卷结构观察助手。请只根据原图找出后续解题最需要关注的文本区域位置。不要抄整页文字，不要解题。输出尽量精简，但思考可以充分。"
    user_prompt = "请在这张试卷原图中找出需要解题的文本块，重点关注题号、题干、选项和与题目直接相关的文字区域。返回文本框位置即可，越精简越好。"
    payload = _call_vl_json(cfg=cfg, image_paths=[image_path], system_prompt=system_prompt, user_prompt=user_prompt, schema_name="exam_ocr_stage1", schema=_OCR_STAGE1_SCHEMA, enable_thinking=True)
    result = {"boxes": _coerce_boxes(payload), "page_note": str(payload.get('page_note') or '').strip()}
    _write_json(run_dir / "01_ocr_stage1.json", result)
    return result


def _ocr_stage_two(image_path: Path, original_prompt: str, stage1_payload: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    cfg = _load_ocr_config()
    system_prompt = "你是一名试卷结构化解析助手。请根据原图和上一阶段的定位结果，恢复出真正需要解题的题目内容。只保留题目本身，不要返回学校名、卷名、分值说明、页眉页脚。输出尽量精简。"
    user_prompt = f"用户原始需求：{original_prompt or '批改这张试卷'}\n请把原图中真正需要解题的题目整理出来。如果是选择题，请带上选项；如果能看出学生勾选或填写的答案，也一并写出。不要重复卷头说明。\n请按这个结构输出：{json.dumps(_OCR_STAGE2_SCHEMA, ensure_ascii=False)}"
    user_prompt += _chain_suffix(stage1_payload)
    payload = _call_vl_json(cfg=cfg, image_paths=[image_path], system_prompt=system_prompt, user_prompt=user_prompt, schema_name="exam_ocr_stage2", schema=_OCR_STAGE2_SCHEMA, enable_thinking=True)
    result = {
        "paper_title": str(payload.get("paper_title") or "").strip(),
        "questions": _coerce_questions(payload),
        "page_summary": str(payload.get("page_summary") or "").strip(),
    }
    _write_json(run_dir / "02_ocr_stage2.json", result)
    _write_text(run_dir / "02_ocr_questions.txt", _questions_brief(result["questions"]))
    return result


def _solve_stage_one(image_path: Path, original_prompt: str, ocr_stage2_payload: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    cfg = _load_solver_config()
    question_brief = _questions_brief(ocr_stage2_payload.get("questions") or [])
    system_prompt = "你是一名数学试卷批改助手。请根据原图和已经整理出的题目内容，先抽取所有可批改的问题，并给出每道题的候选方法和校验计划。先做求解前规划，不要直接展开长篇解答。"
    user_prompt = f"用户原始需求：{original_prompt or '批改这张试卷'}\n已整理出的题目如下：\n{question_brief}\n\n请先抽取这张图里真正需要批改的问题，并为每道题给出候选方法和校验计划。输出尽量精简、结构清楚。\n请按这个结构输出：{json.dumps(_SOLVE_STAGE1_SCHEMA, ensure_ascii=False)}"
    user_prompt += _chain_suffix(ocr_stage2_payload)
    payload = _call_qwen_json(cfg=cfg, system_prompt=system_prompt, user_prompt=user_prompt, enable_thinking=False, supporting_images=[image_path])
    result = {
        "problem_overview": str(payload.get("problem_overview") or "").strip(),
        "problems": [item for item in (payload.get("problems") or []) if isinstance(item, dict)],
    }
    if not result["problems"]:
        result = _fallback_plan_from_questions(ocr_stage2_payload.get("questions") or [])
    _write_json(run_dir / "03_solve_stage1.json", result)
    return result


def _solve_stage_two(image_path: Path, original_prompt: str, solve_stage1_payload: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    cfg = _load_solver_config()
    system_prompt = "你是一名数学阅卷与验证助手。请根据原图、用户原始需求和上一阶段的规划，给出具体的求解与验证结果，判断学生作答哪些正确、哪些错误。所有自然语言都使用简体中文。"
    user_prompt = f"用户原始需求：{original_prompt or '批改这张试卷'}\n请根据原图和上一阶段的解题规划，给出具体的求解与验证。要明确指出每道题学生作答是否正确、正确答案是什么、为什么，以及最基础的解题过程。输出保持简洁。\n请按这个结构输出：{json.dumps(_SOLVE_STAGE2_SCHEMA, ensure_ascii=False)}"
    user_prompt += _chain_suffix(solve_stage1_payload)
    payload = _call_qwen_json(cfg=cfg, system_prompt=system_prompt, user_prompt=user_prompt, enable_thinking=False, supporting_images=[image_path])
    result = _coerce_solve_result(payload)
    _write_json(run_dir / "04_solve_stage2.json", result)
    return result


def _weakness_stage(image_path: Path, original_prompt: str, solve_stage2_payload: dict[str, Any], memory_summary: str, run_dir: Path) -> dict[str, Any]:
    cfg = _load_solver_config()
    system_prompt = "你是一名数学薄弱点诊断助手。请读取历史薄弱点、原图、用户原始需求和求解验证结果，先判断这次哪些内容是正确的、哪些内容是错误的，再用一小段中文说明最核心的薄弱点。你的输出会直接发给用户，所以不要写标题，不要写英文。"
    user_prompt = f"用户原始需求：{original_prompt or '批改这张试卷'}\n历史薄弱点记忆：\n{memory_summary or '当前还没有明显的历史薄弱点记录。'}\n请先用简洁中文总结这次批改与验证的结论，再指出最核心的薄弱点和后续训练重点。\n请按这个结构输出：{json.dumps(_WEAKNESS_SCHEMA, ensure_ascii=False)}"
    user_prompt += _chain_suffix(solve_stage2_payload)
    payload = _call_qwen_json(cfg=cfg, system_prompt=system_prompt, user_prompt=user_prompt, enable_thinking=False, supporting_images=[image_path])
    result = {
        "all_correct": bool(payload.get("all_correct")),
        "correct_points": [str(v).strip() for v in (payload.get("correct_points") or []) if str(v).strip()],
        "error_points": [str(v).strip() for v in (payload.get("error_points") or []) if str(v).strip()],
        "primary_weakness": str(payload.get("primary_weakness") or "").strip(),
        "knowledge_points": [str(v).strip() for v in (payload.get("knowledge_points") or []) if str(v).strip()],
        "practice_focus": [str(v).strip() for v in (payload.get("practice_focus") or []) if str(v).strip()],
        "user_text": str(payload.get("user_text") or "").strip(),
    }
    _write_json(run_dir / "05_weakness.json", result)
    _write_text(run_dir / "05_weakness.txt", result["user_text"])
    return result


def _guided_stage(image_path: Path, original_prompt: str, solve_stage2_payload: dict[str, Any], memory_summary: str, run_dir: Path) -> dict[str, Any]:
    cfg = _load_solver_config()
    system_prompt = "你是一名数学老师。请读取历史薄弱点、原图、用户原始需求和求解验证结果，给出针对性的引导式讲解。讲解要建立在已经算出的求解过程之上，再补几句核心突破点，帮助学生理解怎么破题。你的输出会直接发给用户，所以不要写标题，不要写英文。"
    user_prompt = f"用户原始需求：{original_prompt or '批改这张试卷'}\n历史薄弱点记忆：\n{memory_summary or '当前还没有明显的历史薄弱点记录。'}\n请给出一段直接发给学生的引导式讲解。讲解里要包含最基础的求解过程，再补充几句核心突破点。\n请按这个结构输出：{json.dumps(_GUIDED_SCHEMA, ensure_ascii=False)}"
    user_prompt += _chain_suffix(solve_stage2_payload)
    payload = _call_qwen_json(cfg=cfg, system_prompt=system_prompt, user_prompt=user_prompt, enable_thinking=False, supporting_images=[image_path])
    result = {
        "hint_level": int(payload.get("hint_level") or 1),
        "core_breakthrough_points": [str(v).strip() for v in (payload.get("core_breakthrough_points") or []) if str(v).strip()],
        "user_text": str(payload.get("user_text") or "").strip(),
    }
    _write_json(run_dir / "06_guided.json", result)
    _write_text(run_dir / "06_guided.txt", result["user_text"])
    return result


def _variant_stage(image_path: Path, original_prompt: str, solve_stage2_payload: dict[str, Any], memory_summary: str, run_dir: Path) -> dict[str, Any]:
    cfg = _load_solver_config()
    system_prompt = "你是一名数学练习设计助手。请阅读历史薄弱点、原图、用户原始需求和求解验证结果，直接生成三道给学生练习的题目。如果当前有错误，优先围绕当前错误的题目出题；如果当前都做对了，就优先围绕历史薄弱点出题。所有自然语言都必须是简体中文。你的输出会直接发给学生，所以不要写英文，不要写 JSON，不要只写概述，必须把三道题完整写出来。"
    user_prompt = (
        f"用户原始需求：{original_prompt or '批改这张试卷'}\n"
        f"历史薄弱点记忆：\n{memory_summary or '当前还没有明显的历史薄弱点记录。'}\n"
        "请直接输出三道练习题，按 1、 2、 3 编号，分别对应：相同结构、降低难度、提高一点难度。每道题都要把题目完整写出来；如果需要提示，只能在每题后面补一句很短的中文提示。不要只写开场白。"
    )
    user_prompt += _chain_suffix(solve_stage2_payload)
    user_text = _call_qwen_text(
        cfg=cfg,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        enable_thinking=False,
        supporting_images=[image_path],
    )
    result = {
        "user_text": str(user_text or "").strip(),
    }
    _write_json(run_dir / "07_variants.json", result)
    _write_text(run_dir / "07_variants.txt", result["user_text"])
    return result



def looks_like_exam_pipeline_request(agent: Any, message: str, attachments: list[dict[str, Any]] | None = None) -> bool:
    text = str(message or "").strip()
    if _contains_search_request(text) and not _contains_grading_request(text):
        return False
    kinds = {str(item.get("kind") or "").strip().lower() for item in (attachments or []) if isinstance(item, dict)}
    has_visual = bool({"image", "pdf"} & kinds)
    return has_visual or _contains_grading_request(text)


def can_handle_exam_pipeline_request(agent: Any, message: str, attachments: list[dict[str, Any]] | None = None) -> bool:
    if not looks_like_exam_pipeline_request(agent, message, attachments):
        return False
    return bool(agent._pipeline_source_from_attachments(attachments))


def prepare_exam_pipeline_context(agent: Any, message: str, *, attachments: list[dict[str, Any]] | None = None, session_id: str | None = None) -> dict[str, Any] | None:
    if not can_handle_exam_pipeline_request(agent, message, attachments):
        return None
    source = agent._pipeline_source_from_attachments(attachments)
    if not source:
        return None
    agent._mark_turn_route("exam_pipeline_v2")
    run_dir = _new_run_dir(source, session_id or "")
    image_path = _prepare_visual_source(source, run_dir)
    original_prompt = str(message or "").strip()
    logger.info("[ExamPipelineV2] session=%s source=%s", session_id or "", source)
    try:
        ocr_stage1 = _ocr_stage_one(image_path, original_prompt, run_dir)
        ocr_stage2 = _ocr_stage_two(image_path, original_prompt, ocr_stage1, run_dir)
        if not ocr_stage2.get("questions"):
            return {"status": "partial", "failure_response": "这次已经收到截图，但还没有稳定识别出题目内容。请把单题裁出来再发一次。", "run_dir": str(run_dir)}
        solve_stage1 = _solve_stage_one(image_path, original_prompt, ocr_stage2, run_dir)
        solve_stage2 = _solve_stage_two(image_path, original_prompt, solve_stage1, run_dir)
    except Exception:
        logger.exception("[ExamPipelineV2] main stages failed")
        return {"status": "error", "failure_response": "这次试卷批改没有稳定完成。请换一张更清晰的截图，或者把单题裁出来再发一次。", "run_dir": str(run_dir)}

    memory_payload = get_global_learning_memory(student_id="")
    memory_summary = summarize_global_learning_memory_cn(memory_payload)
    _write_json(run_dir / "08_memory_snapshot.json", memory_payload)
    _write_text(run_dir / "08_memory_summary.txt", memory_summary)

    return {
        "status": "ok",
        "run_dir": str(run_dir),
        "source": source,
        "image_path": str(image_path),
        "original_prompt": original_prompt,
        "ocr_stage1": ocr_stage1,
        "ocr_stage2": ocr_stage2,
        "solve_stage1": solve_stage1,
        "solve_stage2": solve_stage2,
        "memory_payload": memory_payload,
        "memory_summary": memory_summary,
    }



def _escape_markdown_cell(value: Any) -> str:
    text = _first_non_empty(value)
    text = re.sub(r"\s+", " ", text)
    text = text.replace("|", "\|")
    return text or "?"


def _problem_status(item: dict[str, Any]) -> tuple[str, str]:
    if bool(item.get("is_wrong")):
        return "?", "??"
    judgement = str(item.get("judgement") or "").strip()
    if "?" in judgement:
        return "?", "??"
    if judgement:
        return "??", judgement
    return "??", "??"


def _with_stage_title(title: str, text: str) -> str:
    body = str(text or "").strip()
    if not body:
        return body
    prefix = f"{title}\n"
    if body.startswith(prefix) or body.startswith(title):
        return body
    return f"{prefix}{body}"


def format_stage_one(agent: Any, *, weakness_payload: dict[str, Any], solve_stage2: dict[str, Any] | None = None, ocr_stage2: dict[str, Any] | None = None) -> str:
    text = str(weakness_payload.get("user_text") or "").strip()
    if text:
        return _with_stage_title("### \u6279\u6539\u4e0e\u8584\u5f31\u70b9", text)
    if solve_stage2:
        fallback = str((solve_stage2 or {}).get("overall_comment") or "").strip()
        if fallback:
            return _with_stage_title("### \u6279\u6539\u4e0e\u8584\u5f31\u70b9", fallback)
    return _with_stage_title("### \u6279\u6539\u4e0e\u8584\u5f31\u70b9", "\u6279\u6539\u4e0e\u8584\u5f31\u70b9\u6682\u65f6\u672a\u751f\u6210\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002")


def format_stage_two(agent: Any, *, guided_payload: dict[str, Any]) -> str:
    text = str(guided_payload.get("user_text") or "").strip()
    return _with_stage_title("### \u5f15\u5bfc\u8bb2\u89e3", text or "\u5f15\u5bfc\u8bb2\u89e3\u6682\u65f6\u672a\u751f\u6210\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002")


def format_stage_three(agent: Any, *, variant_payload: dict[str, Any]) -> str:
    text = str(variant_payload.get("user_text") or "").strip()
    return _with_stage_title("### \u53d8\u5f0f\u9898", text or "\u53d8\u5f0f\u9898\u6682\u65f6\u672a\u751f\u6210\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002")


def maybe_handle_exam_pipeline_request(agent: Any, message: str, *, attachments: list[dict[str, Any]] | None = None, session_id: str | None = None, store_response: bool = True, return_bundle: bool = False) -> str | dict[str, Any] | None:
    context = prepare_exam_pipeline_context(agent, message, attachments=attachments, session_id=session_id)
    if context is None:
        return None
    failure_response = str(context.get("failure_response") or "").strip()
    if failure_response:
        bundle = {
            "combined_response": failure_response,
            "stage_messages": [failure_response],
            "status": str(context.get("status") or "partial").strip() or "partial",
        }
        if return_bundle:
            return bundle
        if store_response:
            agent.memory.add_message("assistant", failure_response, session_id=session_id)
        return failure_response

    image_path = Path(str(context.get("image_path") or "")).expanduser()
    original_prompt = str(context.get("original_prompt") or "").strip()
    solve_stage2 = context["solve_stage2"]
    memory_summary = str(context.get("memory_summary") or "").strip()
    run_dir = Path(str(context.get("run_dir") or "")).expanduser()

    def run_weakness() -> dict[str, Any]:
        return _weakness_stage(image_path, original_prompt, solve_stage2, memory_summary, run_dir)

    def run_guided() -> dict[str, Any]:
        return _guided_stage(image_path, original_prompt, solve_stage2, memory_summary, run_dir)

    def run_variant() -> dict[str, Any]:
        return _variant_stage(image_path, original_prompt, solve_stage2, memory_summary, run_dir)

    results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            "weakness": executor.submit(run_weakness),
            "guided": executor.submit(run_guided),
            "variant": executor.submit(run_variant),
        }
        for name, future in futures.items():
            try:
                results[name] = future.result()
            except Exception as exc:
                logger.exception("[ExamPipelineV2] %s stage failed", name)
                labels = {"weakness": "批改与薄弱点", "guided": "引导式讲解", "variant": "变式题"}
                results[name] = {"status": "error", "user_text": f"这次{labels.get(name, name)}阶段没有稳定完成：{exc}"}

    stage_messages = [
        format_stage_one(agent, solve_stage2=solve_stage2, weakness_payload=results.get("weakness", {}), ocr_stage2=context.get("ocr_stage2", {})),
        format_stage_two(agent, guided_payload=results.get("guided", {})),
        format_stage_three(agent, variant_payload=results.get("variant", {})),
    ]
    bundle = {
        "combined_response": "\n\n".join(stage_messages),
        "stage_messages": stage_messages,
        "status": "ok",
        "run_dir": str(run_dir),
        "solve_stage2": solve_stage2,
        "ocr_stage2": context.get("ocr_stage2", {}),
    }
    if return_bundle:
        return bundle
    response = str(bundle.get("combined_response") or "").strip()
    if store_response:
        agent.memory.add_message("assistant", response, session_id=session_id)
    return response
