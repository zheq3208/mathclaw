"""Agent API routes - chat with ScholarAgent."""

from __future__ import annotations

import base64
import binascii
import json
import logging
import mimetypes
import re
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from mathclaw.constant import (
    DEFAULT_MAX_INPUT_TOKENS,
    DEFAULT_MAX_ITERS,
    WORKING_DIR,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_CHAT_UPLOAD_ROOT = Path(WORKING_DIR) / "uploads" / "chat"
_MAX_ATTACHMENTS_PER_REQUEST = 6
_MAX_ATTACHMENT_SIZE_BYTES = 15 * 1024 * 1024
_SEGMENT_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")
_ALLOWED_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
}


class ChatAttachment(BaseModel):
    """Metadata for an uploaded attachment referenced by chat."""

    name: str
    mime_type: str = ""
    size: int = 0
    kind: str
    absolute_path: str
    relative_path: str
    download_url: str = ""


class ChatRequest(BaseModel):
    """Chat message request body."""

    message: str
    session_id: str | None = None
    stream: bool = False
    attachments: list[ChatAttachment] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """Chat message response."""

    response: str
    session_id: str


class AttachmentUploadFile(BaseModel):
    """One file payload for JSON-based attachment upload."""

    name: str
    mime_type: str = ""
    size: int = 0
    data_base64: str


class AttachmentUploadRequest(BaseModel):
    """Attachment upload request body."""

    session_id: str | None = None
    files: list[AttachmentUploadFile] = Field(default_factory=list)


class AttachmentUploadItem(BaseModel):
    """Uploaded attachment metadata returned to frontend."""

    name: str
    mime_type: str
    size: int
    kind: str
    absolute_path: str
    relative_path: str
    download_url: str


class AttachmentUploadResponse(BaseModel):
    files: list[AttachmentUploadItem] = Field(default_factory=list)


class AgentsRunningConfig(BaseModel):
    """Runtime agent limits shown in console settings."""

    max_iters: int = DEFAULT_MAX_ITERS
    max_input_length: int = DEFAULT_MAX_INPUT_TOKENS


def _upload_root() -> Path:
    _CHAT_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    return _CHAT_UPLOAD_ROOT


def _safe_segment(value: str | None, fallback: str) -> str:
    text = (value or "").strip()
    text = _SEGMENT_SAFE_RE.sub("-", text).strip("-._")
    if not text:
        text = fallback
    return text[:64]


def _infer_attachment_kind(name: str, mime_type: str) -> str | None:
    lower_name = name.lower().strip()
    lower_mime = mime_type.lower().strip()

    if lower_mime.startswith("image/"):
        return "image"
    if Path(lower_name).suffix in _ALLOWED_IMAGE_EXTENSIONS:
        return "image"
    if lower_mime == "application/pdf" or lower_name.endswith(".pdf"):
        return "pdf"
    return None


def _normalized_suffix(name: str, mime_type: str, kind: str) -> str:
    suffix = Path(name).suffix.lower()
    if kind == "pdf":
        return ".pdf"

    if suffix in _ALLOWED_IMAGE_EXTENSIONS:
        return suffix

    guessed = mimetypes.guess_extension(mime_type.lower().strip()) if mime_type else None
    if guessed and guessed.lower() in _ALLOWED_IMAGE_EXTENSIONS:
        return guessed.lower()

    return ".png"


def _decode_upload_payload(data_base64: str, file_name: str) -> bytes:
    payload = data_base64.strip()
    if not payload:
        raise HTTPException(status_code=400, detail=f"File '{file_name}' is empty")

    if payload.startswith("data:"):
        marker = payload.find(",")
        if marker == -1:
            raise HTTPException(
                status_code=400,
                detail=f"File '{file_name}' has invalid data URL format",
            )
        payload = payload[marker + 1 :]

    try:
        return base64.b64decode(payload, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"File '{file_name}' has invalid base64 content",
        ) from exc


def _load_running_config() -> AgentsRunningConfig:
    config_path = Path(WORKING_DIR) / "config.json"
    if not config_path.exists():
        return AgentsRunningConfig()

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return AgentsRunningConfig()

    return AgentsRunningConfig(
        max_iters=int(data.get("max_iters", DEFAULT_MAX_ITERS)),
        max_input_length=int(
            data.get("max_input_length", DEFAULT_MAX_INPUT_TOKENS),
        ),
    )


def _save_running_config(config: AgentsRunningConfig) -> AgentsRunningConfig:
    config_path = Path(WORKING_DIR) / "config.json"
    payload: dict[str, Any] = {}
    if config_path.exists():
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}

    payload.update(config.model_dump())
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return config


