# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches,too-many-statements
"""QQ Channel.

QQ uses WebSocket for incoming events and HTTP API for replies.
No request-reply coupling: handler enqueues Incoming, consumer processes
and sends reply via send_c2c_message / send_channel_message /
send_group_message.
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

try:
    import aiohttp
except ImportError:  # pragma: no cover - optional dependency
    aiohttp = None  # type: ignore[assignment]

from ..base import (
    BaseChannel,
    ContentType,
    FileContent,
    ImageContent,
    OnReplySent,
    OutgoingContentPart,
    ProcessHandler,
    RunStatus,
    TextContent,
)

logger = logging.getLogger(__name__)

# QQ Bot WebSocket op codes
OP_DISPATCH = 0
OP_HEARTBEAT = 1
OP_IDENTIFY = 2
OP_RESUME = 6
OP_RECONNECT = 7
OP_INVALID_SESSION = 9
OP_HELLO = 10
OP_HEARTBEAT_ACK = 11

# Intents
INTENT_PUBLIC_GUILD_MESSAGES = 1 << 30
INTENT_DIRECT_MESSAGE = 1 << 12
INTENT_GROUP_AND_C2C = 1 << 25
INTENT_GUILD_MEMBERS = 1 << 1

RECONNECT_DELAYS = [1, 2, 5, 10, 30, 60]
RATE_LIMIT_DELAY = 60
MAX_RECONNECT_ATTEMPTS = 100
QUICK_DISCONNECT_THRESHOLD = 5
MAX_QUICK_DISCONNECT_COUNT = 3

DEFAULT_API_BASE = "https://api.sgroup.qq.com"
TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"
_URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_SAFE_FILE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")
_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
}


def _sanitize_qq_text(text: str) -> tuple[str, bool]:
    """QQ API disallows URL links in plain messages.

    Return the sanitized text and whether any URL was removed.
    """
    if not text:
        return "", False
    sanitized, count = _URL_PATTERN.subn("[链接已省略]", text)
    return sanitized, count > 0


def _get_api_base() -> str:
    """API root address (e.g. sandbox: https://sandbox.api.sgroup.qq.com)"""
    return os.getenv("QQ_API_BASE", DEFAULT_API_BASE).rstrip("/")


def _normalize_attachment_url(value: Any) -> str:
    url = str(value or "").strip()
    if not url:
        return ""
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("/"):
        return f"{_get_api_base()}{url}"
    return url


def _guess_attachment_name(attachment: Dict[str, Any], url: str) -> str:
    for key in ("filename", "name", "file_name", "fileName"):
        value = str(attachment.get(key, "")).strip()
        if value:
            return value
    path_name = Path(urlparse(url).path).name
    return path_name or "attachment"


def _guess_attachment_mime_type(
    attachment: Dict[str, Any],
    name: str,
) -> str:
    for key in ("content_type", "contentType", "mime_type", "mimeType"):
        value = str(attachment.get(key, "")).strip().lower()
        if "/" in value:
            return value
    return (mimetypes.guess_type(name)[0] or "").lower()


def _guess_attachment_kind(
    attachment: Dict[str, Any],
) -> tuple[str, str, str, str]:
    url = _normalize_attachment_url(
        attachment.get("url")
        or attachment.get("proxy_url")
        or attachment.get("download_url"),
    )
    name = _guess_attachment_name(attachment, url)
    mime_type = _guess_attachment_mime_type(attachment, name)
    suffix = Path(name).suffix.lower()
    if mime_type.startswith("image/") or suffix in _IMAGE_EXTENSIONS:
        return ("image", name, mime_type, url)
    if mime_type == "application/pdf" or suffix == ".pdf":
        return ("pdf", name, mime_type, url)
    return ("", name, mime_type, url)


def _get_channel_url_sync(access_token: str) -> str:
    import urllib.error
    import urllib.request

    url = f"{_get_api_base()}/gateway"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"QQBot {access_token}",
            "Content-Type": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode() if e.fp else ""
        except Exception:
            pass
        msg = f"HTTP {e.code}: {e.reason}"
        if body:
            msg += f" | body: {body[:500]}"
        raise RuntimeError(f"Failed to get channel url: {msg}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to get channel url: {e}") from e
    channel_url = data.get("url")
    if not channel_url:
        raise RuntimeError(f"No url in channel response: {data}")
    return channel_url


def _api_request_sync(
    access_token: str,
    method: str,
    path: str,
    body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    import urllib.request

    url = f"{_get_api_base()}{path}"
    data = None
    if body is not None:
        data = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"QQBot {access_token}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


_msg_seq: Dict[str, int] = {}
_msg_seq_lock = threading.Lock()


def _get_next_msg_seq(msg_id: str) -> int:
    with _msg_seq_lock:
        n = _msg_seq.get(msg_id, 0) + 1
        _msg_seq[msg_id] = n
        if len(_msg_seq) > 1000:
            for k in list(_msg_seq.keys())[:500]:
                del _msg_seq[k]
        return n


async def _api_request_async(
    session: Any,
    access_token: str,
    method: str,
    path: str,
    body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    url = f"{_get_api_base()}{path}"
    kwargs = {
        "headers": {
            "Authorization": f"QQBot {access_token}",
            "Content-Type": "application/json",
        },
    }
    if body is not None:
        kwargs["json"] = body
    async with session.request(method, url, **kwargs) as resp:
        data = await resp.json()
        if resp.status >= 400:
            raise RuntimeError(f"API {path} {resp.status}: {data}")
        return data


async def _send_c2c_message_async(
    session: Any,
    access_token: str,
    openid: str,
    content: str,
    msg_id: Optional[str] = None,
) -> None:
    msg_seq = _get_next_msg_seq(msg_id or "c2c")
    body = {"content": content, "msg_type": 0, "msg_seq": msg_seq}
    if msg_id:
        body["msg_id"] = msg_id
    await _api_request_async(
        session,
        access_token,
        "POST",
        f"/v2/users/{openid}/messages",
        body,
    )


async def _send_channel_message_async(
    session: Any,
    access_token: str,
    channel_id: str,
    content: str,
    msg_id: Optional[str] = None,
) -> None:
    body = {"content": content}
    if msg_id:
        body["msg_id"] = msg_id
    await _api_request_async(
        session,
        access_token,
        "POST",
        f"/channels/{channel_id}/messages",
        body,
    )


async def _send_group_message_async(
    session: Any,
    access_token: str,
    group_openid: str,
    content: str,
    msg_id: Optional[str] = None,
) -> None:
    msg_seq = _get_next_msg_seq(msg_id or "group")
    body = {"content": content, "msg_type": 0, "msg_seq": msg_seq}
    if msg_id:
        body["msg_id"] = msg_id
    await _api_request_async(
        session,
        access_token,
        "POST",
        f"/v2/groups/{group_openid}/messages",
        body,
    )


class QQChannel(BaseChannel):
    """QQ Channel:
    WebSocket events -> Incoming -> process -> HTTP API reply.
    """

    channel = "qq"

    def __init__(
        self,
        process: ProcessHandler,
        enabled: bool,
        app_id: str,
        client_secret: str,
        bot_prefix: str = "",
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
        self.app_id = app_id
        self.client_secret = client_secret
        self.bot_prefix = bot_prefix

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._account_id = "default"
        self._token_cache: Optional[Dict[str, Any]] = None
        self._token_lock = threading.Lock()

        self._http: Optional[Any] = None
        self._media_dir = Path(
            os.path.expanduser("~/.mathclaw/media/qq"),
        ).resolve()
        self._media_dir.mkdir(parents=True, exist_ok=True)

    def _get_access_token_sync(self) -> str:
        """Sync get access_token for WebSocket thread. Instance-level cache."""
        with self._token_lock:
            if (
                self._token_cache
                and time.time() < self._token_cache["expires_at"] - 300
            ):
                return self._token_cache["token"]
        try:
            import urllib.request

            req = urllib.request.Request(
                TOKEN_URL,
                data=json.dumps(
                    {"appId": self.app_id, "clientSecret": self.client_secret},
                ).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            raise RuntimeError(f"Failed to get access_token: {e}") from e
        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"No access_token in response: {data}")
        expires_in = data.get("expires_in", 7200)
        if isinstance(expires_in, str):
            expires_in = int(expires_in)
        with self._token_lock:
            self._token_cache = {
                "token": token,
                "expires_at": time.time() + expires_in,
            }
        return token

    async def _get_access_token_async(self) -> str:
        """Async get token for send. Instance-level cache."""
        with self._token_lock:
            if (
                self._token_cache
                and time.time() < self._token_cache["expires_at"] - 300
            ):
                return self._token_cache["token"]
        async with self._http.post(
            TOKEN_URL,
            json={"appId": self.app_id, "clientSecret": self.client_secret},
            headers={"Content-Type": "application/json"},
        ) as resp:
            if resp.status >= 400:
                text = await resp.text()
                raise RuntimeError(
                    f"Token request failed {resp.status}: {text}",
                )
            data = await resp.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"No access_token: {data}")
        expires_in = data.get("expires_in", 7200)
        if isinstance(expires_in, str):
            expires_in = int(expires_in)
        with self._token_lock:
            self._token_cache = {
                "token": token,
                "expires_at": time.time() + expires_in,
            }
        return token

    def _clear_token_cache(self) -> None:
        with self._token_lock:
            self._token_cache = None

    def _download_attachment_sync(
        self,
        attachment: Dict[str, Any],
        *,
        message_id: str,
        attachment_index: int,
    ) -> str | None:
        kind, name, _mime_type, url = _guess_attachment_kind(attachment)
        if kind not in {"image", "pdf"} or not url:
            return None

        try:
            import urllib.request

            safe_stem = _SAFE_FILE_SEGMENT_RE.sub("-", Path(name).stem).strip("-._")
            if not safe_stem:
                safe_stem = "attachment"
            suffix = Path(name).suffix.lower()
            if kind == "image" and suffix not in _IMAGE_EXTENSIONS:
                guessed_suffix = (
                    mimetypes.guess_extension(_mime_type) if _mime_type else None
                )
                suffix = guessed_suffix.lower() if guessed_suffix else ".png"
            if kind == "pdf":
                suffix = ".pdf"
            if not suffix:
                suffix = ".bin"

            target = self._media_dir / (
                f"{message_id}_{attachment_index}_{safe_stem[:64]}{suffix}"
            )
            headers: Dict[str, str] = {}
            api_base = _get_api_base()
            if url.startswith(api_base):
                headers["Authorization"] = (
                    f"QQBot {self._get_access_token_sync()}"
                )

            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            if not data:
                return None

            target.write_bytes(data)
            return str(target)
        except Exception:
            logger.exception(
                "qq attachment download failed: msg_id=%s name=%s url=%s",
                message_id,
                name,
                url,
            )
            return None

    def _build_incoming_content_parts(
        self,
        *,
        text: str,
        attachments: List[Dict[str, Any]],
        message_id: str,
    ) -> List[Any]:
        parts: List[Any] = []
        clean_text = text.strip()
        if clean_text:
            parts.append(
                TextContent(
                    type=ContentType.TEXT,
                    text=clean_text,
                ),
            )

        for idx, attachment in enumerate(attachments):
            if not isinstance(attachment, dict):
                continue

            kind, name, _mime_type, _url = _guess_attachment_kind(attachment)
            if kind not in {"image", "pdf"}:
                continue

            local_path = self._download_attachment_sync(
                attachment,
                message_id=message_id,
                attachment_index=idx,
            )
            if not local_path:
                parts.append(
                    TextContent(
                        type=ContentType.TEXT,
                        text=f"[{kind}: download failed - {name}]",
                    ),
                )
                continue

            if kind == "image":
                parts.append(
                    ImageContent(
                        type=ContentType.IMAGE,
                        image_url=local_path,
                    ),
                )
            else:
                parts.append(
                    FileContent(
                        type=ContentType.FILE,
                        file_url=local_path,
                    ),
                )

        return parts

    @classmethod
    def from_env(
        cls,
        process: ProcessHandler,
        on_reply_sent: OnReplySent = None,
    ) -> "QQChannel":
        return cls(
            process=process,
            enabled=os.getenv("QQ_CHANNEL_ENABLED", "1") == "1",
            app_id=os.getenv("QQ_APP_ID", ""),
            client_secret=os.getenv("QQ_CLIENT_SECRET", ""),
            bot_prefix=os.getenv("QQ_BOT_PREFIX", ""),
            on_reply_sent=on_reply_sent,
        )

    @classmethod
    def from_config(
        cls,
        process: ProcessHandler,
        config: Any,
        on_reply_sent: OnReplySent = None,
        show_tool_details: bool = True,
        filter_tool_messages: bool = False,
    ) -> "QQChannel":
        return cls(
            process=process,
            enabled=getattr(config, "enabled", False),
            app_id=getattr(config, "app_id", "") or "",
            client_secret=getattr(config, "client_secret", "") or "",
            bot_prefix=getattr(config, "bot_prefix", "") or "",
            on_reply_sent=on_reply_sent,
            show_tool_details=show_tool_details,
            filter_tool_messages=filter_tool_messages,
        )

    def resolve_session_id(
        self,
        sender_id: str,
        channel_meta: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Scope sessions by QQ chat target instead of sender only."""
        meta = channel_meta or {}
        message_type = str(meta.get("message_type") or "c2c").strip().lower()
        group_openid = str(meta.get("group_openid") or "").strip()
        channel_id = str(meta.get("channel_id") or "").strip()
        if message_type == "group" and group_openid:
            return f"{self.channel}:group:{group_openid}"
        if message_type in {"guild", "dm"} and channel_id:
            return f"{self.channel}:channel:{channel_id}"
        if sender_id:
            return f"{self.channel}:c2c:{sender_id}"
        return f"{self.channel}:{sender_id}"

    @staticmethod
    def _to_handle_from_session_id(session_id: str) -> str:
        s = (session_id or "").strip()
        parts = s.split(":", 2)
        if len(parts) == 3 and parts[0] == "qq":
            kind, ident = parts[1], parts[2]
            if kind == "group":
                return f"group:{ident}"
            if kind == "channel":
                return f"channel:{ident}"
            if kind == "c2c":
                return ident
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

    def to_handle_from_target(self, *, user_id: str, session_id: str) -> str:
        routed = self._to_handle_from_session_id(session_id)
        if routed:
            return routed
        return user_id

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
            logger.debug("qq set channel_meta failed", exc_info=True)
        return request

    async def send(
        self,
        to_handle: str,
        text: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send one text via QQ HTTP API.
        Routes by meta or to_handle (group:/channel:/openid).
        """
        if not self.enabled or not text.strip():
            return
        text = text.strip()
        text, had_url = _sanitize_qq_text(text)
        if had_url:
            logger.info("qq send: stripped URL content for API compatibility")
        meta = meta or {}
        message_type = meta.get("message_type")
        msg_id = meta.get("message_id")
        sender_id = meta.get("sender_id") or to_handle
        channel_id = meta.get("channel_id")
        group_openid = meta.get("group_openid")
        if message_type is None:
            if to_handle.startswith("group:"):
                message_type = "group"
                group_openid = to_handle[6:]
            elif to_handle.startswith("channel:"):
                message_type = "guild"
                channel_id = to_handle[8:]
            else:
                message_type = "c2c"
        try:
            token = await self._get_access_token_async()
        except Exception:
            logger.exception("get access_token failed")
            return
        try:
            if message_type == "c2c":
                await _send_c2c_message_async(
                    self._http,
                    token,
                    sender_id,
                    text,
                    msg_id,
                )
            elif message_type == "group" and group_openid:
                await _send_group_message_async(
                    self._http,
                    token,
                    group_openid,
                    text,
                    msg_id,
                )
            elif channel_id:
                await _send_channel_message_async(
                    self._http,
                    token,
                    channel_id,
                    text,
                    msg_id,
                )
            else:
                await _send_c2c_message_async(
                    self._http,
                    token,
                    sender_id,
                    text,
                    msg_id,
                )
        except Exception:
            logger.exception("send failed")

    def build_agent_request_from_native(self, native_payload: Any) -> Any:
        """Build AgentRequest from QQ native dict (runtime content_parts)."""
        payload = native_payload if isinstance(native_payload, dict) else {}
        channel_id = payload.get("channel_id") or self.channel
        sender_id = payload.get("sender_id") or ""
        content_parts = payload.get("content_parts") or []
        meta = payload.get("meta") or {}
        session_id = self.resolve_session_id(sender_id, meta)
        request = self.build_agent_request_from_user_content(
            channel_id=channel_id,
            sender_id=sender_id,
            session_id=session_id,
            content_parts=content_parts,
            channel_meta=meta,
        )
        return self._set_request_channel_meta(request, meta)

    @staticmethod
    def _is_user_text_part(item: Any) -> bool:
        text = str(getattr(item, "text", "") or "").strip()
        if not text:
            return False
        lowered = text.lower()
        if lowered.startswith("[image: download failed"):
            return False
        if lowered.startswith("[pdf: download failed"):
            return False
        return True

    def _content_has_text(self, contents: List[Any]) -> bool:
        """QQ only triggers a model turn when the user sends actual text.

        Pure image/file messages are buffered and merged into the next
        text-bearing user message for the same session.
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

    async def consume_one(self, payload: Any) -> None:
        """Process one AgentRequest from manager queue."""
        request = payload
        req_input = (
            request.get("input")
            if isinstance(request, dict)
            else getattr(request, "input", None)
        )
        if req_input:
            first_msg = req_input[0] if isinstance(req_input, list) else req_input
            session_id = (
                request.get("session_id", "")
                if isinstance(request, dict)
                else getattr(request, "session_id", "")
            ) or ""
            contents = list(
                (
                    first_msg.get("content")
                    if isinstance(first_msg, dict)
                    else getattr(first_msg, "content", None)
                )
                or [],
            )
            should_process, merged = self._apply_no_text_debounce(
                session_id,
                contents,
            )
            if not should_process:
                return
            if merged:
                if isinstance(first_msg, dict):
                    first_msg["content"] = merged
                elif hasattr(first_msg, "model_copy"):
                    new_msg = first_msg.model_copy(
                        update={"content": merged},
                    )
                    if isinstance(req_input, list):
                        req_input[0] = new_msg
                    else:
                        req_input = new_msg
                else:
                    first_msg.content = merged
        try:
            send_meta = (
                request.get("channel_meta")
                if isinstance(request, dict)
                else getattr(request, "channel_meta", None)
            ) or {}
            send_meta.setdefault("bot_prefix", self.bot_prefix)
            to_handle = (
                request.get("user_id", "")
                if isinstance(request, dict)
                else getattr(request, "user_id", "")
            ) or ""
            last_response = None
            accumulated_parts: List[OutgoingContentPart] = []
            event_count = 0

            async for event in self._process(request):
                event_count += 1
                obj = getattr(event, "object", None)
                status = getattr(event, "status", None)
                ev_type = getattr(event, "type", None)
                logger.debug(
                    "qq event #%s: object=%s status=%s type=%s",
                    event_count,
                    obj,
                    status,
                    ev_type,
                )
                if obj == "message" and status == RunStatus.Completed:
                    parts = self._message_to_content_parts(event)
                    logger.info(
                        "qq completed message: type=%s parts_count=%s",
                        ev_type,
                        len(parts),
                    )
                    accumulated_parts.extend(parts)
                elif obj == "response":
                    last_response = event

            err_obj = (
                getattr(last_response, "error", None)
                if last_response is not None
                else None
            )
            if err_obj:
                err_msg = getattr(err_obj, "message", str(err_obj))
                err_text = self.bot_prefix + f"Error: {err_msg}"
                await self.send_content_parts(
                    to_handle,
                    [{"type": "text", "text": err_text}],
                    send_meta,
                )
            elif accumulated_parts:
                await self.send_content_parts(
                    to_handle,
                    accumulated_parts,
                    send_meta,
                )
            elif last_response is None:
                await self.send_content_parts(
                    to_handle,
                    [
                        {
                            "type": "text",
                            "text": self.bot_prefix
                            + "An error occurred while processing your "
                            "request.",
                        },
                    ],
                    send_meta,
                )
            if self._on_reply_sent:
                args = self.get_on_reply_sent_args(request, to_handle)
                self._on_reply_sent(self.channel, *args)
        except Exception as e:
            logger.exception("qq process/reply failed")
            err_msg = str(e).strip() or "An error occurred while processing."
            try:
                fallback_handle = (
                    request.get("user_id", "")
                    if isinstance(request, dict)
                    else getattr(request, "user_id", "")
                )
                await self.send_content_parts(
                    fallback_handle,
                    [{"type": "text", "text": f"Error: {err_msg}"}],
                    (
                        request.get("channel_meta")
                        if isinstance(request, dict)
                        else getattr(request, "channel_meta", None)
                    )
                    or {},
                )
            except Exception:
                logger.exception("send error message failed")

    def _run_ws_forever(self) -> None:
        try:
            import websocket
        except ImportError:
            logger.error(
                "websocket-client not installed. pip install websocket-client",
            )
            return
        reconnect_attempts = 0
        last_connect_time = 0.0
        quick_disconnect_count = 0
        session_id: Optional[str] = None
        last_seq: Optional[int] = None
        identify_fail_count = 0
        should_refresh_token = False

        def connect() -> bool:
            nonlocal session_id, last_seq, reconnect_attempts, last_connect_time, quick_disconnect_count, should_refresh_token, identify_fail_count  # pylint: disable=line-too-long # noqa: E501
            if self._stop_event.is_set():
                return False
            if should_refresh_token:
                self._clear_token_cache()
                should_refresh_token = False
            try:
                token = self._get_access_token_sync()
                url = _get_channel_url_sync(token)
            except Exception as e:
                logger.warning("qq get token/gateway failed: %s", e)
                return True
            logger.info("qq connecting to %s", url)
            try:
                ws = websocket.create_connection(url)
            except Exception as e:
                logger.warning("qq ws connect failed: %s", e)
                return True
            current_ws = ws
            heartbeat_interval: Optional[float] = None
            heartbeat_timer: Optional[threading.Timer] = None

            def stop_heartbeat() -> None:
                if heartbeat_timer:
                    heartbeat_timer.cancel()

            def schedule_heartbeat() -> None:
                nonlocal heartbeat_timer
                if heartbeat_interval is None or self._stop_event.is_set():
                    return

                def send_ping() -> None:
                    if self._stop_event.is_set():
                        return
                    try:
                        if current_ws.connected:
                            current_ws.send(
                                json.dumps(
                                    {"op": OP_HEARTBEAT, "d": last_seq},
                                ),
                            )
                            logger.debug("qq heartbeat sent")
                    except Exception:
                        pass
                    schedule_heartbeat()

                heartbeat_timer = threading.Timer(
                    heartbeat_interval / 1000.0,
                    send_ping,
                )
                heartbeat_timer.daemon = True
                heartbeat_timer.start()

            try:
                while not self._stop_event.is_set():
                    raw = current_ws.recv()
                    if not raw:
                        break
                    payload = json.loads(raw)
                    op = payload.get("op")
                    d = payload.get("d")
                    s = payload.get("s")
                    t = payload.get("t")
                    if s is not None:
                        last_seq = s

                    if op == OP_HELLO:
                        hi = d or {}
                        heartbeat_interval = hi.get(
                            "heartbeat_interval",
                            45000,
                        )
                        if session_id and last_seq is not None:
                            current_ws.send(
                                json.dumps(
                                    {
                                        "op": OP_RESUME,
                                        "d": {
                                            "token": f"QQBot {token}",
                                            "session_id": session_id,
                                            "seq": last_seq,
                                        },
                                    },
                                ),
                            )
                        else:
                            intents = (
                                INTENT_PUBLIC_GUILD_MESSAGES
                                | INTENT_GUILD_MEMBERS
                            )
                            if identify_fail_count < 3:
                                intents |= (
                                    INTENT_DIRECT_MESSAGE
                                    | INTENT_GROUP_AND_C2C
                                )
                            current_ws.send(
                                json.dumps(
                                    {
                                        "op": OP_IDENTIFY,
                                        "d": {
                                            "token": f"QQBot {token}",
                                            "intents": intents,
                                            "shard": [0, 1],
                                        },
                                    },
                                ),
                            )
                        schedule_heartbeat()
                    elif op == OP_DISPATCH:
                        if t == "READY":
                            session_id = (d or {}).get("session_id")
                            identify_fail_count = 0
                            reconnect_attempts = 0
                            last_connect_time = time.time()
                            logger.info("qq ready session_id=%s", session_id)
                        elif t == "RESUMED":
                            logger.info("qq session resumed")
                        elif t == "C2C_MESSAGE_CREATE":
                            author = (d or {}).get("author") or {}
                            text = ((d or {}).get("content") or "").strip()
                            if not text and not (d or {}).get("attachments"):
                                continue
                            if self.bot_prefix and text.startswith(
                                self.bot_prefix,
                            ):
                                continue
                            sender = (
                                author.get("user_openid")
                                or author.get("id")
                                or ""
                            )
                            if not sender:
                                continue
                            msg_id = (d or {}).get("id", "")
                            # ts = (d or {}).get("timestamp", "")
                            att = (d or {}).get("attachments") or []
                            content_parts = self._build_incoming_content_parts(
                                text=text,
                                attachments=att,
                                message_id=msg_id or "c2c",
                            )
                            if not content_parts:
                                continue
                            meta = {
                                "message_type": "c2c",
                                "message_id": msg_id,
                                "sender_id": sender,
                                "incoming_raw": d,
                                "attachments": att,
                            }
                            native = {
                                "channel_id": "qq",
                                "sender_id": sender,
                                "content_parts": content_parts,
                                "meta": meta,
                            }
                            request = self.build_agent_request_from_native(
                                native,
                            )
                            if self._enqueue is not None:
                                self._enqueue(request)
                            logger.info(
                                "qq recv c2c from=%s text=%r",
                                sender,
                                text[:100],
                            )
                        elif t == "AT_MESSAGE_CREATE":
                            author = (d or {}).get("author") or {}
                            text = ((d or {}).get("content") or "").strip()
                            if not text and not (d or {}).get("attachments"):
                                continue
                            if self.bot_prefix and text.startswith(
                                self.bot_prefix,
                            ):
                                continue
                            sender = (
                                author.get("id")
                                or author.get("username")
                                or ""
                            )
                            if not sender:
                                continue
                            channel_id = (d or {}).get("channel_id", "")
                            guild_id = (d or {}).get("guild_id", "")
                            msg_id = (d or {}).get("id", "")
                            # ts = (d or {}).get("timestamp", "")
                            att = (d or {}).get("attachments") or []
                            content_parts = self._build_incoming_content_parts(
                                text=text,
                                attachments=att,
                                message_id=msg_id or "guild",
                            )
                            if not content_parts:
                                continue
                            meta = {
                                "message_type": "guild",
                                "message_id": msg_id,
                                "sender_id": sender,
                                "channel_id": channel_id,
                                "guild_id": guild_id,
                                "incoming_raw": d,
                                "attachments": att,
                            }
                            native = {
                                "channel_id": "qq",
                                "sender_id": sender,
                                "content_parts": content_parts,
                                "meta": meta,
                            }
                            request = self.build_agent_request_from_native(
                                native,
                            )
                            if self._enqueue is not None:
                                self._enqueue(request)
                            logger.info(
                                "qq recv guild from=%s channel=%s text=%r",
                                sender,
                                channel_id,
                                text[:100],
                            )
                        elif t == "DIRECT_MESSAGE_CREATE":
                            author = (d or {}).get("author") or {}
                            text = ((d or {}).get("content") or "").strip()
                            if not text and not (d or {}).get("attachments"):
                                continue
                            if self.bot_prefix and text.startswith(
                                self.bot_prefix,
                            ):
                                continue
                            sender = (
                                author.get("id")
                                or author.get("username")
                                or ""
                            )
                            if not sender:
                                continue
                            channel_id = (d or {}).get("channel_id", "")
                            guild_id = (d or {}).get("guild_id", "")
                            msg_id = (d or {}).get("id", "")
                            att = (d or {}).get("attachments") or []
                            content_parts = self._build_incoming_content_parts(
                                text=text,
                                attachments=att,
                                message_id=msg_id or "dm",
                            )
                            if not content_parts:
                                continue
                            meta = {
                                "message_type": "dm",
                                "message_id": msg_id,
                                "sender_id": sender,
                                "channel_id": channel_id,
                                "guild_id": guild_id,
                                "incoming_raw": d,
                                "attachments": att,
                            }
                            native = {
                                "channel_id": "qq",
                                "sender_id": sender,
                                "content_parts": content_parts,
                                "meta": meta,
                            }
                            request = self.build_agent_request_from_native(
                                native,
                            )
                            if self._enqueue is not None:
                                self._enqueue(request)
                            logger.info(
                                "qq recv dm from=%s text=%r",
                                sender,
                                text[:100],
                            )
                        elif t == "GROUP_AT_MESSAGE_CREATE":
                            author = (d or {}).get("author") or {}
                            text = ((d or {}).get("content") or "").strip()
                            if not text and not (d or {}).get("attachments"):
                                continue
                            if self.bot_prefix and text.startswith(
                                self.bot_prefix,
                            ):
                                continue
                            sender = (
                                author.get("member_openid")
                                or author.get("id")
                                or ""
                            )
                            if not sender:
                                continue
                            group_openid = (d or {}).get("group_openid", "")
                            msg_id = (d or {}).get("id", "")
                            att = (d or {}).get("attachments") or []
                            content_parts = self._build_incoming_content_parts(
                                text=text,
                                attachments=att,
                                message_id=msg_id or "group",
                            )
                            if not content_parts:
                                continue
                            meta = {
                                "message_type": "group",
                                "message_id": msg_id,
                                "sender_id": sender,
                                "group_openid": group_openid,
                                "incoming_raw": d,
                                "attachments": att,
                            }
                            native = {
                                "channel_id": "qq",
                                "sender_id": sender,
                                "content_parts": content_parts,
                                "meta": meta,
                            }
                            request = self.build_agent_request_from_native(
                                native,
                            )
                            if self._enqueue is not None:
                                self._enqueue(request)
                            logger.info(
                                "qq recv group from=%s group=%s text=%r",
                                sender,
                                group_openid,
                                text[:100],
                            )
                    elif op == OP_HEARTBEAT_ACK:
                        logger.debug("qq heartbeat ack")
                    elif op == OP_RECONNECT:
                        logger.info("qq server requested reconnect")
                        break
                    elif op == OP_INVALID_SESSION:
                        can_resume = d
                        logger.error(
                            "qq invalid session can_resume=%s",
                            can_resume,
                        )
                        if not can_resume:
                            session_id = None
                            last_seq = None
                            identify_fail_count += 1
                            should_refresh_token = True
                        break
            except websocket.WebSocketConnectionClosedException:
                pass
            except Exception as e:
                logger.exception("qq ws loop: %s", e)
            finally:
                stop_heartbeat()
                try:
                    current_ws.close()
                except Exception:
                    pass
            last_connect_time_val = last_connect_time
            if (
                last_connect_time_val
                and (time.time() - last_connect_time_val)
                < QUICK_DISCONNECT_THRESHOLD
            ):
                quick_disconnect_count += 1
                if quick_disconnect_count >= MAX_QUICK_DISCONNECT_COUNT:
                    session_id = None
                    last_seq = None
                    should_refresh_token = True
                    quick_disconnect_count = 0
                    reconnect_attempts = min(
                        reconnect_attempts,
                        len(RECONNECT_DELAYS) - 1,
                    )
                    delay = RATE_LIMIT_DELAY
                else:
                    delay = RECONNECT_DELAYS[
                        min(reconnect_attempts, len(RECONNECT_DELAYS) - 1)
                    ]
            else:
                quick_disconnect_count = 0
                delay = RECONNECT_DELAYS[
                    min(reconnect_attempts, len(RECONNECT_DELAYS) - 1)
                ]
            reconnect_attempts += 1
            if reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
                logger.error("qq max reconnect attempts reached")
                return False
            logger.info(
                "qq reconnecting in %ss (attempt %s)",
                delay,
                reconnect_attempts,
            )
            self._stop_event.wait(timeout=delay)
            return not self._stop_event.is_set()

        while connect():
            pass
        self._stop_event.set()
        logger.info("qq ws thread stopped")

    async def start(self) -> None:
        if not self.enabled:
            logger.debug("qq channel disabled by QQ_CHANNEL_ENABLED=0")
            return
        if aiohttp is None:
            logger.warning(
                "qq dependency missing: aiohttp. Install with: pip install aiohttp",
            )
            return
        if not self.app_id or not self.client_secret:
            raise RuntimeError(
                "QQ_APP_ID and QQ_CLIENT_SECRET are required when "
                "channel is enabled.",
            )
        self._loop = asyncio.get_running_loop()
        self._stop_event.clear()
        self._ws_thread = threading.Thread(
            target=self._run_ws_forever,
            daemon=True,
        )
        self._ws_thread.start()
        if self._http is None:
            self._http = aiohttp.ClientSession()

    async def stop(self) -> None:
        if not self.enabled:
            return
        self._stop_event.set()
        if self._ws_thread:
            self._ws_thread.join(timeout=8)
        if self._http is not None:
            await self._http.close()
            self._http = None
