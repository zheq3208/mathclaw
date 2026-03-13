import asyncio

from researchclaw.agents.react_agent import ScholarAgent


def _make_agent(namesake_strategy: str) -> ScholarAgent:
    agent = ScholarAgent.__new__(ScholarAgent)
    agent._tools = {}
    agent._mcp_registered_tools = set()
    agent.namesake_strategy = namesake_strategy  # type: ignore[attr-defined]
    agent._tool_schemas = []  # type: ignore[attr-defined]
    agent._build_tool_schemas = lambda: [{"type": "function"}]  # type: ignore[attr-defined]
    return agent


def test_register_tool_skip_duplicate() -> None:
    agent = _make_agent("skip")
    f1 = lambda: "a"
    f2 = lambda: "b"
    agent._register_tool("dup", f1, source="t1")
    agent._register_tool("dup", f2, source="t2")
    assert agent._tools["dup"] is f1


def test_register_tool_rename_duplicate() -> None:
    agent = _make_agent("rename")
    f1 = lambda: "a"
    f2 = lambda: "b"
    agent._register_tool("dup", f1, source="t1")
    renamed = agent._register_tool("dup", f2, source="t2")
    assert renamed != "dup"
    assert agent._tools["dup"] is f1
    assert agent._tools[renamed] is f2


def test_register_mcp_clients_refreshes_schemas() -> None:
    agent = _make_agent("override")

    class _DummyTool:
        def __init__(self, name: str):
            self.name = name

    class _DummyFn:
        json_schema = {"type": "object", "properties": {}}
        description = "demo tool"

        async def __call__(self, **kwargs):
            return "ok"

    class _DummyMcp:
        name = "demo"

        async def list_tools(self):
            return [_DummyTool("mcp_tool")]

        async def get_callable_function(self, func_name: str):
            assert func_name == "mcp_tool"
            return _DummyFn()

    asyncio.run(agent.register_mcp_clients([_DummyMcp()]))
    assert "mcp_tool" in agent._tools
    assert agent._tool_schemas == [{"type": "function"}]


def test_register_mcp_clients_clears_removed_tools() -> None:
    agent = _make_agent("override")

    class _DummyTool:
        def __init__(self, name: str):
            self.name = name

    class _DummyFn:
        json_schema = {"type": "object", "properties": {}}
        description = "demo tool"

        async def __call__(self, **kwargs):
            return "ok"

    class _DummyMcp:
        name = "demo"

        async def list_tools(self):
            return [_DummyTool("mcp_tool")]

        async def get_callable_function(self, func_name: str):
            return _DummyFn()

    asyncio.run(agent.register_mcp_clients([_DummyMcp()]))
    assert "mcp_tool" in agent._tools

    asyncio.run(agent.register_mcp_clients([]))
    assert "mcp_tool" not in agent._tools


def test_build_tool_schemas_prefers_json_schema() -> None:
    agent = ScholarAgent.__new__(ScholarAgent)
    agent._tools = {}

    class _DummyFn:
        json_schema = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }
        description = "Search remote exam sources"

        async def __call__(self, **kwargs):
            return "ok"

    agent._tools["search_exam_sources"] = _DummyFn()
    schemas = ScholarAgent._build_tool_schemas(agent)

    assert schemas[0]["function"]["name"] == "search_exam_sources"
    assert schemas[0]["function"]["parameters"]["required"] == ["query"]
