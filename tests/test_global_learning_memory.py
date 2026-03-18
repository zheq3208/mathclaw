import json
from pathlib import Path

from mathclaw.agents.react_agent import ScholarAgent
from mathclaw.agents.skills.mastery_updater import register as mastery_register
from mathclaw.agents.tools import math_learning
from mathclaw.agents.tools import weakness_diag_q3vl as weakness_mod


class _DummyMemory:
    def __init__(self, seed_messages: list[dict] | None = None) -> None:
        self.messages = []
        self._messages = seed_messages or []

    def add_message(self, role: str, content: str, session_id: str | None = None) -> None:
        self.messages.append((role, content, session_id))
        self._messages.append({"role": role, "content": content, "session_id": session_id})


def _read_global_memory(base_dir: Path) -> dict:
    path = base_dir / 'math_learning' / 'global_learning_memory.json'
    return json.loads(path.read_text(encoding='utf-8'))


def test_update_global_learning_memory_persists_single_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(math_learning, 'MEMORY_DIR', str(tmp_path))

    result = math_learning.update_global_learning_memory(
        primary_weakness='symbolic_manipulation_gap',
        secondary_weaknesses=['incomplete_reasoning'],
        knowledge_points=['linear equation'],
        prerequisite_gaps=['inverse operations'],
        practice_focus=['show the isolation step'],
        result='incorrect',
        note='lost the first algebraic step',
        evidence=['missing first derivation step'],
        source='weakness_diag',
        conversation_id='conv-1',
    )

    assert Path(result['memory_path']).exists()
    payload = _read_global_memory(tmp_path)
    bucket = payload['students']['__global__']
    assert 'symbolic_manipulation_gap' in bucket['weaknesses']
    assert 'linear equation' in bucket['knowledge_points']
    assert bucket['recent_events'][-1]['conversation_id'] == 'conv-1'


