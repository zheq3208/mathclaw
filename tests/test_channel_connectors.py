import asyncio
from types import SimpleNamespace

from researchclaw.app._app import _build_channel_runtime_config
from researchclaw.app.channels.base import ImageContent, TextContent
from researchclaw.app.channels.qq import QQChannel
from researchclaw.app.channels.registry import get_channel_registry
from researchclaw.app.channels.wecom import WecomChannel
from researchclaw.app.runner.manager import AgentRunnerManager
from researchclaw.config.watcher import ConfigWatcher


async def _noop_process(request):
    if False:
        yield request


class _FakeWecomClient:
    def __init__(self):
        self.calls = []
        self.sent = []

    async def reply_stream(self, frame, stream_id, content, finish=True):
        self.calls.append((frame, stream_id, content, finish))

    async def send_message(self, chatid, body):
        self.sent.append((chatid, body))


def test_runtime_config_recognizes_top_level_wecom():
    cfg = _build_channel_runtime_config({"wecom": {"enabled": True}})
    assert cfg.channels.wecom.enabled is True

    normalized = ConfigWatcher._normalize_channels({"wecom": {"enabled": True}})
    assert normalized["wecom"]["enabled"] is True


def test_registry_includes_wecom():
    registry = get_channel_registry()
    assert "wecom" in registry


def test_qq_routes_sessions_by_chat_target():
    channel = QQChannel(
        process=_noop_process,
        enabled=False,
        app_id="",
        client_secret="",
    )

    assert channel.resolve_session_id(
        "user-openid",
        {"message_type": "c2c"},
    ) == "qq:c2c:user-openid"
    assert channel.resolve_session_id(
        "member-openid",
        {"message_type": "group", "group_openid": "group-1"},
    ) == "qq:group:group-1"
    assert channel.resolve_session_id(
        "user-1",
        {"message_type": "guild", "channel_id": "channel-1"},
    ) == "qq:channel:channel-1"

    assert channel.to_handle_from_target(
        user_id="user-openid",
        session_id="qq:c2c:user-openid",
    ) == "user-openid"
    assert channel.to_handle_from_target(
        user_id="member-openid",
        session_id="qq:group:group-1",
    ) == "group:group-1"
    assert channel.to_handle_from_target(
        user_id="user-1",
        session_id="qq:channel:channel-1",
    ) == "channel:channel-1"


def test_qq_reply_callback_uses_user_and_session():
    channel = QQChannel(
        process=_noop_process,
        enabled=False,
        app_id="",
        client_secret="",
    )
    request = SimpleNamespace(user_id="user-openid", session_id="qq:group:group-1")
    assert channel.get_on_reply_sent_args(request, "group:group-1") == (
        "user-openid",
        "qq:group:group-1",
    )


def test_qq_dict_request_flow_does_not_crash():
    async def _empty_process(request):
        if False:
            yield request

    async def _run() -> None:
        channel = QQChannel(
            process=_empty_process,
            enabled=False,
            app_id="",
            client_secret="",
        )

        request = channel.build_agent_request_from_native(
            {
                "channel_id": "qq",
                "sender_id": "user-openid",
                "content_parts": [{"type": "text", "text": "hello"}],
                "meta": {
                    "message_type": "c2c",
                    "message_id": "msg-1",
                    "sender_id": "user-openid",
                },
            },
        )
        assert isinstance(request, dict)
        assert request["channel_meta"]["message_id"] == "msg-1"

        await channel.consume_one(request)

    asyncio.run(_run())


def test_qq_builds_image_parts_from_incoming_attachments(tmp_path):
    channel = QQChannel(
        process=_noop_process,
        enabled=False,
        app_id="",
        client_secret="",
    )

    image_path = tmp_path / "question.png"
    image_path.write_bytes(b"fake-image")

    channel._download_attachment_sync = (  # type: ignore[method-assign]
        lambda attachment, *, message_id, attachment_index: str(image_path)
    )

    parts = channel._build_incoming_content_parts(
        text="solve it",
        attachments=[
            {
                "url": "https://example.com/question.png",
                "filename": "question.png",
                "content_type": "image/png",
            },
        ],
        message_id="msg-1",
    )

    assert isinstance(parts[0], TextContent)
    assert parts[0].text == "solve it"
    assert any(
        isinstance(part, ImageContent) and part.image_url == str(image_path)
        for part in parts
    )