@router.post("/attachments", response_model=AttachmentUploadResponse)
async def upload_attachments(payload: AttachmentUploadRequest):
    """Upload image/PDF attachments via JSON (base64 content)."""
    if not payload.files:
        return AttachmentUploadResponse(files=[])

    if len(payload.files) > _MAX_ATTACHMENTS_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"At most {_MAX_ATTACHMENTS_PER_REQUEST} attachments are allowed",
        )

    upload_root = _upload_root()
    session_segment = _safe_segment(payload.session_id, "session")
    batch_segment = _safe_segment(uuid.uuid4().hex[:12], "batch")
    target_dir = upload_root / session_segment / batch_segment
    target_dir.mkdir(parents=True, exist_ok=True)

    uploaded: list[AttachmentUploadItem] = []

    for file in payload.files:
        kind = _infer_attachment_kind(file.name, file.mime_type)
        if kind is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported attachment type: {file.name}",
            )

        raw = _decode_upload_payload(file.data_base64, file.name)
        if not raw:
            raise HTTPException(
                status_code=400,
                detail=f"Attachment '{file.name}' is empty",
            )

        if len(raw) > _MAX_ATTACHMENT_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Attachment '{file.name}' exceeds max size "
                    f"({_MAX_ATTACHMENT_SIZE_BYTES} bytes)"
                ),
            )

        stem = _safe_segment(Path(file.name).stem, "attachment")
        suffix = _normalized_suffix(file.name, file.mime_type, kind)
        final_name = f"{uuid.uuid4().hex[:12]}-{stem}{suffix}"
        file_path = target_dir / final_name
        file_path.write_bytes(raw)

        relative_path = file_path.relative_to(upload_root).as_posix()
        download_url = f"/api/agent/attachments/file?path={quote(relative_path, safe='/')}"

        uploaded.append(
            AttachmentUploadItem(
                name=file.name,
                mime_type=file.mime_type,
                size=len(raw),
                kind=kind,
                absolute_path=str(file_path.resolve()),
                relative_path=relative_path,
                download_url=download_url,
            ),
        )

    return AttachmentUploadResponse(files=uploaded)


@router.get("/attachments/file")
async def get_attachment_file(
    path: str = Query(..., min_length=1),
):
    """Serve a previously uploaded chat attachment by safe relative path."""
    upload_root = _upload_root().resolve()
    clean = path.replace("\\", "/").strip("/")
    target = (upload_root / clean).resolve()

    try:
        target.relative_to(upload_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid attachment path") from exc

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Attachment not found")

    media_type, _ = mimetypes.guess_type(target.name)
    return FileResponse(
        str(target),
        media_type=media_type or "application/octet-stream",
        filename=target.name,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    """Send a message to ScholarAgent and get a response."""
    runner = getattr(req.app.state, "runner", None)
    if not runner:
        return ChatResponse(
            response="Agent is not running. Please check the server logs.",
            session_id=request.session_id or str(uuid.uuid4()),
        )

    session_id = request.session_id or str(uuid.uuid4())
    attachments = [item.model_dump(mode="python") for item in request.attachments]

    try:
        response = await runner.chat(
            message=request.message,
            session_id=session_id,
            attachments=attachments,
        )
        return ChatResponse(response=response, session_id=session_id)
    except Exception as e:
        logger.exception("Chat error")
        return ChatResponse(
            response=f"Error: {e}",
            session_id=session_id,
        )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, req: Request):
    """Stream a response from ScholarAgent via SSE."""
    runner = getattr(req.app.state, "runner", None)
    session_id = request.session_id or str(uuid.uuid4())
    attachments = [item.model_dump(mode="python") for item in request.attachments]

    async def generate():
        if not runner:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Agent not running'})}\n\n"
            return

        try:
            async for event in runner.chat_stream(
                message=request.message,
                session_id=session_id,
                attachments=attachments,
            ):
                event["session_id"] = session_id
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e), 'session_id': session_id})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/tools")
async def list_tools(req: Request):
    """List available agent tools."""
    runner = getattr(req.app.state, "runner", None)
    if not runner or not runner.agent:
        return {"tools": []}
    return {"tools": runner.agent.tool_names}


@router.get("/status")
async def agent_status(req: Request):
    """Get agent status."""
    runner = getattr(req.app.state, "runner", None)
    return {
        "running": runner is not None and runner.is_running,
        "agent_name": "Scholar",
        "tool_count": len(runner.agent.tool_names)
        if runner and runner.agent
        else 0,
    }


@router.get("/running-config", response_model=AgentsRunningConfig)
async def get_running_config():
    """Get persisted runtime configuration for agent limits."""
    return _load_running_config()


@router.put("/running-config", response_model=AgentsRunningConfig)
async def update_running_config(config: AgentsRunningConfig):
    """Persist runtime configuration for agent limits."""
    return _save_running_config(config)

