import asyncio
import time

from researchclaw.app.runner.runner import AgentRunner


class _SlowAgent:
    def reply_stream(self, message, session_id=None, attachments=None):
        yield {"type": "stage_message", "content": "start"}
        time.sleep(61)
        yield {"type": "stage_message", "content": "after wait"}
        yield {"type": "done", "content": "done"}


def test_chat_stream_survives_long_gap_between_events():
    runner = AgentRunner()
    runner.agent = _SlowAgent()
    runner._is_running = True

    async def collect():
        items = []
        async for event in runner.chat_stream('x', session_id='s'):
            items.append(event)
            if len(items) >= 3:
                break
        return items

    items = asyncio.run(collect())
    assert [item.get('content') for item in items] == ['start', 'after wait', 'done']
