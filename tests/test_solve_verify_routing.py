from pathlib import Path

from researchclaw.agents.react_agent import ScholarAgent


class _DummyMemory:
    def __init__(self) -> None:
        self.messages = []

    def add_message(self, role: str, content: str, session_id: str | None = None) -> None:
        self.messages.append((role, content, session_id))


def test_looks_like_solve_verify_request_for_equation() -> None:
    agent = ScholarAgent.__new__(ScholarAgent)
    assert agent._looks_like_solve_verify_request("??? x^2 - 5x + 6 = 0") is True


def test_maybe_handle_solve_verify_request_reads_solved_markdown(tmp_path: Path) -> None:
    agent = ScholarAgent.__new__(ScholarAgent)
    agent._tools = {"run_math_solve_verify_agent": object()}
    agent.memory = _DummyMemory()
    solved_path = tmp_path / "Solved.md"
    solved_path.write_text("?????x=2 ? x=3", encoding="utf-8")

    def fake_invoke_tool(name: str, kwargs: dict):
        assert name == "run_math_solve_verify_agent"
        assert kwargs["problem_text"] == "??? x^2 - 5x + 6 = 0"
        return {
            "Solved_md_path": str(solved_path),
            "status": "pass",
        }

    agent._invoke_tool = fake_invoke_tool  # type: ignore[attr-defined]
    agent._tool_response_json = lambda result: result  # type: ignore[attr-defined]

    response = agent._maybe_handle_solve_verify_request(
        "??? x^2 - 5x + 6 = 0",
        attachments=[],
        session_id="s1",
        store_response=True,
    )

    assert response is not None
    assert "x=2" in response
    assert "Status: pass" in response
    assert agent.memory.messages[-1][0] == "assistant"
