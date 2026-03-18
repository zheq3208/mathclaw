"""Core configuration read/write helpers."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from mathclaw.constant import WORKING_DIR

_DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_DEFAULT_MODEL_NAME = "qwen3-vl-plus"


def _default_mcp_clients() -> dict[str, Any]:
    working_dir = Path(WORKING_DIR)
    repo_root = working_dir.parent if working_dir.name.startswith(".") else working_dir
    exam_bank_dir = working_dir / "exam_bank"
    return {
        "tavily": {
            "name": "tavily-search",
            "description": "Optional Tavily MCP client for search and extraction.",
            "enabled": False,
            "transport": "streamable_http",
            "url": "https://mcp.tavily.com/mcp/",
            "headers": {},
            "command": "",
            "args": [],
            "env": {},
            "cwd": "",
        },
        "playwright": {
            "name": "playwright-browser",
            "description": "Optional Playwright MCP client for browser automation.",
            "enabled": False,
            "transport": "stdio",
            "url": "",
            "headers": {},
            "command": "npx",
            "args": ["-y", "@playwright/mcp@latest", "--headless", "--no-sandbox"],
            "env": {},
            "cwd": "",
        },
        "filesystem": {
            "name": "exam-filesystem",
            "description": "Optional filesystem MCP client scoped to the project workspace.",
            "enabled": False,
            "transport": "stdio",
            "url": "",
            "headers": {},
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                str(repo_root),
                str(working_dir),
                str(exam_bank_dir),
            ],
            "env": {},
            "cwd": "",
        },
    }


def config_path() -> Path:
    return Path(WORKING_DIR) / "config.json"


def merge_config(base: dict[str, Any], override: dict[str, Any] | None = None) -> dict[str, Any]:
    """Deep-merge two config dictionaries without mutating inputs."""
    merged = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_config(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def build_default_config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "language": "zh-CN",
        "show_tool_details": True,
        "heartbeat_every": "30m",
        "provider": "dashscope",
        "model_name": _DEFAULT_MODEL_NAME,
        "api_key": "",
        "base_url": _DEFAULT_BASE_URL,
        "supports_vision": True,
        "extra": {
            "supports_vision": True,
        },
        "mcp": {
            "clients": _default_mcp_clients(),
        },
        "channels": {
            "qq": {
                "enabled": False,
                "app_id": "",
                "client_secret": "",
                "bot_prefix": "",
            },
            "wecom": {
                "enabled": False,
                "bot_id": "",
                "secret": "",
                "bot_prefix": "",
                "welcome_message": "",
            },
        },
        "agents": {
            "defaults": {
                "heartbeat": {
                    "enabled": False,
                    "every": "30m",
                    "target": "last",
                    "channel": "",
                    "user_id": "",
                    "session_id": "",
                },
            },
        },
        "debug_skill_footer": False,
    }
    return merge_config(defaults, overrides)


def load_config(path: Path | None = None) -> dict[str, Any]:
    path = path or config_path()
    if not path.exists():
        return build_default_config()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    return build_default_config(raw)


def save_config(data: dict[str, Any], path: Path | None = None) -> None:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def get_heartbeat_query_path() -> Path:
    """Return HEARTBEAT.md path (prefers md_files/)."""
    working = Path(WORKING_DIR)
    candidate = working / "md_files" / "HEARTBEAT.md"
    if candidate.exists():
        return candidate
    return working / "HEARTBEAT.md"


def get_heartbeat_config() -> Any:
    """Return heartbeat config as attribute-access object."""
    data = load_config()
    hb = (
        data.get("agents", {})
        .get("defaults", {})
        .get("heartbeat")
    )
    if not isinstance(hb, dict):
        hb = {}

    if "heartbeat_enabled" in data and "enabled" not in hb:
        hb["enabled"] = bool(data.get("heartbeat_enabled"))
    if "heartbeat_every" in data and "every" not in hb:
        hb["every"] = str(data.get("heartbeat_every") or "").strip()
    if "heartbeat_target" in data and "target" not in hb:
        hb["target"] = str(data.get("heartbeat_target") or "").strip()
    if "heartbeat_channel" in data and "channel" not in hb:
        hb["channel"] = str(data.get("heartbeat_channel") or "").strip()
    if "heartbeat_user_id" in data and "user_id" not in hb:
        hb["user_id"] = str(data.get("heartbeat_user_id") or "").strip()
    if "heartbeat_session_id" in data and "session_id" not in hb:
        hb["session_id"] = str(data.get("heartbeat_session_id") or "").strip()

    merged: dict[str, Any] = {
        "enabled": bool(hb.get("enabled", False)),
        "every": str(hb.get("every") or "30m"),
        "target": str(hb.get("target") or "last"),
        "channel": str(hb.get("channel") or "").strip(),
        "user_id": str(hb.get("user_id") or "").strip(),
        "session_id": str(hb.get("session_id") or "").strip(),
    }
    active = hb.get("active_hours") or hb.get("activeHours")
    if isinstance(active, dict):
        merged["active_hours"] = SimpleNamespace(
            start=str(active.get("start") or "08:00"),
            end=str(active.get("end") or "22:00"),
        )
    else:
        merged["active_hours"] = None
    return SimpleNamespace(**merged)


def update_last_dispatch(channel: str, user_id: str, session_id: str) -> None:
    """Persist last channel dispatch target for heartbeat target=last."""
    data = load_config()
    data["last_dispatch"] = {
        "channel": channel or "",
        "user_id": user_id or "",
        "session_id": session_id or "",
    }
    save_config(data)