def test_mastery_and_micro_quiz_update_global_memory(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(math_learning, 'MEMORY_DIR', str(tmp_path))

    mastery_event = math_learning.update_math_mastery(
        student_id='stu-1',
        knowledge_point='linear_equation',
        result='correct',
        evidence=['solved'],
        note='first pass',
    )
    assert mastery_event['global_memory_event']['student_id'] == 'stu-1'

    quiz = math_learning.generate_micro_quiz(
        'Solve 2x + 3 = 7',
        student_id='stu-1',
    )
    answers = [entry['answer'] for entry in quiz['answer_key']]
    graded = math_learning.grade_micro_quiz(
        quiz_id=quiz['quiz_id'],
        student_answers=answers,
        student_id='stu-1',
        update_mastery_record=False,
    )

    assert graded['global_memory_event']['student_id'] == 'stu-1'
    payload = _read_global_memory(tmp_path)
    bucket = payload['students']['stu-1']
    assert 'linear_equation' in bucket['knowledge_points']
    assert bucket['recent_events'][-1]['source'] == 'micro_quiz'


def test_weakness_diagnosis_updates_global_memory(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(math_learning, 'MEMORY_DIR', str(tmp_path))

    verification_path = tmp_path / 'VerificationReport.json'
    verification_path.write_text(
        '{"arbiter": {"status": "conflict", "final_answer": "x=2"}, "critic": {"conflict_summary": ["student answer mismatched"]}, "tool_checks": {}}',
        encoding='utf-8',
    )

    combined_output = {
        'process': {
            'primary_error_stage': 'final_answer',
            'wrong_answer': True,
            'process_incomplete': True,
            'missing_steps': ['The first derivation step is missing.'],
            'evidence_items': ['Student final answer conflicts with the verified answer or exact check.'],
            'likely_error_causes': ['symbolic_manipulation_gap'],
            'confidence': 0.88,
        },
        'learning': {
            'primary_weakness': 'symbolic_manipulation_gap',
            'secondary_weaknesses': ['incomplete_reasoning'],
            'knowledge_points': ['linear equation'],
            'prerequisite_gaps': ['inverse operations'],
            'recommended_practice_focus': ['show the isolation step'],
            'teacher_watchouts': ['Check whether the student can isolate x without guessing.'],
            'confidence': 0.81,
        },
        'arbiter': {
            'status': 'diagnosed',
            'problem_summary': 'solve a linear equation',
            'primary_weakness': 'symbolic_manipulation_gap',
            'secondary_weaknesses': ['incomplete_reasoning'],
            'wrong_answer': True,
            'process_incomplete': True,
            'missing_steps': ['The first derivation step is missing.'],
            'evidence_items': ['Student final answer conflicts with the verified answer or exact check.'],
            'chapter': 'Algebra',
            'question_type': 'equation',
            'knowledge_points': ['linear equation'],
            'prerequisite_gaps': ['inverse operations'],
            'likely_error_causes': ['symbolic_manipulation_gap'],
            'recommended_practice_focus': ['show the isolation step'],
            'teacher_feedback_markdown': '# Weakness Diagnosis\n\n- Primary weakness: symbolic_manipulation_gap',
            'mastery_update_suggestion': {'result': 'incorrect', 'knowledge_points': ['linear equation'], 'note': 'symbolic_manipulation_gap'},
            'confidence': 0.88,
        },
    }

    monkeypatch.setattr(
        weakness_mod,
        'run_math_solve_verify_agent',
        lambda **kwargs: {
            'VerificationReport_json_path': str(verification_path),
            'final_answer': 'x=2',
        },
    )
    monkeypatch.setattr(weakness_mod, '_call_qwen_json', lambda **kwargs: combined_output)
    monkeypatch.setattr(
        weakness_mod,
        '_load_solver_config',
        lambda: {
            'model_name': 'qwen3-vl-plus',
            'planner_enable_thinking': True,
            'critic_enable_thinking': True,
            'arbiter_enable_thinking': False,
        },
    )

    def fake_run_dir(seed_text: str) -> Path:
        run_dir = tmp_path / 'run'
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    monkeypatch.setattr(weakness_mod, '_new_run_dir', fake_run_dir)

    result = weakness_mod.run_math_weakness_diagnosis_agent(
        problem_text='Solve 2x + 3 = 7',
        student_answer='x=5',
        student_work='x=5',
        student_id='stu-weak',
        conversation_id='conv-weak',
    )

    assert Path(result['GlobalLearningMemory_json_path']).exists()
    payload = _read_global_memory(tmp_path)
    bucket = payload['students']['stu-weak']
    assert 'symbolic_manipulation_gap' in bucket['weaknesses']
    assert bucket['recent_events'][-1]['conversation_id'] == 'conv-weak'


def test_mastery_updater_register_exposes_global_memory_tools() -> None:
    tools = mastery_register()
    assert 'get_global_learning_memory' in tools
    assert 'update_global_learning_memory' in tools


def test_weakness_route_passes_conversation_id(tmp_path: Path) -> None:
    feedback_path = tmp_path / 'TeacherFeedback.md'
    feedback_path.write_text('# Weakness Diagnosis\n\n- Primary weakness: symbolic_manipulation_gap', encoding='utf-8')

    agent = ScholarAgent.__new__(ScholarAgent)
    agent._tools = {'run_math_weakness_diagnosis_agent': object()}
    agent.memory = _DummyMemory(
        [
            {'role': 'user', 'content': 'Solve x^2 - 5x + 6 = 0', 'session_id': 's1'},
            {'role': 'assistant', 'content': 'Answer: x=2, x=3\nStatus: pass', 'session_id': 's1'},
        ]
    )

    def fake_invoke_tool(name: str, kwargs: dict):
        assert name == 'run_math_weakness_diagnosis_agent'
        assert kwargs['conversation_id'] == 's1'
        return {
            'TeacherFeedback_md_path': str(feedback_path),
            'status': 'diagnosed',
        }

    agent._invoke_tool = fake_invoke_tool  # type: ignore[attr-defined]
    agent._tool_response_json = lambda result: result  # type: ignore[attr-defined]

    response = agent._maybe_handle_weakness_diagnosis_request(
        'diagnose the weakness in this problem',
        attachments=[],
        session_id='s1',
        store_response=True,
    )

    assert response is not None
    assert 'Status: diagnosed' in response


def test_auto_archive_and_manual_mastered_flow(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(math_learning, 'MEMORY_DIR', str(tmp_path))

    for _ in range(3):
        math_learning.update_global_learning_memory(
            student_id='stu-2',
            primary_weakness='symbolic_manipulation_gap',
            knowledge_points=['linear equation'],
            result='incorrect',
            source='diag',
        )
    for _ in range(7):
        math_learning.update_global_learning_memory(
            student_id='stu-2',
            knowledge_points=['linear equation'],
            result='quiz_pass',
            source='micro_quiz',
        )

    payload = _read_global_memory(tmp_path)
    bucket = payload['students']['stu-2']
    assert 'linear equation' in bucket['mastered_knowledge_points']
    assert 'symbolic_manipulation_gap' in bucket['mastered_weaknesses']
    assert 'linear equation' not in bucket['knowledge_points']

    marked = math_learning.mark_global_memory_mastered(
        student_id='stu-2',
        item_type='knowledge_point',
        item_name='quadratic function',
        note='teacher confirmed mastery',
    )
    assert marked['ok'] is True
    payload = _read_global_memory(tmp_path)
    bucket = payload['students']['stu-2']
    assert 'quadratic function' in bucket['mastered_knowledge_points']


def test_generate_micro_quiz_prioritizes_global_memory(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(math_learning, 'MEMORY_DIR', str(tmp_path))

    math_learning.update_global_learning_memory(
        student_id='stu-quiz',
        primary_weakness='symbolic_manipulation_gap',
        knowledge_points=['linear equation'],
        result='incorrect',
        source='weakness_diag',
    )

    quiz = math_learning.generate_micro_quiz(
        'Find the mean of 2, 4, 6',
        student_id='stu-quiz',
        include_answer_key=False,
    )

    assert quiz['memory_context']['quiz_source'] == 'global_memory'
    assert quiz['memory_context']['targeted_knowledge_point'] == 'linear equation'
    assert quiz['question_type'] == 'equation'