def test_qq_buffers_image_only_until_next_text_message(tmp_path):
    seen_requests = []

    async def _capture_process(request):
        seen_requests.append(request)
        yield SimpleNamespace(
            object="response",
            status="completed",
            type="response",
            error=None,
        )

    channel = QQChannel(
        process=_capture_process,
        enabled=False,
        app_id="",
        client_secret="",
    )

    image_path = (tmp_path / "question.png").resolve()
    image_path.write_bytes(b"fake-image")

    image_request = channel.build_agent_request_from_native(
        {
            "channel_id": "qq",
            "sender_id": "user-openid",
            "content_parts": [
                ImageContent(image_url=str(image_path)),
            ],
            "meta": {
                "message_type": "c2c",
                "message_id": "msg-image",
                "sender_id": "user-openid",
            },
        },
    )
    asyncio.run(channel.consume_one(image_request))

    assert seen_requests == []
    pending = channel._pending_content_by_session["qq:c2c:user-openid"]
    assert len(pending) == 1
    assert isinstance(pending[0], ImageContent)

    text_request = channel.build_agent_request_from_native(
        {
            "channel_id": "qq",
            "sender_id": "user-openid",
            "content_parts": [
                TextContent(text="solve question 6"),
            ],
            "meta": {
                "message_type": "c2c",
                "message_id": "msg-text",
                "sender_id": "user-openid",
            },
        },
    )
    asyncio.run(channel.consume_one(text_request))

    assert len(seen_requests) == 1
    merged_input = seen_requests[0]["input"][0]["content"]
    assert isinstance(merged_input[0], ImageContent)
    assert merged_input[0].image_url == str(image_path)
    assert isinstance(merged_input[1], TextContent)
    assert merged_input[1].text == "solve question 6"
    assert "qq:c2c:user-openid" not in channel._pending_content_by_session


def test_manager_stream_query_forwards_local_image_parts_as_attachments(tmp_path):
    manager = AgentRunnerManager()
    image_path = (tmp_path / "paper.png").resolve()
    image_path.write_bytes(b"fake-image")

    captured: dict[str, object] = {}

    async def _fake_chat_stream(message, session_id=None, attachments=None):
        captured["message"] = message
        captured["session_id"] = session_id
        captured["attachments"] = attachments
        yield {"type": "done", "content": "ok"}

    manager.chat_stream = _fake_chat_stream  # type: ignore[method-assign]

    request = {
        "session_id": "qq:c2c:user-openid",
        "user_id": "user-openid",
        "channel": "qq",
        "input": [
            {
                "role": "user",
                "content": [
                    TextContent(text="solve question 6"),
                    ImageContent(image_url=str(image_path)),
                ],
            },
        ],
    }

    async def _run():
        async for _event in manager.stream_query(request):
            pass

    asyncio.run(_run())

    assert captured["message"] == "solve question 6"
    assert captured["session_id"] == "qq:c2c:user-openid"
    attachments = captured["attachments"]
    assert isinstance(attachments, list)
    assert attachments[0]["kind"] == "image"
    assert attachments[0]["absolute_path"] == str(image_path)
    assert attachments[0]["name"] == "paper.png"


def test_wecom_dict_request_keeps_channel_meta():
    channel = WecomChannel(
        process=_noop_process,
        enabled=False,
        bot_id="",
        secret="",
    )

    request = channel.build_agent_request_from_native(
        {
            "channel_id": "wecom",
            "sender_id": "user-1",
            "content_parts": [TextContent(text="hello")],
            "meta": {
                "wecom_chat_id": "chat-1",
                "wecom_chat_type": "single",
            },
        },
    )

    assert isinstance(request, dict)
    assert request["channel_meta"]["wecom_chat_id"] == "chat-1"


def test_wecom_buffers_image_only_until_next_text_message(tmp_path):
    seen_requests = []

    async def _capture_process(request):
        seen_requests.append(request)
        yield SimpleNamespace(
            object="response",
            status="completed",
            type="response",
            error=None,
        )

    channel = WecomChannel(
        process=_capture_process,
        enabled=False,
        bot_id="",
        secret="",
    )

    image_path = (tmp_path / "wecom-question-1.png").resolve()
    image_path.write_bytes(b"fake-image-1")
    image_payload = {
        "channel_id": "wecom",
        "sender_id": "user-1",
        "session_id": "wecom:single:chat-1",
        "content_parts": [ImageContent(image_url=str(image_path))],
        "meta": {
            "wecom_chat_id": "chat-1",
            "wecom_chat_type": "single",
        },
    }
    asyncio.run(channel.consume_one(image_payload))

    assert seen_requests == []
    pending = channel._pending_content_by_session["wecom:single:chat-1"]
    assert len(pending) == 1
    assert isinstance(pending[0], ImageContent)

    text_payload = {
        "channel_id": "wecom",
        "sender_id": "user-1",
        "session_id": "wecom:single:chat-1",
        "content_parts": [TextContent(text="describe both images")],
        "meta": {
            "wecom_chat_id": "chat-1",
            "wecom_chat_type": "single",
        },
    }
    asyncio.run(channel.consume_one(text_payload))

    assert len(seen_requests) == 1
    merged_input = seen_requests[0]["input"][0]["content"]
    assert isinstance(merged_input[0], ImageContent)
    assert merged_input[0].image_url == str(image_path)
    assert isinstance(merged_input[1], TextContent)
    assert merged_input[1].text == "describe both images"
    assert "wecom:single:chat-1" not in channel._pending_content_by_session


