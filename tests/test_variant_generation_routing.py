from pathlib import Path

from researchclaw.agents.react_agent import ScholarAgent


class _DummyMemory:
    def __init__(self, seed_messages: list[dict] | None = None) -> None:
        self.messages = []
        self._messages = seed_messages or []

    def add_message(self, role: str, content: str, session_id: str | None = None) -> None:
        self.messages.append((role, content, session_id))
        self._messages.append({'role': role, 'content': content, 'session_id': session_id})


def test_looks_like_variant_generation_request() -> None:
    agent = ScholarAgent.__new__(ScholarAgent)
    assert agent._looks_like_variant_generation_request('Give me one harder version of this quadratic equation') is True
    assert agent._looks_like_variant_generation_request('find 2025 beijing paper') is False


def test_maybe_handle_variant_generation_request_reads_variant_markdown(tmp_path: Path) -> None:
    variant_path = tmp_path / 'VariantSet.md'
    variant_path.write_text('# Quadratic Variant Set\n\n## Harder\n\nSolve x^2 - 5x + 6 = 0 and justify the roots by substitution.', encoding='utf-8')

    agent = ScholarAgent.__new__(ScholarAgent)
    agent._tools = {'run_problem_variant_agent': object()}
    agent.memory = _DummyMemory(
        [
            {'role': 'user', 'content': 'Solve x^2 - 5x + 6 = 0', 'session_id': 's1'},
            {'role': 'assistant', 'content': 'Answer: x=2, x=3\nStatus: pass', 'session_id': 's1'},
        ]
    )

    def fake_invoke_tool(name: str, kwargs: dict):
        assert name == 'run_problem_variant_agent'
        assert kwargs['problem_text'] == 'Solve x^2 - 5x + 6 = 0'
        assert kwargs['variant_request'] == 'Give me one harder variant.'
        return {
            'VariantSet_md_path': str(variant_path),
            'variant_count': 1,
            'status': 'generated',
        }

    agent._invoke_tool = fake_invoke_tool  # type: ignore[attr-defined]
    agent._tool_response_json = lambda result: result  # type: ignore[attr-defined]

    response = agent._maybe_handle_variant_generation_request(
        'Give me one harder variant.',
        attachments=[],
        session_id='s1',
        store_response=True,
    )

    assert response is not None
    assert 'Quadratic Variant Set' in response
    assert 'Variant count: 1' in response
    assert 'Status: generated' in response
    assert agent.memory.messages[-1][0] == 'assistant'


def test_maybe_handle_variant_generation_request_extracts_inline_problem(tmp_path: Path) -> None:
    variant_path = tmp_path / 'VariantSetInline.md'
    variant_path.write_text('# Inline Variant Set', encoding='utf-8')

    agent = ScholarAgent.__new__(ScholarAgent)
    agent._tools = {'run_problem_variant_agent': object()}
    agent.memory = _DummyMemory([])

    def fake_invoke_tool(name: str, kwargs: dict):
        assert kwargs['problem_text'] == 'Solve x^2 - 5x + 6 = 0'
        return {
            'VariantSet_md_path': str(variant_path),
            'variant_count': 3,
            'status': 'generated',
        }

    agent._invoke_tool = fake_invoke_tool  # type: ignore[attr-defined]
    agent._tool_response_json = lambda result: result  # type: ignore[attr-defined]

    response = agent._maybe_handle_variant_generation_request(
        'Generate isomorphic, easier, and harder follow-up practice variants for x^2 - 5x + 6 = 0.',
        attachments=[],
        session_id='s-inline',
        store_response=False,
    )

    assert response is not None
    assert 'Inline Variant Set' in response
