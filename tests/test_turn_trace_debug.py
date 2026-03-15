import asyncio
import json
from pathlib import Path

import researchclaw.app.runner.manager as manager_module
import researchclaw.app.runner.session as session_module


class _FakeAgent:
    def __init__(self, trace):
        self._trace = trace

    def get_last_turn_trace(self):
        return self._trace


class _FakeRunner:
    def __init__(self, trace, response="????"):
        self.is_running = True
        self.agent = _FakeAgent(trace)
        self._response = response

    async def chat(self, message, session_id, attachments=None):
        return self._response

    async def chat_stream(self, message, session_id, attachments=None):
        yield {"type": "done", "content": self._response}


def test_manager_chat_appends_trace_footer_and_persists_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(manager_module, "WORKING_DIR", str(tmp_path))
    monkeypatch.setattr(session_module, "WORKING_DIR", str(tmp_path))
    (tmp_path / "config.json").write_text(
        json.dumps({"debug_skill_footer": True}, ensure_ascii=False),
        encoding="utf-8",
    )

    trace = {
        "route": "solve_verify",
        "used_skills": ["math_solver_verifier"],
        "used_tools": ["run_math_solve_verify_agent"],
        "artifacts": [".researchclaw/solve_verify_runs/demo/SolutionAudit.json"],
        "status": "pass",
    }
    manager = manager_module.AgentRunnerManager()
    manager.runner = _FakeRunner(trace)

    out = asyncio.run(manager.chat("??????", session_id="wecom:single:test"))
    assert "[Skill Trace]" in out
    assert "skills: math_solver_verifier" in out
    assert "tools: run_math_solve_verify_agent" in out

    session_path = tmp_path / "sessions" / "wecom:single:test.json"
    data = json.loads(session_path.read_text(encoding="utf-8"))
    metadata = data["messages"][-1]["metadata"]
    assert metadata["turn_trace"]["route"] == "solve_verify"
    trace_file = Path(metadata["trace_file"])
    assert trace_file.exists()
    assert "run_math_solve_verify_agent" in trace_file.read_text(encoding="utf-8")


def test_manager_chat_stream_decorates_done_event(tmp_path, monkeypatch):
    monkeypatch.setattr(manager_module, "WORKING_DIR", str(tmp_path))
    monkeypatch.setattr(session_module, "WORKING_DIR", str(tmp_path))
    (tmp_path / "config.json").write_text(
        json.dumps({"debug_skill_footer": True}, ensure_ascii=False),
        encoding="utf-8",
    )

    trace = {
        "route": "ocr",
        "used_skills": ["ocr_document_processor"],
        "used_tools": ["extract_math_document"],
        "status": "ok",
    }
    manager = manager_module.AgentRunnerManager()
    manager.runner = _FakeRunner(trace, response="OCR??")

    async def _collect():
        items = []
        async for event in manager.chat_stream("??OCR", session_id="wecom:single:stream"):
            items.append(event)
        return items

    events = asyncio.run(_collect())

    done = events[-1]
    assert done["type"] == "done"
    assert "[Skill Trace]" in done["content"]
    assert "skills: ocr_document_processor" in done["content"]
    assert "tools: extract_math_document" in done["content"]
