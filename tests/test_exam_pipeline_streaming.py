import asyncio
import json
from pathlib import Path

import mathclaw.app.runner.manager as manager_module
import mathclaw.app.runner.session as session_module
from mathclaw.agents.react_agent import ScholarAgent


class _DummyMemory:
    def __init__(self, seed_messages=None):
        self.messages = []
        self._messages = seed_messages or []

    def add_message(self, role: str, content: str, session_id: str | None = None) -> None:
        self.messages.append((role, content, session_id))
        self._messages.append({'role': role, 'content': content, 'session_id': session_id})


def test_exam_pipeline_defaults_on_image_and_builds_three_stage_messages(tmp_path: Path) -> None:
    structured_path = tmp_path / 'Structured.md'
    structured_path.write_text('1. Solve x^2 - 5x + 6 = 0', encoding='utf-8')
    solve_path = tmp_path / 'Solved.md'
    solve_path.write_text("""# Solved

Final answer: x=2, x=3""", encoding='utf-8')
    weakness_path = tmp_path / 'TeacherFeedback.md'
    weakness_path.write_text("""# Weakness

- symbolic_manipulation_gap""", encoding='utf-8')
    guided_path = tmp_path / 'TeacherReply.md'
    guided_path.write_text("""# Guided

Step 1: factor the quadratic.""", encoding='utf-8')
    variant_path = tmp_path / 'VariantSet.md'
    variant_path.write_text("""# Variants

1. Solve x^2 - 4x + 3 = 0
2. Solve x^2 - 3x + 2 = 0
3. Solve x^2 - 6x + 5 = 0""", encoding='utf-8')
    ocr_run_dir = tmp_path / 'ocr_run'
    crop_dir = ocr_run_dir / 'question_crops'
    crop_dir.mkdir(parents=True)
    (crop_dir / 'q1.png').write_bytes(b'fake')

    agent = ScholarAgent.__new__(ScholarAgent)
    agent._tools = {
        'extract_math_document': object(),
        'run_math_solve_verify_agent': object(),
        'run_math_weakness_diagnosis_agent': object(),
        'run_guided_explanation_agent': object(),
        'run_problem_variant_agent': object(),
        'get_global_learning_memory': object(),
    }
    agent.memory = _DummyMemory([])
    agent._current_turn_trace = {'used_tools': [], 'used_skills': [], 'used_mcp': [], 'artifacts': [], 'selected_skills': [], 'route': '', 'status': ''}
    agent._tool_sources = {
        'extract_math_document': 'skill:ocr_document_processor',
        'run_math_solve_verify_agent': 'skill:math_solver_verifier',
        'run_math_weakness_diagnosis_agent': 'skill:weakness_diagnoser',
        'run_guided_explanation_agent': 'skill:guiding_users',
        'run_problem_variant_agent': 'skill:variant_generator',
        'get_global_learning_memory': 'skill:mastery_updater',
    }
    agent.working_dir = str(tmp_path)

    def fake_invoke_tool(name: str, kwargs: dict):
        if name == 'extract_math_document':
            return {'Structured_md_path': str(structured_path), 'run_dir': str(ocr_run_dir), 'question_count': 1, 'status': 'ok'}
        if name == 'run_math_solve_verify_agent':
            assert 'q1.png' in kwargs['supporting_images']
            return {'Solved_md_path': str(solve_path), 'final_answer': 'x=2, x=3', 'status': 'pass'}
        if name == 'get_global_learning_memory':
            return {'memory': {'weaknesses': {'symbolic_manipulation_gap': {'severity': 0.82, 'status': 'active'}}, 'knowledge_points': {'quadratic equation': {'risk_score': 0.76, 'status': 'watch'}}, 'practice_focus': ['factoring']}}
        if name == 'run_math_weakness_diagnosis_agent':
            assert 'Historical memory snapshot' in kwargs['conversation_excerpt']
            return {'TeacherFeedback_md_path': str(weakness_path), 'primary_weakness': 'symbolic_manipulation_gap', 'status': 'diagnosed'}
        if name == 'run_guided_explanation_agent':
            assert 'historical weakness memory snapshot' in kwargs['learning_goal']
            return {'TeacherReply_md_path': str(guided_path), 'hint_level': 1, 'status': 'guided'}
        if name == 'run_problem_variant_agent':
            assert 'historical weakness memory snapshot' in kwargs['variant_request']
            return {'VariantSet_md_path': str(variant_path), 'variant_count': 3, 'status': 'generated'}
        raise AssertionError(name)

    agent._invoke_tool = fake_invoke_tool  # type: ignore[attr-defined]

    bundle = agent._maybe_handle_exam_pipeline_request(
        '??????',
        attachments=[{'kind': 'image', 'absolute_path': '/root/autodl-tmp/123456.png'}],
        session_id='wecom:single:test',
        store_response=False,
        return_bundle=True,
    )

    assert isinstance(bundle, dict)
    assert len(bundle['stage_messages']) == 3
    assert 'Solve & Diagnose' in bundle['stage_messages'][0]
    assert 'Guided Explanation' in bundle['stage_messages'][1]
    assert 'Variants' in bundle['stage_messages'][2]
    assert agent._current_turn_trace['route'] == 'exam_pipeline'


class _FakeAgent:
    def __init__(self, trace):
        self._trace = trace

    def get_last_turn_trace(self):
        return self._trace


class _StageRunner:
    def __init__(self, trace):
        self.is_running = True
        self.agent = _FakeAgent(trace)

    async def chat_stream(self, message, session_id, attachments=None):
        yield {'type': 'stage_message', 'content': 'first stage'}
        yield {'type': 'stage_message', 'content': 'second stage'}
        yield {'type': 'done', 'content': 'combined response', 'stage_messages': ['third stage'], 'suppress_emit': True}


def test_stream_query_emits_stage_messages_individually(tmp_path, monkeypatch):
    monkeypatch.setattr(manager_module, 'WORKING_DIR', str(tmp_path))
    monkeypatch.setattr(session_module, 'WORKING_DIR', str(tmp_path))
    (tmp_path / 'config.json').write_text(json.dumps({'debug_skill_footer': True}, ensure_ascii=False), encoding='utf-8')
    trace = {'route': 'exam_pipeline', 'used_skills': ['ocr_document_processor', 'math_solver_verifier'], 'used_tools': ['extract_math_document', 'run_math_solve_verify_agent'], 'status': 'ok'}
    manager = manager_module.AgentRunnerManager()
    manager.runner = _StageRunner(trace)
    request = {'session_id': 'wecom:single:test', 'user_id': 'user-1', 'channel': 'wecom', 'input': [{'content': [{'type': 'text', 'text': '??????'}]}]}

    async def _collect():
        items = []
        async for event in manager.stream_query(request):
            items.append(event)
        return items

    events = asyncio.run(_collect())
    messages = [event for event in events if getattr(event, 'object', '') == 'message']
    assert len(messages) == 3
    assert messages[0].data.content[0].text == 'first stage'
    assert messages[1].data.content[0].text == 'second stage'
    assert '[Skill Trace]' in messages[2].data.content[0].text
    assert 'route: exam_pipeline' in messages[2].data.content[0].text
