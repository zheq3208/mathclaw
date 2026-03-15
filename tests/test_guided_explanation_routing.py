from pathlib import Path

from researchclaw.agents.react_agent import ScholarAgent


class _DummyMemory:
    def __init__(self, seed_messages: list[dict] | None = None) -> None:
        self.messages = []
        self._messages = seed_messages or []

    def add_message(self, role: str, content: str, session_id: str | None = None) -> None:
        self.messages.append((role, content, session_id))
        self._messages.append({"role": role, "content": content, "session_id": session_id})


def test_looks_like_guided_explanation_request() -> None:
    agent = ScholarAgent.__new__(ScholarAgent)
    assert agent._looks_like_guided_explanation_request("Give me a hint step by step, not the full answer") is True
    assert agent._looks_like_guided_explanation_request("find 2025 beijing paper") is False


def test_maybe_handle_guided_explanation_request_reads_reply(tmp_path: Path) -> None:
    reply_path = tmp_path / "TeacherReply.md"
    reply_path.write_text("Let us not jump to the final answer.\n\nFirst tell me what the problem is asking.", encoding="utf-8")

    agent = ScholarAgent.__new__(ScholarAgent)
    agent._tools = {"run_guided_explanation_agent": object()}
    agent.memory = _DummyMemory(
        [
            {"role": "user", "content": "Solve x^2 - 5x + 6 = 0", "session_id": "s1"},
            {"role": "assistant", "content": "Answer: x=2, x=3\nStatus: pass", "session_id": "s1"},
        ]
    )

    def fake_invoke_tool(name: str, kwargs: dict):
        assert name == "run_guided_explanation_agent"
        assert kwargs["problem_text"] == "Solve x^2 - 5x + 6 = 0"
        assert kwargs["learning_goal"] == "Give me a hint step by step, not the full answer"
        return {
            "TeacherReply_md_path": str(reply_path),
            "status": "guided",
            "hint_level": 1,
        }

    agent._invoke_tool = fake_invoke_tool  # type: ignore[attr-defined]
    agent._tool_response_json = lambda result: result  # type: ignore[attr-defined]

    response = agent._maybe_handle_guided_explanation_request(
        "Give me a hint step by step, not the full answer",
        attachments=[],
        session_id="s1",
        store_response=True,
    )

    assert response is not None
    assert "Let us not jump to the final answer" in response
    assert "Hint level: 1" in response
    assert "Status: guided" in response
    assert agent.memory.messages[-1][0] == "assistant"
