"""AgentRunnerManager 鈥?top-level manager for the agent runner lifecycle."""

from __future__ import annotations

import json
import logging
import mimetypes
import re
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import unquote, urlparse

from mathclaw.app.runner.runner import AgentRunner
from mathclaw.app.runner.session import ChatSession, SessionManager
from mathclaw.app.channels.schema import DEFAULT_CHANNEL
from mathclaw.constant import WORKING_DIR
from mathclaw.config import load_config

logger = logging.getLogger(__name__)


class AgentRunnerManager:
    """Coordinates agent runner and session management.

    Used in the FastAPI lifespan to start/stop the agent, and provides
    a unified interface for chat operations.
    """

    TRACE_FOOTER_TITLE = "[\u8c03\u8bd5\u94fe\u8def]"

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

    @staticmethod
    def _safe_session_slug(session_id: str | None) -> str:
        raw = str(session_id or "main").strip() or "main"
        return re.sub(r"[^A-Za-z0-9._-]+", "_", raw)

    def _trace_dir(self) -> Path:
        path = Path(WORKING_DIR) / "turn_traces"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _runtime_config(self) -> dict[str, Any]:
        if self._model_config:
            return dict(self._model_config)
        return self._load_model_config()

    @staticmethod
    def _has_usable_model_config(model_config: dict[str, Any]) -> bool:
        provider = str(
            model_config.get("provider")
            or model_config.get("model_type")
            or ""
        ).strip().lower()
        model_name = str(model_config.get("model_name") or "").strip()
        api_key = str(model_config.get("api_key") or "").strip()
        if not model_name:
            return False
        if provider in {"ollama", "local", "llamacpp", "mlx"}:
            return True
        return bool(api_key)

    def _debug_skill_footer_enabled(self) -> bool:
        return bool(self._runtime_config().get("debug_skill_footer", False))

    @staticmethod
    def _clone_trace(trace: Any) -> dict[str, Any]:
        if not isinstance(trace, dict):
            return {}
        try:
            return json.loads(json.dumps(trace, ensure_ascii=False))
        except Exception:
            return dict(trace)

    def _collect_turn_trace(self) -> dict[str, Any]:
        agent = getattr(self.runner, "agent", None)
        getter = getattr(agent, "get_last_turn_trace", None)
        if not callable(getter):
            return {}
        try:
            return self._clone_trace(getter())
        except Exception:
            logger.debug("collect turn trace failed", exc_info=True)
            return {}

    def _write_turn_trace(
        self,
        session_id: str | None,
        user_message: str,
        response: str,
        trace: dict[str, Any],
    ) -> str:
        if not trace:
            return ""
        trace_file = self._trace_dir() / f"{self._safe_session_slug(session_id)}.jsonl"
        payload = {
            "timestamp": time.time(),
            "session_id": session_id or "",
            "user_message": user_message,
            "response": response,
            "trace": trace,
        }
        with trace_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return str(trace_file)

    @staticmethod
    def _trace_string_list(trace: dict[str, Any], key: str) -> list[str]:
        values = trace.get(key, []) if isinstance(trace, dict) else []
        if not isinstance(values, list):
            return []
        out: list[str] = []
        for value in values:
            text = str(value or "").strip()
            if text and text not in out:
                out.append(text)
        return out

    def _format_turn_trace_footer(self, trace: dict[str, Any]) -> str:
        if not trace:
            return ""
        lines = [self.TRACE_FOOTER_TITLE]
        route = self._normalize_text(trace.get("route", "")).strip()
        if route:
            lines.append(f"\u8def\u7531: {route}")
        used_skills = self._trace_string_list(trace, "used_skills")
        selected_skills = self._trace_string_list(trace, "selected_skills")
        if used_skills:
            lines.append(f"\u6280\u80fd: {', '.join(used_skills[:6])}")
        elif selected_skills:
            lines.append(f"\u6280\u80fd(\u5019\u9009): {', '.join(selected_skills[:6])}")
        used_tools = self._trace_string_list(trace, "used_tools")
        if used_tools:
            lines.append(f"\u5de5\u5177: {', '.join(used_tools[:8])}")
        used_mcp = self._trace_string_list(trace, "used_mcp")
        if used_mcp:
            lines.append(f"MCP: {', '.join(used_mcp[:4])}")
        artifacts = self._trace_string_list(trace, "artifacts")
        if artifacts:
            lines.append(f"\u4ea7\u7269: {', '.join(artifacts[:4])}")
        status = self._normalize_text(trace.get("status", "")).strip()
        if status:
            lines.append(f"\u72b6\u6001: {status}")
        if len(lines) == 1:
            return ""
        return "\n".join(lines)

    def _decorate_response_with_trace(
        self,
        response: str,
        trace: dict[str, Any],
    ) -> str:
        base = self._normalize_text(response)
        if not self._debug_skill_footer_enabled():
            return base
        footer = self._format_turn_trace_footer(trace)
        if not footer or self.TRACE_FOOTER_TITLE in base:
            return base
        if not base.strip():
            return footer
        return f"{base.rstrip()}\n\n{footer}"

    def _assistant_trace_metadata(
        self,
        trace: dict[str, Any],
        trace_file: str,
    ) -> dict[str, Any] | None:
        metadata: dict[str, Any] = {}
        cloned = self._clone_trace(trace)
        if cloned:
            metadata["turn_trace"] = cloned
        if trace_file:
            metadata["trace_file"] = trace_file
        return metadata or None

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
        if self._has_usable_model_config(self._model_config):
            try:
                await self.runner.start(self._model_config)
            except Exception:
                logger.warning(
                    "Failed to auto-start agent. "
                    "Configure model via CLI or API and restart.",
                )
        else:
            logger.info(
                "No usable model credentials configured yet. "
                "Use 'mathclaw init' or /api/config/quickstart before chatting.",
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
                    "MathClaw is not ready. Please configure your LLM provider first.\n"
                    "Run `mathclaw init` or set up via Settings."
                )

        session = self._get_or_create_session(session_id)
        normalized_attachments = self._normalize_attachments(attachments)
        user_metadata = (
            {"attachments": normalized_attachments}
            if normalized_attachments
            else None
        )
        session.add_message("user", message, metadata=user_metadata)
        raw_response = await self.runner.chat(
            message,
            session.session_id,
            attachments=normalized_attachments,
        )
        trace = self._collect_turn_trace()
        trace_file = self._write_turn_trace(
            session.session_id,
            message,
            raw_response,
            trace,
        )
        response = self._decorate_response_with_trace(raw_response, trace)
        session.add_message(
            "assistant",
            response,
            metadata=self._assistant_trace_metadata(trace, trace_file),
        )
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
                        "provider first.\nRun `mathclaw init` or set "
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
        trace: dict[str, Any] = {}
        trace_file = ""

        async for event in self.runner.chat_stream(
            message,
            session.session_id,
            attachments=normalized_attachments,
        ):
            if event.get("type") == "done":
                raw_content = event.get("content", full_content)
                trace = self._collect_turn_trace()
                trace_file = self._write_turn_trace(
                    session.session_id,
                    message,
                    raw_content,
                    trace,
                )
                full_content = self._decorate_response_with_trace(raw_content, trace)
                event = dict(event)
                event["content"] = full_content
                stage_messages = event.get("stage_messages")
                if isinstance(stage_messages, list):
                    normalized_stage_messages = [
                        self._normalize_text(item).strip()
                        for item in stage_messages
                        if self._normalize_text(item).strip()
                    ]
                    if normalized_stage_messages:
                        footer = self._format_turn_trace_footer(trace) if self._debug_skill_footer_enabled() else ""
                        if footer and self.TRACE_FOOTER_TITLE not in normalized_stage_messages[-1]:
                            normalized_stage_messages[-1] = f"{normalized_stage_messages[-1].rstrip()}\n\n{footer}"
                        event["stage_messages"] = normalized_stage_messages
            yield event

        if full_content:
            session.add_message(
                "assistant",
                full_content,
                metadata=self._assistant_trace_metadata(trace, trace_file),
            )
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

                if event_type == "stage_message":
                    text = self._normalize_text(
                        self._extract_value(raw_event, "content", ""),
                    ).strip()
                    if text:
                        yield self._build_message_event(
                            event_type="content",
                            content_items=[
                                {"type": "text", "text": text},
                            ],
                        )
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
                    stage_messages = self._extract_value(raw_event, "stage_messages", [])
                    suppress_emit = bool(self._extract_value(raw_event, "suppress_emit", False))
                    if isinstance(stage_messages, list) and stage_messages:
                        for segment in stage_messages:
                            text = self._normalize_text(segment).strip()
                            if not text:
                                continue
                            yield self._build_message_event(
                                event_type="content",
                                content_items=[
                                    {"type": "text", "text": text},
                                ],
                            )
                        yield self._build_response_event()
                        return

                    full_text = self._normalize_text(
                        self._extract_value(raw_event, "content", ""),
                    ).strip() or "".join(content_chunks).strip()
                    if full_text and not suppress_emit:
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
        try:
            return load_config()
        except Exception:
            return {}








