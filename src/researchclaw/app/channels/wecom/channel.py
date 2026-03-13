"""WeCom channel implementation."""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import logging
import os
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import (
    BaseChannel,
    ContentType,
    FileContent,
    ImageContent,
    OnReplySent,
    ProcessHandler,
    TextContent,
)

logger = logging.getLogger(__name__)

WECOM_AVAILABLE = importlib.util.find_spec("wecom_aibot_sdk") is not None

_MSG_TYPE_LABELS = {
    "image": "[image]",
    "voice": "[voice]",
    "file": "[file]",
    "mixed": "[mixed]",
}


class WecomChannel(BaseChannel):
    """Enterprise WeChat bot over a long WebSocket connection."""

    channel = "wecom"

    def __init__(
        self,
        process: ProcessHandler,
        enabled: bool,
        bot_id: str,
        secret: str,
        bot_prefix: str = "",
        media_dir: str = "~/.researchclaw/media",
        welcome_message: str = "",
        on_reply_sent: OnReplySent = None,
        show_tool_details: bool = True,
        filter_tool_messages: bool = False,
    ):
        super().__init__(
            process,
            on_reply_sent=on_reply_sent,
            show_tool_details=show_tool_details,
            filter_tool_messages=filter_tool_messages,
        )
        self.enabled = enabled
        self.bot_id = bot_id
        self.secret = secret
        self.bot_prefix = bot_prefix
        self.welcome_message = welcome_message or ""
        self._media_dir = Path(media_dir).expanduser()

        self._client: Any = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._run_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._generate_req_id: Any = None

        self._processed_message_ids: OrderedDict[str, None] = OrderedDict()
        self._chat_frames: Dict[str, Any] = {}
        self._chat_frames_lock = asyncio.Lock()

    @classmethod
    def from_config(
        cls,
        process: ProcessHandler,
        config: Any,
        on_reply_sent: OnReplySent = None,
        show_tool_details: bool = True,
        filter_tool_messages: bool = False,
    ) -> "WecomChannel":
        return cls(
            process=process,
            enabled=getattr(config, "enabled", False),
            bot_id=getattr(config, "bot_id", "") or "",
            secret=getattr(config, "secret", "") or "",
            bot_prefix=getattr(config, "bot_prefix", "") or "",
            media_dir=getattr(config, "media_dir", "~/.researchclaw/media")
            or "~/.researchclaw/media",
            welcome_message=getattr(config, "welcome_message", "") or "",
            on_reply_sent=on_reply_sent,
            show_tool_details=show_tool_details,
            filter_tool_messages=filter_tool_messages,
        )

    def resolve_session_id(
        self,
        sender_id: str,
        channel_meta: Optional[Dict[str, Any]] = None,
    ) -> str:
        meta = channel_meta or {}
        chat_type = str(
            meta.get("wecom_chat_type") or meta.get("chat_type") or "single",
        ).strip() or "single"
        chat_id = str(
            meta.get("wecom_chat_id") or meta.get("chat_id") or "",
        ).strip()
        if chat_id:
            return f"{self.channel}:{chat_type}:{chat_id}"
        if sender_id:
            return f"{self.channel}:user:{sender_id}"
        return f"{self.channel}:{sender_id}"

    def build_agent_request_from_native(self, native_payload: Any) -> Any:
        payload = native_payload if isinstance(native_payload, dict) else {}
        channel_id = payload.get("channel_id") or self.channel
        sender_id = payload.get("sender_id") or ""
        content_parts = payload.get("content_parts") or []
        meta = dict(payload.get("meta") or {})
        session_id = payload.get("session_id") or self.resolve_session_id(
            sender_id,
            meta,
        )
        request = self.build_agent_request_from_user_content(
            channel_id=channel_id,
            sender_id=sender_id,
            session_id=session_id,
            content_parts=content_parts,
            channel_meta=meta,
        )
        return self._set_request_channel_meta(request, meta)

    def to_handle_from_target(self, *, user_id: str, session_id: str) -> str:
        parts = (session_id or "").split(":", 2)
        if len(parts) == 3 and parts[0] == self.channel:
            return f"{self.channel}:chat:{parts[2]}"
        if user_id:
            return f"{self.channel}:user:{user_id}"
        return ""

    def get_to_handle_from_request(self, request: Any) -> str:
        session_id = (
            request.get("session_id", "")
            if isinstance(request, dict)
            else getattr(request, "session_id", "")
        ) or ""
        user_id = (
            request.get("user_id", "")
            if isinstance(request, dict)
            else getattr(request, "user_id", "")
        ) or ""
        return self.to_handle_from_target(user_id=user_id, session_id=session_id)

    def get_on_reply_sent_args(
        self,
        request: Any,
        to_handle: str,
    ) -> tuple[str, str]:
        user_id = (
            request.get("user_id", "")
            if isinstance(request, dict)
            else getattr(request, "user_id", "")
        ) or to_handle
        session_id = (
            request.get("session_id", "")
            if isinstance(request, dict)
            else getattr(request, "session_id", "")
        ) or f"{self.channel}:{to_handle}"
        return (user_id, session_id)

    @staticmethod
    def _set_request_channel_meta(
        request: Any,
        meta: Dict[str, Any],
    ) -> Any:
        if isinstance(request, dict):
            request["channel_meta"] = meta
            return request
        if hasattr(request, "channel_meta"):
            request.channel_meta = meta
            return request
        try:
            setattr(request, "channel_meta", meta)
        except Exception:
            logger.debug("wecom set channel_meta failed", exc_info=True)
        return request

    @staticmethod
    def _is_user_text_part(item: Any) -> bool:
        text = str(getattr(item, "text", "") or "").strip()
        if not text:
            return False
        lowered = text.lower()
        if lowered in {
            "[image]",
            "[voice]",
            "[file]",
            "[mixed]",
        }:
            return False
        if lowered.startswith("[image: download failed"):
            return False
        if lowered.startswith("[file:"):
            return False
        return True

    def _content_has_text(self, contents: List[Any]) -> bool:
        """Only real user text triggers a model turn for WeCom.

        Pure image/file inputs are buffered until the next text-bearing turn,
        so the model only sees attachments together with the user's question.
        """
        if not contents:
            return False

        for item in contents:
            t = getattr(item, "type", None)
            t_val = (
                t.value if isinstance(t, ContentType) else str(t) if t else ""
            ).lower()
            if t_val == ContentType.TEXT.value and self._is_user_text_part(item):
                return True
            if t_val == ContentType.REFUSAL.value:
                refusal = str(getattr(item, "refusal", "") or "").strip()
                if refusal:
                    return True
        return False

    def merge_native_items(self, items: List[Any]) -> Any:
        if not items:
            return None
        first = items[0] if isinstance(items[0], dict) else {}
        merged_parts: List[Any] = []
        for item in items:
            payload = item if isinstance(item, dict) else {}
            merged_parts.extend(payload.get("content_parts") or [])
        last = items[-1] if isinstance(items[-1], dict) else {}
        return {
            "channel_id": first.get("channel_id") or self.channel,
            "sender_id": last.get("sender_id", first.get("sender_id", "")),
            "user_id": last.get("user_id", first.get("user_id", "")),
            "session_id": last.get("session_id", first.get("session_id", "")),
            "content_parts": merged_parts,
            "meta": dict(last.get("meta") or {}),
        }

    async def _before_consume_process(self, request: Any) -> None:
        meta = getattr(request, "channel_meta", None) or {}
        frame = meta.get("wecom_frame")
        chat_id = str(meta.get("wecom_chat_id") or "").strip()
        if frame is not None and chat_id:
            await self._save_chat_frame(chat_id, frame)

    async def start(self) -> None:
        if not self.enabled:
            logger.debug("wecom channel disabled")
            return
        if not WECOM_AVAILABLE:
            logger.warning(
                "wecom dependency missing. Install the SDK that provides "
                "'wecom_aibot_sdk' before enabling this channel.",
            )
            return
        if not self.bot_id or not self.secret:
            raise RuntimeError(
                "wecom bot_id and secret are required when channel is enabled.",
            )
        if self._run_task and not self._run_task.done():
            return
        self._loop = asyncio.get_running_loop()
        self._stop_event.clear()
        self._run_task = asyncio.create_task(
            self._run_client(),
            name="wecom_channel",
        )

    async def stop(self) -> None:
        self._stop_event.set()
        await self._disconnect_client()
        if self._run_task and not self._run_task.done():
            self._run_task.cancel()
            try:
                await self._run_task
            except asyncio.CancelledError:
                pass
        self._run_task = None

    async def send(
        self,
        to_handle: str,
        text: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.enabled or not text.strip():
            return
        if self._client is None:
            logger.warning("wecom send skipped: client not initialized")
            return

        route = self._route_from_handle(to_handle, meta)
        chat_id = route.get("chat_id") or ""
        frame = route.get("frame")
        if frame is None and chat_id:
            frame = await self._load_chat_frame(chat_id)

        try:
            if frame is not None:
                stream_id = self._make_stream_id()
                await self._client.reply_stream(
                    frame,
                    stream_id,
                    text.strip(),
                    finish=True,
                )
                return

            send_message = getattr(self._client, "send_message", None)
            if callable(send_message) and chat_id:
                result = send_message(
                    chat_id,
                    {
                        "msgtype": "markdown",
                        "markdown": {"content": text.strip()},
                    },
                )
                if inspect.isawaitable(result):
                    await result
                return

            logger.warning(
                "wecom send skipped: no frame or proactive chat target for "
                "to_handle=%s.",
                to_handle,
            )
        except Exception:
            logger.exception("wecom send failed")

    async def _run_client(self) -> None:
        try:
            from wecom_aibot_sdk import WSClient, generate_req_id

            self._generate_req_id = generate_req_id
            self._client = WSClient(
                {
                    "bot_id": self.bot_id,
                    "secret": self.secret,
                    "reconnect_interval": 1000,
                    "max_reconnect_attempts": -1,
                    "heartbeat_interval": 30000,
                },
            )
            self._client.on("connected", self._on_connected)
            self._client.on("authenticated", self._on_authenticated)
            self._client.on("disconnected", self._on_disconnected)
            self._client.on("error", self._on_error)
            self._client.on("message.text", self._on_text_message)
            self._client.on("message.image", self._on_image_message)
            self._client.on("message.voice", self._on_voice_message)
            self._client.on("message.file", self._on_file_message)
            self._client.on("message.mixed", self._on_mixed_message)
            self._client.on("event.enter_chat", self._on_enter_chat)

            logger.info("wecom WebSocket connecting")
            await self._client.connect_async()
            while not self._stop_event.is_set():
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("wecom client loop failed")
        finally:
            await self._disconnect_client()

    async def _disconnect_client(self) -> None:
        client = self._client
        self._client = None
        if client is None:
            return
        try:
            disconnect = getattr(client, "disconnect", None)
            if disconnect is None:
                return
            result = disconnect()
            if inspect.isawaitable(result):
                await result
        except Exception:
            logger.debug("wecom disconnect failed", exc_info=True)

    async def _on_connected(self, frame: Any) -> None:
        logger.info("wecom WebSocket connected")

    async def _on_authenticated(self, frame: Any) -> None:
        logger.info("wecom authenticated")

    async def _on_disconnected(self, frame: Any) -> None:
        reason = getattr(frame, "body", None) or frame
        logger.warning("wecom WebSocket disconnected: %s", reason)

    async def _on_error(self, frame: Any) -> None:
        logger.error("wecom error: %s", frame)

    async def _on_text_message(self, frame: Any) -> None:
        await self._process_message(frame, "text")

    async def _on_image_message(self, frame: Any) -> None:
        await self._process_message(frame, "image")

    async def _on_voice_message(self, frame: Any) -> None:
        await self._process_message(frame, "voice")

    async def _on_file_message(self, frame: Any) -> None:
        await self._process_message(frame, "file")

    async def _on_mixed_message(self, frame: Any) -> None:
        await self._process_message(frame, "mixed")

    async def _on_enter_chat(self, frame: Any) -> None:
        if not self.welcome_message or self._client is None:
            return
        try:
            await self._client.reply_welcome(
                frame,
                {
                    "msgtype": "text",
                    "text": {"content": self.welcome_message},
                },
            )
        except Exception:
            logger.debug("wecom welcome reply failed", exc_info=True)

    async def _process_message(self, frame: Any, msg_type: str) -> None:
        body = self._extract_frame_body(frame)
        if not body:
            return

        msg_id = str(body.get("msgid") or "").strip()
        if not msg_id:
            msg_id = (
                f"{body.get('chatid', '')}_{body.get('sendertime', '')}"
            ).strip("_")
        if not msg_id or not self._accept_message_id(msg_id):
            return

        from_info = body.get("from") or {}
        sender_id = str(
            from_info.get("userid")
            or body.get("userid")
            or body.get("sender")
            or "",
        ).strip()
        chat_type = str(body.get("chattype") or "single").strip() or "single"
        chat_id = str(body.get("chatid") or sender_id or "").strip()
        if not sender_id or not chat_id:
            return

        content_parts = await self._build_content_parts(body, msg_type)
        if not content_parts:
            return

        await self._save_chat_frame(chat_id, frame)
        meta = {
            "wecom_message_id": msg_id,
            "wecom_msg_type": msg_type,
            "wecom_sender_id": sender_id,
            "wecom_chat_id": chat_id,
            "wecom_chat_type": chat_type,
            "wecom_frame": frame,
        }
        session_id = self.resolve_session_id(sender_id, meta)
        native = {
            "channel_id": self.channel,
            "sender_id": sender_id,
            "user_id": sender_id,
            "session_id": session_id,
            "content_parts": content_parts,
            "meta": meta,
        }
        if self._enqueue is not None:
            self._enqueue(native)

    async def _build_content_parts(
        self,
        body: Dict[str, Any],
        msg_type: str,
    ) -> List[Any]:
        parts: List[Any] = []
        text_bits: List[str] = []

        if msg_type == "text":
            text = str(
                ((body.get("text") or {}).get("content") or ""),
            ).strip()
            if text:
                text_bits.append(text)
        elif msg_type == "image":
            url_or_path = await self._download_media_from_payload(
                body.get("image") or {},
                "image",
            )
            if url_or_path:
                parts.append(
                    ImageContent(
                        type=ContentType.IMAGE,
                        image_url=url_or_path,
                    ),
                )
            else:
                text_bits.append("[image: download failed]")
        elif msg_type == "file":
            file_info = body.get("file") or {}
            url_or_path = await self._download_media_from_payload(
                file_info,
                "file",
                filename=file_info.get("name"),
            )
            if url_or_path:
                parts.append(
                    FileContent(
                        type=ContentType.FILE,
                        file_url=url_or_path,
                    ),
                )
            else:
                name = file_info.get("name") or "unknown"
                text_bits.append(f"[file: {name}]")
        elif msg_type == "voice":
            voice_info = body.get("voice") or {}
            transcript = str(voice_info.get("content") or "").strip()
            if transcript:
                text_bits.append(f"[voice] {transcript}")
            else:
                text_bits.append("[voice]")
        elif msg_type == "mixed":
            for item in ((body.get("mixed") or {}).get("item") or []):
                if not isinstance(item, dict):
                    continue
                item_type = str(item.get("type") or "").strip()
                if item_type == "text":
                    text = str(
                        ((item.get("text") or {}).get("content") or ""),
                    ).strip()
                    if text:
                        text_bits.append(text)
                elif item_type == "image":
                    url_or_path = await self._download_media_from_payload(
                        item.get("image") or {},
                        "image",
                    )
                    if url_or_path:
                        parts.append(
                            ImageContent(
                                type=ContentType.IMAGE,
                                image_url=url_or_path,
                            ),
                        )
                    else:
                        text_bits.append("[image: download failed]")
                elif item_type == "file":
                    file_info = item.get("file") or {}
                    url_or_path = await self._download_media_from_payload(
                        file_info,
                        "file",
                        filename=file_info.get("name"),
                    )
                    if url_or_path:
                        parts.append(
                            FileContent(
                                type=ContentType.FILE,
                                file_url=url_or_path,
                            ),
                        )
                    else:
                        name = file_info.get("name") or "unknown"
                        text_bits.append(f"[file: {name}]")
                else:
                    text_bits.append(
                        _MSG_TYPE_LABELS.get(item_type, f"[{item_type}]"),
                    )
        else:
            text_bits.append(_MSG_TYPE_LABELS.get(msg_type, f"[{msg_type}]"))

        text = "\n".join(x for x in text_bits if x).strip()
        if text:
            parts.insert(0, TextContent(type=ContentType.TEXT, text=text))
        return parts

    async def _download_media_from_payload(
        self,
        payload: Dict[str, Any],
        media_type: str,
        *,
        filename: Optional[str] = None,
    ) -> Optional[str]:
        if not isinstance(payload, dict) or self._client is None:
            return None
        file_url = str(payload.get("url") or "").strip()
        aes_key = str(payload.get("aeskey") or "").strip()
        if not file_url or not aes_key:
            return None
        download = getattr(self._client, "download_file", None)
        if download is None:
            return None
        try:
            data, suggested_name = await download(file_url, aes_key)
        except Exception:
            logger.debug("wecom download %s failed", media_type, exc_info=True)
            return None
        if not data:
            return None

        target_name = os.path.basename(
            str(filename or suggested_name or f"{media_type}_{int(time.time())}"),
        )
        if not target_name:
            target_name = f"{media_type}_{int(time.time())}"
        self._media_dir.mkdir(parents=True, exist_ok=True)
        path = self._media_dir / target_name
        if path.exists():
            stem = path.stem
            suffix = path.suffix
            path = self._media_dir / f"{stem}_{int(time.time() * 1000)}{suffix}"
        path.write_bytes(data)
        return str(path)

    @staticmethod
    def _extract_frame_body(frame: Any) -> Dict[str, Any]:
        if hasattr(frame, "body"):
            body = getattr(frame, "body", None) or {}
        elif isinstance(frame, dict):
            body = frame.get("body", frame)
        else:
            body = {}
        return body if isinstance(body, dict) else {}

    def _accept_message_id(self, msg_id: str) -> bool:
        if not msg_id or msg_id in self._processed_message_ids:
            return False
        self._processed_message_ids[msg_id] = None
        while len(self._processed_message_ids) > 1000:
            self._processed_message_ids.popitem(last=False)
        return True

    async def _save_chat_frame(self, chat_id: str, frame: Any) -> None:
        if not chat_id:
            return
        async with self._chat_frames_lock:
            self._chat_frames[chat_id] = frame

    async def _load_chat_frame(self, chat_id: str) -> Any:
        if not chat_id:
            return None
        async with self._chat_frames_lock:
            return self._chat_frames.get(chat_id)

    def _route_from_handle(
        self,
        to_handle: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        merged = dict(meta or {})
        frame = merged.get("wecom_frame") or merged.get("frame")
        chat_id = str(
            merged.get("wecom_chat_id")
            or merged.get("chat_id")
            or merged.get("user_id")
            or "",
        ).strip()
        s = (to_handle or "").strip()
        parts = s.split(":", 2)
        if len(parts) == 3 and parts[0] == self.channel:
            chat_id = parts[2] or chat_id
        elif s:
            chat_id = s
        return {"chat_id": chat_id, "frame": frame}

    def _make_stream_id(self) -> str:
        if callable(self._generate_req_id):
            try:
                return str(self._generate_req_id("stream"))
            except Exception:
                logger.debug("wecom generate_req_id failed", exc_info=True)
        return f"stream_{int(time.time() * 1000)}"
