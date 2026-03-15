from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import logging
import re
from pathlib import Path
from typing import Any

from .tools.math_learning import summarize_global_learning_memory_cn

logger = logging.getLogger(__name__)


def _contains_search_request(message: str) -> bool:
    text = str(message or '').strip()
    return '搜索' in text


def _contains_grading_request(message: str) -> bool:
    text = str(message or '').strip()
    return any(token in text for token in ('批改', '判卷', '阅卷', '改卷', '批阅', '分析试卷'))


def _read_text(path_value: str) -> str:
    path = Path(str(path_value or '').strip())
    if not path.exists() or not path.is_file():
        return ''
    return path.read_text(encoding='utf-8').strip()


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value or '').strip()
        if text:
            return text
    return ''


def looks_like_exam_pipeline_request(agent: Any, message: str, attachments: list[dict[str, Any]] | None = None) -> bool:
    text = str(message or '').strip()
    if _contains_search_request(text) and not _contains_grading_request(text):
        return False
    kinds = {str(item.get('kind') or '').strip().lower() for item in (attachments or []) if isinstance(item, dict)}
    has_visual = bool({'image', 'pdf'} & kinds)
    return has_visual or _contains_grading_request(text)


def can_handle_exam_pipeline_request(agent: Any, message: str, attachments: list[dict[str, Any]] | None = None) -> bool:
    required_tools = (
        'extract_math_document',
        'run_math_solve_verify_agent',
        'run_math_weakness_diagnosis_agent',
        'run_guided_explanation_agent',
        'run_problem_variant_agent',
    )
    if any(tool_name not in agent._tools for tool_name in required_tools):
        return False
    if not looks_like_exam_pipeline_request(agent, message, attachments):
        return False
    return bool(agent._pipeline_source_from_attachments(attachments))


def prepare_exam_pipeline_context(agent: Any, message: str, *, attachments: list[dict[str, Any]] | None = None, session_id: str | None = None) -> dict[str, Any] | None:
    if not can_handle_exam_pipeline_request(agent, message, attachments):
        return None
    source = agent._pipeline_source_from_attachments(attachments)
    if not source:
        return None
    agent._mark_turn_route('exam_pipeline')
    logger.info('[ExamPipelineSimple] session=%s message=%s', session_id or '', str(message or '')[:120])

    try:
        ocr_payload = agent._tool_response_json(
            agent._invoke_tool(
                'extract_math_document',
                {
                    'source': source,
                    'max_pages': 1,
                    'mode': 'full',
                    'max_questions': 8,
                    'original_prompt': str(message or '').strip(),
                },
            ),
        )
    except Exception:
        logger.exception('[ExamPipelineSimple] OCR stage failed')
        return {
            'status': 'error',
            'failure_response': '这次没有稳定完成题目识别。请换一张更清晰的截图，或者把单题裁出来再发一次。',
        }

    ocr_text = _first_non_empty(
        ocr_payload.get('structured_text'),
        _read_text(str(ocr_payload.get('Structured_md_path') or '').strip()),
    )
    if not ocr_text:
        return {
            'status': 'partial',
            'failure_response': '这次已经收到截图，但还没有稳定识别出题目内容。请把目标题目单独裁剪后再发一次。',
        }

    try:
        solve_payload = agent._tool_response_json(
            agent._invoke_tool(
                'run_math_solve_verify_agent',
                {
                    'problem_text': ocr_text,
                    'expected_answer': '',
                    'supporting_images': source,
                    'original_prompt': str(message or '').strip(),
                },
            ),
        )
    except Exception:
        logger.exception('[ExamPipelineSimple] solve stage failed')
        return {
            'status': 'error',
            'failure_response': '题目已经识别出来了，但这次求解与验证没有稳定完成。请把题目裁成更小范围后再试一次。',
        }

    solve_summary = _first_non_empty(
        _read_text(str(solve_payload.get('Solved_md_path') or '').strip()),
        str(solve_payload.get('user_markdown') or '').strip(),
        json.dumps(solve_payload, ensure_ascii=False),
    )

    memory_payload: dict[str, Any] = {}
    memory_summary = ''
    if 'get_global_learning_memory' in agent._tools:
        try:
            memory_payload = agent._tool_response_json(agent._invoke_tool('get_global_learning_memory', {'student_id': ''}))
            memory_summary = summarize_global_learning_memory_cn(memory_payload)
        except Exception:
            logger.exception('[ExamPipelineSimple] memory snapshot failed')

    common = {
        'problem_text': ocr_text,
        'supporting_images': source,
        'original_prompt': str(message or '').strip(),
        'student_id': '',
    }
    return {
        'status': 'ok',
        'source': source,
        'ocr_payload': ocr_payload,
        'solve_payload': solve_payload,
        'solve_summary': solve_summary,
        'memory_payload': memory_payload,
        'memory_summary': memory_summary,
        'weakness_args': {
            **common,
            'verification_report': solve_summary,
            'conversation_excerpt': str(message or '').strip(),
            'student_answer': '',
            'student_work': '',
            'reference_answer': '',
            'error_description': str(message or '').strip(),
            'conversation_id': session_id or '',
        },
        'guided_args': {
            **common,
            'verification_report': solve_summary,
            'conversation_excerpt': str(message or '').strip(),
            'student_attempt': '',
            'learning_goal': str(message or '').strip(),
            'requested_hint_level': 1,
            'latest_student_reply': '',
        },
        'variant_args': {
            **common,
            'solve_summary': solve_summary,
            'variant_request': str(message or '').strip(),
            'grade_hint': '',
            'requested_count': 3,
            'target_skill': '',
        },
    }


