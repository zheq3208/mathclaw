"""Global learning memory API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class MemoryMasteredRequest(BaseModel):
    student_id: str = ""
    item_type: str = Field(default="knowledge_point")
    item_name: str = Field(..., min_length=1)
    note: str = ""


def _sorted_entries(mapping: dict[str, Any], *, score_key: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for name, record in mapping.items():
        if not isinstance(record, dict):
            continue
        entries.append({"name": name, **record})
    entries.sort(key=lambda item: (-float(item.get(score_key, 0.0)), item["name"]))
    return entries


@router.get("")
async def get_memory(student_id: str = ""):
    from researchclaw.agents.tools.math_learning import get_global_learning_memory

    payload = get_global_learning_memory(student_id)
    if student_id.strip():
        memory = payload.get("memory", {}) if isinstance(payload, dict) else {}
        active_weaknesses = _sorted_entries(memory.get("weaknesses", {}), score_key="severity")
        active_knowledge_points = _sorted_entries(memory.get("knowledge_points", {}), score_key="risk_score")
        mastered_weaknesses = _sorted_entries(memory.get("mastered_weaknesses", {}), score_key="mastery_streak")
        mastered_knowledge_points = _sorted_entries(memory.get("mastered_knowledge_points", {}), score_key="mastery_streak")
        return {
            "memory_path": payload.get("memory_path", ""),
            "student_id": payload.get("student_id", ""),
            "student_ids": payload.get("students", []),
            "memory": memory,
            "active_weaknesses": active_weaknesses,
            "active_knowledge_points": active_knowledge_points,
            "mastered_weaknesses": mastered_weaknesses,
            "mastered_knowledge_points": mastered_knowledge_points,
            "summary": {
                "active_weakness_count": len(active_weaknesses),
                "active_knowledge_point_count": len(active_knowledge_points),
                "mastered_weakness_count": len(mastered_weaknesses),
                "mastered_knowledge_point_count": len(mastered_knowledge_points),
                "recent_event_count": len(memory.get("recent_events", [])) if isinstance(memory, dict) else 0,
            },
            "updated_at": payload.get("updated_at", ""),
        }
    students = payload.get("students", {}) if isinstance(payload.get("students"), dict) else {}
    return {
        "memory_path": payload.get("memory_path", ""),
        "student_ids": sorted(students.keys()),
        "students": students,
        "updated_at": payload.get("updated_at", ""),
    }


@router.post("/mastered")
async def mark_memory_mastered(request: MemoryMasteredRequest):
    from researchclaw.agents.tools.math_learning import mark_global_memory_mastered

    return mark_global_memory_mastered(
        student_id=request.student_id,
        item_type=request.item_type,
        item_name=request.item_name,
        note=request.note,
    )