def test_wecom_mixed_message_keeps_multiple_images(tmp_path):
    channel = WecomChannel(
        process=_noop_process,
        enabled=False,
        bot_id="",
        secret="",
    )

    image_one = (tmp_path / "mixed-1.png").resolve()
    image_two = (tmp_path / "mixed-2.png").resolve()
    image_one.write_bytes(b"img-1")
    image_two.write_bytes(b"img-2")

    async def _fake_download(payload, media_type, *, filename=None):
        url = str((payload or {}).get("url") or "")
        if url.endswith("1"):
            return str(image_one)
        if url.endswith("2"):
            return str(image_two)
        return None

    channel._download_media_from_payload = _fake_download  # type: ignore[method-assign]

    parts = asyncio.run(
        channel._build_content_parts(
            {
                "mixed": {
                    "item": [
                        {
                            "type": "image",
                            "image": {"url": "image-1", "aeskey": "k1"},
                        },
                        {
                            "type": "text",
                            "text": {"content": "describe the figures"},
                        },
                        {
                            "type": "image",
                            "image": {"url": "image-2", "aeskey": "k2"},
                        },
                    ]
                }
            },
            "mixed",
        )
    )

    assert isinstance(parts[0], TextContent)
    assert parts[0].text == "describe the figures"
    image_parts = [part for part in parts if isinstance(part, ImageContent)]
    assert [part.image_url for part in image_parts] == [
        str(image_one),
        str(image_two),
    ]


def test_wecom_process_message_enqueues_native_payload():
    captured = []

    async def _fake_build_content_parts(body, msg_type):
        return [TextContent(text="hello")]

    channel = WecomChannel(
        process=_noop_process,
        enabled=False,
        bot_id="",
        secret="",
    )
    channel._build_content_parts = _fake_build_content_parts  # type: ignore[method-assign]
    channel._enqueue = captured.append

    frame = {
        "body": {
            "msgid": "msg-1",
            "chattype": "single",
            "chatid": "chat-1",
            "from": {"userid": "user-1"},
        }
    }

    asyncio.run(channel._process_message(frame, "text"))

    assert len(captured) == 1
    payload = captured[0]
    assert payload["session_id"] == "wecom:single:chat-1"
    assert payload["meta"]["wecom_chat_id"] == "chat-1"
    assert isinstance(payload["content_parts"][0], TextContent)


def test_wecom_send_uses_cached_frame_by_chat():
    async def _run() -> None:
        channel = WecomChannel(
            process=_noop_process,
            enabled=True,
            bot_id="bot",
            secret="secret",
        )
        channel._client = _FakeWecomClient()
        channel._generate_req_id = lambda kind: f"{kind}-001"

        frame = {"body": {"chatid": "chat-1"}}
        await channel._save_chat_frame("chat-1", frame)
        await channel.send("wecom:chat:chat-1", "hello")

        assert channel._client.calls == [(frame, "stream-001", "hello", True)]

    asyncio.run(_run())


def test_wecom_send_falls_back_to_proactive_send_message():
    async def _run() -> None:
        channel = WecomChannel(
            process=_noop_process,
            enabled=True,
            bot_id="bot",
            secret="secret",
        )
        channel._client = _FakeWecomClient()

        await channel.send("wecom:chat:chat-2", "hello proactive")

        assert channel._client.calls == []
        assert channel._client.sent == [
            (
                "chat-2",
                {
                    "msgtype": "markdown",
                    "markdown": {"content": "hello proactive"},
                },
            )
        ]

    asyncio.run(_run())


def test_wecom_routes_session_by_chat():
    channel = WecomChannel(
        process=_noop_process,
        enabled=False,
        bot_id="",
        secret="",
    )

    assert channel.resolve_session_id(
        "user-1",
        {"wecom_chat_type": "single", "wecom_chat_id": "chat-1"},
    ) == "wecom:single:chat-1"
    assert channel.resolve_session_id(
        "user-1",
        {"wecom_chat_type": "group", "wecom_chat_id": "group-1"},
    ) == "wecom:group:group-1"
    assert channel.to_handle_from_target(
        user_id="user-1",
        session_id="wecom:group:group-1",
    ) == "wecom:chat:group-1"
