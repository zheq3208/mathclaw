from pathlib import Path

from researchclaw.agents.react_agent import ScholarAgent


class _DummyMemory:
    def __init__(self, seed_messages: list[dict] | None = None) -> None:
        self.messages = []
        self._messages = seed_messages or []

    def add_message(self, role: str, content: str, session_id: str | None = None) -> None:
        self.messages.append((role, content, session_id))
        self._messages.append({"role": role, "content": content, "session_id": session_id})


def test_looks_like_weakness_diagnosis_request() -> None:
    agent = ScholarAgent.__new__(ScholarAgent)
    assert agent._looks_like_weakness_diagnosis_request("diagnose the weakness in this solution") is True
    assert agent._looks_like_weakness_diagnosis_request("find 2025 beijing paper") is False


def test_maybe_handle_weakness_diagnosis_request_reads_feedback(tmp_path: Path) -> None:
    feedback_path = tmp_path / "TeacherFeedback.md"
    feedback_path.write_text("# Weakness Diagnosis\n\n- Primary weakness: symbolic_manipulation_gap", encoding="utf-8")

    agent = ScholarAgent.__new__(ScholarAgent)
    agent._tools = {"run_math_weakness_diagnosis_agent": object()}
    agent.memory = _DummyMemory(
        [
            {"role": "user", "content": "??? x^2 - 5x + 6 = 0", "session_id": "s1"},
            {"role": "assistant", "content": "Answer: x=2, x=3\nStatus: pass", "session_id": "s1"},
        ]
    )

    def fake_invoke_tool(name: str, kwargs: dict):
        assert name == "run_math_weakness_diagnosis_agent"
        assert kwargs["problem_text"] == "??? x^2 - 5x + 6 = 0"
        assert "Answer: x=2, x=3" in kwargs["conversation_excerpt"]
        return {
            "TeacherFeedback_md_path": str(feedback_path),
            "status": "diagnosed",
        }

    agent._invoke_tool = fake_invoke_tool  # type: ignore[attr-defined]
    agent._tool_response_json = lambda result: result  # type: ignore[attr-defined]

    response = agent._maybe_handle_weakness_diagnosis_request(
        "diagnose the weakness in this problem",
        attachments=[],
        session_id="s1",
        store_response=True,
    )

    assert response is not None
    assert "symbolic_manipulation_gap" in response
    assert "Status: diagnosed" in response
    assert agent.memory.messages[-1][0] == "assistant"