def _resolve_future(agent: Any, future: Any, *, stage: str) -> dict[str, Any]:
    try:
        return agent._tool_response_json(future.result())
    except Exception as exc:
        logger.exception('[ExamPipelineSimple] %s stage failed', stage)
        return {'status': 'error', 'error': str(exc), 'stage': stage}


def format_stage_one(agent: Any, *, solve_payload: dict[str, Any], weakness_payload: dict[str, Any]) -> str:
    solve_text = _first_non_empty(
        _read_text(str(solve_payload.get('Solved_md_path') or '').strip()),
        str(solve_payload.get('user_markdown') or '').strip(),
    )
    weakness_text = _first_non_empty(
        _read_text(str(weakness_payload.get('TeacherFeedback_md_path') or '').strip()),
        str(weakness_payload.get('teacher_feedback_markdown') or '').strip(),
    )
    parts = [part for part in [solve_text, weakness_text] if part]
    return '\n\n'.join(parts).strip() or '这次已经完成求解、验证和薄弱点诊断，但还没有整理出可直接展示的内容。'


def format_stage_two(agent: Any, *, guided_payload: dict[str, Any]) -> str:
    return _first_non_empty(
        _read_text(str(guided_payload.get('TeacherReply_md_path') or '').strip()),
        str(guided_payload.get('teacher_response_markdown') or '').strip(),
    ) or '这次还没有稳定生成引导式讲解。'


def format_stage_three(agent: Any, *, variant_payload: dict[str, Any]) -> str:
    return _first_non_empty(
        _read_text(str(variant_payload.get('VariantSet_md_path') or '').strip()),
        str(variant_payload.get('variant_markdown') or '').strip(),
        str(variant_payload.get('teacher_response_markdown') or '').strip(),
    ) or '这次还没有稳定生成变式题。'


def maybe_handle_exam_pipeline_request(agent: Any, message: str, *, attachments: list[dict[str, Any]] | None = None, session_id: str | None = None, store_response: bool = True, return_bundle: bool = False) -> str | dict[str, Any] | None:
    context = prepare_exam_pipeline_context(agent, message, attachments=attachments, session_id=session_id)
    if context is None:
        return None
    failure_response = str(context.get('failure_response') or '').strip()
    if failure_response:
        bundle = {
            'combined_response': failure_response,
            'stage_messages': [failure_response],
            'status': str(context.get('status') or 'partial').strip() or 'partial',
        }
        if return_bundle:
            return bundle
        if store_response:
            agent.memory.add_message('assistant', failure_response, session_id=session_id)
        return failure_response

    specs = {
        'weakness': ('run_math_weakness_diagnosis_agent', context['weakness_args']),
        'guided': ('run_guided_explanation_agent', context['guided_args']),
        'variant': ('run_problem_variant_agent', context['variant_args']),
    }
    results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_map = {
            name: executor.submit(agent._invoke_tool, tool_name, tool_args)
            for name, (tool_name, tool_args) in specs.items()
        }
        for name, future in future_map.items():
            results[name] = _resolve_future(agent, future, stage=name)

    stage_messages = [
        format_stage_one(agent, solve_payload=context['solve_payload'], weakness_payload=results.get('weakness', {})),
        format_stage_two(agent, guided_payload=results.get('guided', {})),
        format_stage_three(agent, variant_payload=results.get('variant', {})),
    ]
    status = 'ok'
    if any(str(results.get(stage, {}).get('status') or '').strip().lower() == 'error' for stage in ('weakness', 'guided', 'variant')):
        status = 'partial'
    bundle = {
        'combined_response': '\n\n'.join(stage_messages),
        'stage_messages': stage_messages,
        'status': status,
        'solve_payload': context['solve_payload'],
        'ocr_payload': context['ocr_payload'],
    }
    if return_bundle:
        return bundle
    response = str(bundle.get('combined_response') or '').strip()
    if store_response:
        agent.memory.add_message('assistant', response, session_id=session_id)
    return response
