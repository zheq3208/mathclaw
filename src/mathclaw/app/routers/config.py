"""Configuration API routes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from mathclaw.config import (
    build_default_config,
    config_path,
    load_config,
    merge_config,
    save_config,
)
from mathclaw.constant import SECRET_DIR, WORKING_DIR
from mathclaw.providers import ProviderStore

logger = logging.getLogger(__name__)

router = APIRouter()

_LOCAL_PROVIDER_TYPES = {"ollama", "local", "llamacpp", "mlx"}


class QuickstartConfigRequest(BaseModel):
    """One-shot setup payload for the common local deployment path."""

    provider: str = "dashscope"
    provider_name: str | None = None
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model_name: str = "qwen3-vl-plus"
    supports_vision: bool = True
    language: str = "zh-CN"
    show_tool_details: bool = True
    heartbeat_every: str = "30m"
    heartbeat_enabled: bool = False
    heartbeat_target: str = "last"
    enable_tavily: bool = False
    tavily_api_key: str = ""
    enable_playwright: bool = False
    enable_filesystem: bool = False
    qq_enabled: bool = False
    qq_app_id: str = ""
    qq_client_secret: str = ""
    qq_bot_prefix: str = ""
    wecom_enabled: bool = False
    wecom_bot_id: str = ""
    wecom_secret: str = ""
    wecom_bot_prefix: str = ""
    wecom_welcome_message: str = ""


def _clean(value: str | None) -> str:
    return str(value or "").strip()


def _resolve_provider_name(payload: QuickstartConfigRequest) -> str:
    provider_name = _clean(payload.provider_name)
    if provider_name:
        return provider_name
    provider = _clean(payload.provider).lower() or "provider"
    return f"{provider}-default"


def _validate_quickstart(payload: QuickstartConfigRequest) -> list[str]:
    errors: list[str] = []
    if payload.qq_enabled:
        if not _clean(payload.qq_app_id):
            errors.append("qq_app_id is required when qq_enabled=true")
        if not _clean(payload.qq_client_secret):
            errors.append("qq_client_secret is required when qq_enabled=true")
    if payload.wecom_enabled:
        if not _clean(payload.wecom_bot_id):
            errors.append("wecom_bot_id is required when wecom_enabled=true")
        if not _clean(payload.wecom_secret):
            errors.append("wecom_secret is required when wecom_enabled=true")
    if payload.enable_tavily and not _clean(payload.tavily_api_key):
        errors.append("tavily_api_key is required when enable_tavily=true")
    return errors


def _can_hot_apply(provider: str, model_name: str, api_key: str) -> bool:
    provider_norm = _clean(provider).lower()
    if not _clean(model_name):
        return False
    if provider_norm in _LOCAL_PROVIDER_TYPES:
        return True
    return bool(_clean(api_key))


def _build_quickstart_update(payload: QuickstartConfigRequest) -> dict[str, Any]:
    defaults = build_default_config()
    tavily_url = "https://mcp.tavily.com/mcp/"
    tavily_key = _clean(payload.tavily_api_key)
    if payload.enable_tavily and tavily_key:
        tavily_url = f"https://mcp.tavily.com/mcp/?tavilyApiKey={tavily_key}"

    return {
        "language": _clean(payload.language) or defaults["language"],
        "show_tool_details": bool(payload.show_tool_details),
        "heartbeat_every": _clean(payload.heartbeat_every) or defaults["heartbeat_every"],
        "provider": _clean(payload.provider) or defaults["provider"],
        "model_name": _clean(payload.model_name) or defaults["model_name"],
        "api_key": _clean(payload.api_key),
        "base_url": _clean(payload.base_url) or defaults["base_url"],
        "supports_vision": bool(payload.supports_vision),
        "extra": {
            "supports_vision": bool(payload.supports_vision),
        },
        "mcp": {
            "clients": {
                "tavily": {
                    "enabled": bool(payload.enable_tavily),
                    "transport": "streamable_http",
                    "url": tavily_url,
                    "headers": {},
                },
                "playwright": {
                    "enabled": bool(payload.enable_playwright),
                },
                "filesystem": {
                    "enabled": bool(payload.enable_filesystem),
                },
            },
        },
        "channels": {
            "qq": {
                "enabled": bool(payload.qq_enabled),
                "app_id": _clean(payload.qq_app_id),
                "client_secret": _clean(payload.qq_client_secret),
                "bot_prefix": _clean(payload.qq_bot_prefix),
            },
            "wecom": {
                "enabled": bool(payload.wecom_enabled),
                "bot_id": _clean(payload.wecom_bot_id),
                "secret": _clean(payload.wecom_secret),
                "bot_prefix": _clean(payload.wecom_bot_prefix),
                "welcome_message": payload.wecom_welcome_message or "",
            },
        },
        "agents": {
            "defaults": {
                "heartbeat": {
                    "enabled": bool(payload.heartbeat_enabled),
                    "every": _clean(payload.heartbeat_every) or defaults["heartbeat_every"],
                    "target": _clean(payload.heartbeat_target) or "last",
                },
            },
        },
    }


def _build_provider_payload(payload: QuickstartConfigRequest) -> dict[str, Any]:
    return {
        "name": _resolve_provider_name(payload),
        "provider_type": _clean(payload.provider) or "dashscope",
        "api_key": _clean(payload.api_key),
        "base_url": _clean(payload.base_url),
        "model_name": _clean(payload.model_name),
        "enabled": _can_hot_apply(payload.provider, payload.model_name, payload.api_key),
        "extra": {
            "supports_vision": bool(payload.supports_vision),
        },
    }


def _config_summary(config: dict[str, Any]) -> dict[str, Any]:
    qq = config.get("channels", {}).get("qq", {})
    wecom = config.get("channels", {}).get("wecom", {})
    tavily = config.get("mcp", {}).get("clients", {}).get("tavily", {})
    return {
        "provider": config.get("provider"),
        "model_name": config.get("model_name"),
        "api_key_set": bool(config.get("api_key")),
        "supports_vision": bool(config.get("supports_vision")),
        "qq_enabled": bool(qq.get("enabled")),
        "qq_app_id_set": bool(qq.get("app_id")),
        "wecom_enabled": bool(wecom.get("enabled")),
        "wecom_bot_id_set": bool(wecom.get("bot_id")),
        "tavily_enabled": bool(tavily.get("enabled")),
        "tavily_api_key_set": "tavilyApiKey=" in str(tavily.get("url") or ""),
    }


@router.get("")
async def get_config():
    """Get current configuration merged with repository defaults."""
    return load_config()


@router.put("")
async def update_config(updates: dict[str, Any]):
    """Update configuration values with deep merge semantics."""
    config = merge_config(load_config(), updates)
    save_config(config)
    return {"status": "ok", "config": config}


@router.get("/template")
async def get_config_template():
    """Expose default values and the recommended quickstart payload schema."""
    return {
        "config_path": str(config_path()),
        "secret_dir": str(Path(SECRET_DIR)),
        "defaults": build_default_config(),
        "quickstart_payload": QuickstartConfigRequest().model_dump(),
        "required_when_enabled": {
            "model": ["api_key"],
            "qq": ["qq_app_id", "qq_client_secret"],
            "wecom": ["wecom_bot_id", "wecom_secret"],
            "tavily": ["tavily_api_key"],
        },
        "notes": [
            "DashScope + qwen3-vl-plus is the default quickstart target.",
            "QQ and WeCom remain disabled until you provide credentials.",
            "Optional MCP clients are disabled by default for a simpler first run.",
        ],
    }


@router.post("/quickstart")
async def configure_quickstart(payload: QuickstartConfigRequest, request: Request):
    """Apply a simple default config and optionally hot-load the model provider."""
    errors = _validate_quickstart(payload)
    if errors:
        raise HTTPException(status_code=400, detail=errors)

    config = merge_config(load_config(), _build_quickstart_update(payload))
    save_config(config)

    store = ProviderStore()
    provider_payload = _build_provider_payload(payload)
    store.save_provider(provider_payload)
    provider_name = provider_payload["name"]
    if provider_payload["enabled"]:
        store.set_enabled(provider_name)

    runner_started = False
    runner_error = ""
    model_config = {
        "provider": config.get("provider", ""),
        "model_name": config.get("model_name", ""),
        "api_key": config.get("api_key", ""),
        "base_url": config.get("base_url", ""),
        "supports_vision": bool(config.get("supports_vision", False)),
        "extra": config.get("extra", {}),
    }
    runner = getattr(request.app.state, "runner", None)
    if runner is not None and _can_hot_apply(
        model_config.get("provider", ""),
        model_config.get("model_name", ""),
        model_config.get("api_key", ""),
    ):
        try:
            await runner.apply_provider(model_config)
            runner_started = True
        except Exception as exc:
            runner_error = str(exc)
            logger.exception("Quickstart provider apply failed")

    missing_required: list[str] = []
    if not _can_hot_apply(payload.provider, payload.model_name, payload.api_key):
        missing_required.append("api_key")

    return {
        "status": "ok",
        "config_path": str(config_path()),
        "provider_store_path": str(store.file_path),
        "provider": provider_name,
        "runner_started": runner_started,
        "runner_error": runner_error,
        "restart_required": bool(
            payload.qq_enabled
            or payload.wecom_enabled
            or payload.enable_tavily
            or payload.enable_playwright
            or payload.enable_filesystem
        ),
        "missing_required": missing_required,
        "summary": _config_summary(config),
    }


@router.get("/working-dir")
async def get_working_dir():
    """Get current working directory info."""
    wd = Path(WORKING_DIR)
    return {
        "path": str(wd),
        "exists": wd.exists(),
        "config_path": str(config_path()),
        "secret_dir": str(Path(SECRET_DIR)),
        "papers_dir": str(wd / "papers"),
        "references_dir": str(wd / "references"),
        "experiments_dir": str(wd / "experiments"),
    }


@router.get("/model")
async def get_model_config():
    """Get current model configuration summary."""
    config = load_config()
    return {
        "model": config.get("model_name"),
        "provider": config.get("provider"),
        "base_url": config.get("base_url"),
        "api_key_set": bool(config.get("api_key")),
        "supports_vision": bool(config.get("supports_vision", False)),
    }
