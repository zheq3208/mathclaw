"""AgentRunnerManager 鈥?top-level manager for the agent runner lifecycle."""

from __future__ import annotations

import json
import logging
import mimetypes
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import unquote, urlparse

from researchclaw.app.runner.runner import AgentRunner
from researchclaw.app.runner.session import ChatSession, SessionManager
from researchclaw.app.channels.schema import DEFAULT_CHANNEL
from researchclaw.constant import WORKING_DIR

logger = logging.getLogger(__name__)


class AgentRunnerManager:
    """Coordinates agent runner and session management.

    Used in the FastAPI lifespan to start/stop the agent, and provides
    a unified interface for chat operations.
    """

    def __init__(self):
        self.runner = AgentRunner()
        self.session_manager = SessionManager()
        self._model_config: dict[str, Any] = {}
        self._chat_manager: Any = None

    @property
    def is_running(self) -> bool:
        return self.runner.is_running

    @property
    def agent(self):
        return self.runner.agent

    def set_chat_manager(self, chat_manager: Any) -> None:
        self._chat_manager = chat_manager

    def set_mcp_manager(self, mcp_manager: Any) -> None:
        self.runner.set_mcp_manager(mcp_manager)

    async def refresh_mcp_clients(self, force: bool = False) -> None:
        await self.runner.refresh_mcp_clients(force=force)

    @staticmethod
    def _extract_value(obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    @staticmethod
    def _normalize_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return str(value)

    @staticmethod
    def _normalize_attachments(
        attachments: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(attachments, list):
            return []

        normalized: list[dict[str, Any]] = []
        for item in attachments:
            if not isinstance(item, dict):
                continue

            kind = str(item.get("kind", "")).strip().lower()
            if kind not in ("image", "pdf"):
                continue

            name = str(item.get("name", "")).strip()
            abs_path = str(item.get("absolute_path", "")).strip()
            rel_path = str(item.get("relative_path", "")).strip()
            download_url = str(item.get("download_url", "")).strip()
            if not name or not abs_path or not rel_path:
                continue

            normalized.append(
                {
                    "name": name,
                    "kind": kind,
                    "mime_type": str(item.get("mime_type", "")).strip(),
                    "size": int(item.get("size", 0) or 0),
                    "absolute_path": abs_path,
                    "relative_path": rel_path,
                    "download_url": download_url,
                },
            )

        return normalized

    def _get_or_create_session(
        self,
        session_id: str | None,
    ) -> ChatSession:
        if session_id:
            existing = self.session_manager.get_session(session_id)
            if existing:
                return existing
            session = ChatSession(session_id=session_id)
            self.session_manager._sessions[session_id] = session
            self.session_manager._save_session(session)
            return session
        return self.session_manager.create_session()

    def _request_to_prompt(self, request: Any) -> str:
        """Flatten request.input[0].content into one textual prompt."""
        inp = self._extract_value(request, "input", []) or []
        if not inp:
            return ""
        first_msg = inp[0] if isinstance(inp, list) else inp
        contents = self._extract_value(first_msg, "content", []) or []
        if not isinstance(contents, list):
            contents = [contents]

        out: list[str] = []
        for item in contents:
            if isinstance(item, str):
                s = item.strip()
                if s:
                    out.append(s)
                continue

            t = self._extract_value(item, "type", "")
            t_val = (
                t.value if hasattr(t, "value") else str(t) if t else ""
            ).lower()
            if t_val == "text":
                txt = self._normalize_text(
                    self._extract_value(item, "text", ""),
                ).strip()
                if txt:
                    out.append(txt)
                continue
            if t_val == "refusal":
                txt = self._normalize_text(
                    self._extract_value(item, "refusal", ""),
                ).strip()
                if txt:
                    out.append(txt)
                continue

            txt = self._normalize_text(
                self._extract_value(item, "text", ""),
            ).strip()
            if txt:
                out.append(txt)

        return "\n".join(out).strip()

    @staticmethod
    def _local_path_from_ref(value: Any) -> Path | None:
        ref = str(value or "").strip()
        if not ref:
            return None

        parsed = urlparse(ref)
        if parsed.scheme == "file":
            candidate = Path(unquote(parsed.path))
        elif parsed.scheme in {"http", "https"}:
            return None
        else:
            candidate = Path(ref)

        try:
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()
        except OSError:
            return None
        return None

    @staticmethod
    def _attachment_kind_for_path(path: Path) -> tuple[str, str]:
        mime_type = (mimetypes.guess_type(path.name)[0] or "").lower()
        suffix = path.suffix.lower()
        if mime_type.startswith("image/"):
            return ("image", mime_type)
        if mime_type == "application/pdf" or suffix == ".pdf":
            return ("pdf", "application/pdf")
        return ("", mime_type)

    def _attachment_from_content_part(self, item: Any) -> dict[str, Any] | None:
        t = self._extract_value(item, "type", "")
        t_val = (
            t.value if hasattr(t, "value") else str(t) if t else ""
        ).lower()
        source_ref = ""
        kind = ""
        mime_type = ""

        if t_val == "image":
            source_ref = self._normalize_text(
                self._extract_value(item, "image_url", ""),
            ).strip()
            kind = "image"
        elif t_val == "file":
            source_ref = self._normalize_text(
                self._extract_value(
                    item,
                    "file_url",
                    self._extract_value(item, "file_id", ""),
                ),
            ).strip()
        else:
            return None

        path = self._local_path_from_ref(source_ref)
        if path is None:
            return None

        if not kind:
            kind, mime_type = self._attachment_kind_for_path(path)
            if not kind:
                return None
        else:
            mime_type = (mimetypes.guess_type(path.name)[0] or "").lower()

        try:
            relative_path = path.relative_to(Path(WORKING_DIR)).as_posix()
        except ValueError:
            relative_path = path.name

        return {
            "name": path.name,
            "kind": kind,
            "mime_type": mime_type,
            "size": int(path.stat().st_size),
            "absolute_path": str(path),
            "relative_path": relative_path or path.name,
            "download_url": "",
        }

    def _request_to_attachments(self, request: Any) -> list[dict[str, Any]]:
        inp = self._extract_value(request, "input", []) or []
        if not inp:
            return []
        first_msg = inp[0] if isinstance(inp, list) else inp
        contents = self._extract_value(first_msg, "content", []) or []
        if not isinstance(contents, list):
            contents = [contents]

        attachments: list[dict[str, Any]] = []
        seen_paths: set[str] = set()
        for item in contents:
            attachment = self._attachment_from_content_part(item)
            if not attachment:
                continue
            absolute_path = str(attachment.get("absolute_path", "")).strip()
            if not absolute_path or absolute_path in seen_paths:
                continue
            seen_paths.add(absolute_path)
            attachments.append(attachment)
        return attachments

    @staticmethod
    def _build_message_event(
        *,
        event_type: str,
        content_items: list[dict[str, Any]],
    ) -> Any:
        return SimpleNamespace(
            object="message",
            status="completed",
            type=event_type,
            data=SimpleNamespace(
                content=[SimpleNamespace(**i) for i in content_items],
            ),
        )

    @staticmethod
    def _build_response_event(error_message: str | None = None) -> Any:
        err = (
            SimpleNamespace(message=error_message)
            if error_message
            else None
        )
        return SimpleNamespace(
            object="response",
            status="failed" if error_message else "completed",
            type="response",
            error=err,
        )

    async def start(self):
        """Start the agent runner with persisted config."""
        self._model_config = self._load_model_config()
        if self._model_config.get("model_name") or self._model_config.get(
            "api_key",
        ):
            try:
                await self.runner.start(self._model_config)
            except Exception:
                logger.warning(
                    "Failed to auto-start agent. "
                    "Configure model via CLI or API and restart.",
                )
        else:
            logger.info(
                "No model configured. Use 'researchclaw init' or the "
                "API to set up a model before chatting.",
            )

    async def stop(self):
        """Stop the agent runner."""
        await self.runner.stop()

    async def chat(
        self,
        message: str,
        session_id: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> str:
        """Send a chat message, creating a session if needed."""
        if not self.runner.is_running:
            # Try to start with current config
            await self.start()
            if not self.runner.is_running:
                return (
                    "Scholar is not ready. Please configure your LLM provider first.\n"
                    "Run `researchclaw init` or set up via Settings."
                )

        session = self._get_or_create_session(session_id)
        normalized_attachments = self._normalize_attachments(attachments)
        user_metadata = (
            {"attachments": normalized_attachments}
            if normalized_attachments
            else None
        )
        session.add_message("user", message, metadata=user_metadata)
        response = await self.runner.chat(
            message,
            session.session_id,
            attachments=normalized_attachments,
        )
        session.add_message("assistant", response)
        self.session_manager._save_session(session)

        return response

    async def chat_stream(
        self,
        message: str,
        session_id: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ):
        """Stream a chat response, yielding SSE event dicts."""
        if not self.runner.is_running:
            await self.start()
            if not self.runner.is_running:
                yield {
                    "type": "error",
                    "content": (
                        "Scholar is not ready. Please configure your LLM "
                        "provider first.\nRun `researchclaw init` or set "
                        "up via Settings."
                    ),
                }
                return

        session = self._get_or_create_session(session_id)
        normalized_attachments = self._normalize_attachments(attachments)
        user_metadata = (
            {"attachments": normalized_attachments}
            if normalized_attachments
            else None
        )
        session.add_message("user", message, metadata=user_metadata)
        full_content = ""

        async for event in self.runner.chat_stream(
            message,
            session.session_id,
            attachments=normalized_attachments,
        ):
            if event.get("type") == "done":
                full_content = event.get("content", full_content)
            yield event

        if full_content:
            session.add_message("assistant", full_content)
            self.session_manager._save_session(session)

    async def stream_query(self, request: Any):
        """CoPaw-compatible process adapter for channel manager.

        Accepts a channel-built request and yields Event-like objects with
        ``object/status/type`` fields expected by channel renderers.
        """
        session_id = self._extract_value(request, "session_id", None)
        user_id = self._normalize_text(
            self._extract_value(request, "user_id", ""),
        ).strip() or "main"
        channel = self._normalize_text(
            self._extract_value(request, "channel", DEFAULT_CHANNEL),
        ).strip() or DEFAULT_CHANNEL
        prompt = self._request_to_prompt(request)
        attachments = self._request_to_attachments(request)
        if not prompt:
            prompt = self._normalize_text(
                self._extract_value(request, "message", ""),
            )

        content_chunks: list[str] = []
        chat_spec = None
        if self._chat_manager and session_id:
            try:
                chat_spec = await self._chat_manager.get_or_create_chat(
                    session_id=session_id,
                    user_id=user_id,
                    channel=channel,
                    name=(prompt[:50] or "New Chat"),
                )
            except Exception:
                logger.debug(
                    "stream_query: auto-register chat failed",
                    exc_info=True,
                )

        try:
            async for raw_event in self.chat_stream(
                prompt,
                session_id=session_id,
                attachments=attachments,
            ):
                event_type = self._extract_value(raw_event, "type", "")
                if event_type == "thinking":
                    text = self._normalize_text(
                        self._extract_value(raw_event, "content", ""),
                    ).strip()
                    if text:
                        yield self._build_message_event(
                            event_type="thinking",
                            content_items=[
                                {"type": "thinking", "text": text},
                            ],
                        )
                    continue

                if event_type == "tool_call":
                    name = self._normalize_text(
                        self._extract_value(raw_event, "name", "tool"),
                    )
                    args = self._extract_value(raw_event, "arguments", "")
                    yield self._build_message_event(
                        event_type="tool_call",
                        content_items=[
                            {
                                "type": "tool_call",
                                "name": name,
                                "arguments": args,
                            },
                        ],
                    )
                    continue

                if event_type == "tool_result":
                    name = self._normalize_text(
                        self._extract_value(raw_event, "name", ""),
                    )
                    result = self._extract_value(raw_event, "result", "")
                    yield self._build_message_event(
                        event_type="tool_result",
                        content_items=[
                            {
                                "type": "tool_output",
                                "name": name,
                                "output": result,
                            },
                        ],
                    )
                    continue

                if event_type == "content":
                    chunk = self._normalize_text(
                        self._extract_value(raw_event, "content", ""),
                    )
                    if chunk:
                        content_chunks.append(chunk)
                    continue

                if event_type == "error":
                    err = self._normalize_text(
                        self._extract_value(raw_event, "content", ""),
                    ).strip()
                    if content_chunks:
                        yield self._build_message_event(
                            event_type="content",
                            content_items=[
                                {
                                    "type": "text",
                                    "text": "".join(content_chunks),
                                },
                            ],
                        )
                    yield self._build_response_event(
                        error_message=err or "Unknown error",
                    )
                    return

                if event_type == "done":
                    full_text = self._normalize_text(
                        self._extract_value(raw_event, "content", ""),
                    ).strip() or "".join(content_chunks).strip()
                    if full_text:
                        yield self._build_message_event(
                            event_type="content",
                            content_items=[
                                {"type": "text", "text": full_text},
                            ],
                        )
                    yield self._build_response_event()
                    return

                maybe_text = self._normalize_text(
                    self._extract_value(raw_event, "content", ""),
                )
                if maybe_text:
                    content_chunks.append(maybe_text)

            if content_chunks:
                yield self._build_message_event(
                    event_type="content",
                    content_items=[
                        {"type": "text", "text": "".join(content_chunks)},
                    ],
                )
            yield self._build_response_event()
        except Exception as e:
            yield self._build_response_event(error_message=str(e))
        finally:
            if self._chat_manager and chat_spec is not None:
                try:
                    await self._chat_manager.update_chat(chat_spec)
                except Exception:
                    logger.debug(
                        "stream_query: chat update failed",
                        exc_info=True,
                    )

    async def apply_provider(self, model_config: dict[str, Any]) -> None:
        """Hot-reload the agent with a new provider config."""
        logger.info(
            "Applying new provider config: %s / %s",
            model_config.get("provider"),
            model_config.get("model_name"),
        )
        await self.runner.restart(model_config)
        self._model_config = model_config
        logger.info("Agent restarted with new provider config")

    def _load_model_config(self) -> dict[str, Any]:
        """Load model config from working directory."""
        config_path = Path(WORKING_DIR) / "config.json"
        if not config_path.exists():
            return {}
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            return {}








