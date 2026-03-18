import asyncio
from pathlib import Path
from types import SimpleNamespace

from mathclaw.app.crons import heartbeat as hb


class _Runner:
    def __init__(self):
        self.calls = 0

    async def stream_query(self, req):
        self.calls += 1
        if False:
            yield req


def test_run_heartbeat_once_skips_when_disabled(tmp_path):
    runner = _Runner()
    heartbeat_file = tmp_path / "HEARTBEAT.md"
    heartbeat_file.write_text("send something", encoding="utf-8")

    orig_cfg = hb._get_heartbeat_config_safe
    orig_path = hb._get_heartbeat_query_path
    try:
        hb._get_heartbeat_config_safe = lambda: SimpleNamespace(
            enabled=False,
            every="1h",
            target="last",
            active_hours=None,
        )
        hb._get_heartbeat_query_path = lambda _working_dir: heartbeat_file

        asyncio.run(hb.run_heartbeat_once(runner=runner, channel_manager=None))
    finally:
        hb._get_heartbeat_config_safe = orig_cfg
        hb._get_heartbeat_query_path = orig_path

    assert runner.calls == 0


def test_run_heartbeat_once_skips_comment_only_file(tmp_path):
    runner = _Runner()
    heartbeat_file = tmp_path / "HEARTBEAT.md"
    heartbeat_file.write_text(
        "# comment only\n\n# still comment\n",
        encoding="utf-8",
    )

    orig_cfg = hb._get_heartbeat_config_safe
    orig_path = hb._get_heartbeat_query_path
    try:
        hb._get_heartbeat_config_safe = lambda: SimpleNamespace(
            enabled=True,
            every="1h",
            target="",
            active_hours=None,
        )
        hb._get_heartbeat_query_path = lambda _working_dir: heartbeat_file

        asyncio.run(hb.run_heartbeat_once(runner=runner, channel_manager=None))
    finally:
        hb._get_heartbeat_config_safe = orig_cfg
        hb._get_heartbeat_query_path = orig_path

    assert runner.calls == 0


def test_normalize_heartbeat_query_drops_comment_lines():
    query = hb._normalize_heartbeat_query(
        "# title\n\n- keep this\ntext\n# footer\n",
    )

    assert query == "- keep this\ntext"
