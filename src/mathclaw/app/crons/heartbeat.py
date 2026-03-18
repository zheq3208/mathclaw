"""Heartbeat helpers for scheduled learning check-ins."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Any

from ...constant import WORKING_DIR

logger = logging.getLogger(__name__)

_EVERY_PATTERN = re.compile(
    r"^(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s)?$",
    re.IGNORECASE,
)

HEARTBEAT_TARGET_LAST = "last"
HEARTBEAT_TIMEOUT_SECONDS = 45


def parse_heartbeat_every(every: str) -> int:
    """Parse interval string (for example 30m or 1h) into seconds."""
    every = str(every or "").strip()
    if not every:
        return 30 * 60

    match = _EVERY_PATTERN.match(every)
    if not match:
        logger.warning("heartbeat every=%r invalid, using 30m", every)
        return 30 * 60

    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    total = hours * 3600 + minutes * 60 + seconds
    return total if total > 0 else 30 * 60


def _in_active_hours(active_hours: Any) -> bool:
    if (
        not active_hours
        or not hasattr(active_hours, "start")
        or not hasattr(active_hours, "end")
    ):
        return True

    try:
        start_parts = str(active_hours.start).strip().split(":")
        end_parts = str(active_hours.end).strip().split(":")
        start_t = dt_time(
            int(start_parts[0]),
            int(start_parts[1]) if len(start_parts) > 1 else 0,
        )
        end_t = dt_time(
            int(end_parts[0]),
            int(end_parts[1]) if len(end_parts) > 1 else 0,
        )
    except (ValueError, IndexError, AttributeError):
        return True

    now = datetime.now().time()
    if start_t <= end_t:
        return start_t <= now <= end_t
    return now >= start_t or now <= end_t


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _dedupe_texts(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = _safe_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _rank_named_records(mapping: Any, *score_keys: str) -> list[tuple[float, str, dict[str, Any]]]:
    ranked: list[tuple[float, str, dict[str, Any]]] = []
    if not isinstance(mapping, dict):
        return ranked
    for raw_name, raw_payload in mapping.items():
        name = _safe_text(raw_name)
        if not name:
            continue
        payload = raw_payload if isinstance(raw_payload, dict) else {}
        score = 0.0
        for key in score_keys:
            value = payload.get(key)
            if isinstance(value, (int, float)):
                score = float(value)
                break
        ranked.append((score, name, payload))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return ranked


def _resolve_dispatch_target(hb_config: Any) -> dict[str, str] | None:
    if hb_config is None:
        return None

    target = _safe_text(getattr(hb_config, "target", "")).lower()
    if not target:
        return None

    last_dispatch = _get_last_dispatch_safe()
    if target == HEARTBEAT_TARGET_LAST:
        if last_dispatch is None:
            return None
        channel = _safe_text(getattr(last_dispatch, "channel", "")).lower()
        user_id = _safe_text(getattr(last_dispatch, "user_id", ""))
        session_id = _safe_text(getattr(last_dispatch, "session_id", ""))
        if not channel or not (user_id or session_id):
            return None
        return {
            "channel": channel,
            "user_id": user_id,
            "session_id": session_id,
        }

    channel = _safe_text(getattr(hb_config, "channel", "") or target).lower()
    user_id = _safe_text(getattr(hb_config, "user_id", ""))
    session_id = _safe_text(getattr(hb_config, "session_id", ""))

    if last_dispatch is not None:
        last_channel = _safe_text(getattr(last_dispatch, "channel", "")).lower()
        if last_channel == channel:
            if not user_id:
                user_id = _safe_text(getattr(last_dispatch, "user_id", ""))
            if not session_id:
                session_id = _safe_text(getattr(last_dispatch, "session_id", ""))

    if not channel or not (user_id or session_id):
        return None
    return {
        "channel": channel,
        "user_id": user_id,
        "session_id": session_id,
    }


def _get_last_dispatch_safe() -> Any:
    try:
        from ...config import load_config

        config = load_config()
        if isinstance(config, dict):
            last = config.get("last_dispatch")
            if isinstance(last, dict):
                from types import SimpleNamespace
                return SimpleNamespace(**last)
            return None
        return getattr(config, "last_dispatch", None)
    except Exception:
        return None


def _get_heartbeat_config_safe() -> Any:
    try:
        from ...config import get_heartbeat_config
        return get_heartbeat_config()
    except Exception:
        return None


def _load_global_memory(student_id: str = "__global__") -> dict[str, Any]:
    try:
        from ...agents.tools.math_learning import get_global_learning_memory
        payload = get_global_learning_memory(student_id)
    except Exception:
        logger.debug("heartbeat: load global memory failed", exc_info=True)
        return {}
    if isinstance(payload, dict):
        memory = payload.get("memory")
        if isinstance(memory, dict):
            return memory
    return {}


def _load_direct_review_reminders(student_id: str = "__global__") -> list[dict[str, Any]]:
    try:
        from ...agents.tools.math_learning import (
            _load_json,
            _resolve_global_student_key,
            _review_registry_path,
        )
    except Exception:
        logger.debug("heartbeat: review reminder helpers unavailable", exc_info=True)
        return []

    registry = _load_json(_review_registry_path(), {})
    if not isinstance(registry, dict):
        return []

    target_student = _resolve_global_student_key(student_id)
    reminders: list[dict[str, Any]] = []
    for job_id, raw in registry.items():
        if not isinstance(raw, dict):
            continue
        if _safe_text(raw.get("status")) == "cancelled":
            continue
        record_student = _safe_text(raw.get("student_id")) or "__global__"
        if target_student == "__global__":
            if record_student not in {"", "__global__"}:
                continue
        elif record_student != target_student:
            continue
        item = dict(raw)
        item["job_id"] = _safe_text(job_id)
        reminders.append(item)

    reminders.sort(
        key=lambda item: (
            _safe_text(item.get("due_at")) or _safe_text(item.get("created_at")),
            _safe_text(item.get("knowledge_point")),
        ),
    )
    return reminders


def _build_learning_plan_checkin(student_id: str = "__global__") -> str:
    memory = _load_global_memory(student_id)
    reminders = _load_direct_review_reminders(student_id)

    knowledge_points = _rank_named_records(
        memory.get("knowledge_points", {}),
        "risk_score",
        "severity",
    )
    weaknesses = _rank_named_records(
        memory.get("weaknesses", {}),
        "severity",
        "risk_score",
    )
    mastered_points = _rank_named_records(
        memory.get("mastered_knowledge_points", {}),
        "risk_score",
        "severity",
    )
    prerequisite_gaps = _rank_named_records(
        memory.get("prerequisite_gaps", {}),
        "count",
    )

    reminder_points = _dedupe_texts([
        _safe_text(item.get("knowledge_point")) for item in reminders
    ])
    active_points = [name for _, name, _ in knowledge_points]
    task_points = _dedupe_texts(reminder_points + active_points)
    if not task_points:
        task_points = [name for _, name, _ in mastered_points[:1]]
    if not task_points:
        task_points = ["\u8fd1\u671f\u6570\u5b66\u5185\u5bb9"]

    primary_weakness = weaknesses[0][1] if weaknesses else ""
    prerequisite_gap = prerequisite_gaps[0][1] if prerequisite_gaps else ""

    focus_items = _dedupe_texts(
        list(memory.get("practice_focus", []))
        + list(weaknesses[0][2].get("practice_focus", [])) if weaknesses else list(memory.get("practice_focus", []))
        + list(knowledge_points[0][2].get("practice_focus", [])) if knowledge_points else list(memory.get("practice_focus", []))
    )
    focus_items = focus_items[:3]

    focus_text = "\u3001".join(focus_items[:2]) if focus_items else "\u7b26\u53f7\u3001\u6b65\u9aa4\u548c\u5b9a\u4e49\u57df\u68c0\u67e5"
    task_text = "\u3001".join(task_points[:2])

    guidance_parts: list[str] = []
    if primary_weakness:
        guidance_parts.append(f"\u5148\u76ef\u4f4f{primary_weakness}")
    if focus_text:
        guidance_parts.append(f"\u505a\u9898\u65f6\u9010\u9879\u68c0\u67e5{focus_text}")
    if prerequisite_gap and len(guidance_parts) < 2:
        guidance_parts.append(f"\u5148\u8865{prerequisite_gap}")
    guidance = "\uff1b".join(guidance_parts[:2]) + "\u3002" if guidance_parts else "\u5148\u56de\u770b1\u9053\u4f8b\u9898\uff0c\u518d\u5b8c\u62102\u9053\u540c\u7c7b\u9898\u3002"

    schedule_parts: list[str] = []
    if reminders:
        schedule_parts.append(f"\u672c\u8f6e\u6709{len(reminders)}\u9879\u590d\u4e60\u63d0\u9192")
    schedule_parts.append(f"\u5148\u752810\u5206\u949f\u56de\u770b{task_points[0]}")
    schedule_parts.append("\u518d\u752810\u5206\u949f\u5b8c\u62102\u9053\u540c\u7c7b\u9898")
    schedule_parts.append("\u6700\u540e\u75281\u53e5\u8bdd\u8bb0\u5f55\u9519\u56e0")
    schedule = "\uff0c".join(schedule_parts[:3]) + "\u3002"

    now_text = datetime.now().strftime("%m\u6708%d\u65e5 %H:%M")
    lines = [
        f"\u5b66\u4e60\u8ba1\u5212\u6253\u5361\u63d0\u9192 | {now_text}",
        f"\u4eca\u65e5\u590d\u4e60\uff1a{task_text}\u3002",
        f"\u91cd\u70b9\u6307\u5bfc\uff1a{guidance}",
        f"\u5b89\u6392\u5efa\u8bae\uff1a{schedule}",
        "\u5b8c\u6210\u540e\u56de\u590d\u201c\u5df2\u590d\u4e60\u201d\u6253\u5361\u3002",
    ]
    return "\n".join(lines)


async def run_heartbeat_once(
    *,
    runner: Any,
    channel_manager: Any,
) -> None:
    """Run one lightweight heartbeat and optionally dispatch it."""
    _ = runner
    working_dir = Path(WORKING_DIR)
    hb_config = _get_heartbeat_config_safe()

    if hb_config and not bool(getattr(hb_config, "enabled", False)):
        logger.debug("heartbeat skipped: disabled in config")
        return

    if hb_config and not _in_active_hours(getattr(hb_config, "active_hours", None)):
        logger.debug("heartbeat skipped: outside active hours")
        return

    final_text = _build_learning_plan_checkin("__global__")
    if not final_text:
        logger.debug("heartbeat skipped: no direct reminder text generated")
        return

    _write_heartbeat_status(working_dir)

    dispatch_target = _resolve_dispatch_target(hb_config)
    if not dispatch_target or channel_manager is None:
        logger.debug("heartbeat generated without dispatch target")
        return

    try:
        await asyncio.wait_for(
            channel_manager.send_text(
                channel=dispatch_target["channel"],
                user_id=dispatch_target.get("user_id", ""),
                session_id=dispatch_target.get("session_id", ""),
                text=final_text,
                meta={"heartbeat": True, "mode": "direct"},
            ),
            timeout=HEARTBEAT_TIMEOUT_SECONDS,
        )
        logger.info(
            "heartbeat dispatched: channel=%s target=%s",
            dispatch_target.get("channel", ""),
            dispatch_target.get("user_id", "") or dispatch_target.get("session_id", ""),
        )
    except asyncio.TimeoutError:
        logger.warning("heartbeat dispatch timed out")
    except Exception:
        logger.exception("heartbeat dispatch failed")


def _write_heartbeat_status(working_dir: Path) -> None:
    hb_file = working_dir / "heartbeat.json"
    hb_file.parent.mkdir(parents=True, exist_ok=True)
    hb_file.write_text(
        json.dumps(
            {"timestamp": time.time(), "status": "alive"},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
