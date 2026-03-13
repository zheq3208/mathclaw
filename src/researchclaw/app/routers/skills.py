"""Skill management API routes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


class SkillToggleRequest(BaseModel):
    """Request to enable or disable a skill."""

    skill_name: str


class SkillInstallRequest(BaseModel):
    """Request to install a skill from hub."""

    skill_id: str
    hub_url: str | None = None


class SkillPreviewRequest(BaseModel):
    """Request to preview markdown-only skills from requirements."""

    requirements: str = Field(..., min_length=8, max_length=4000)
    preferred_count: int = Field(default=2, ge=1, le=2)


class SkillDraftPayload(BaseModel):
    slug: str = Field(..., min_length=1, max_length=80)
    title: str = Field(..., min_length=1, max_length=80)
    description: str = Field(..., min_length=1, max_length=180)
    markdown: str = Field(..., min_length=20)
    categories: list[str] = Field(default_factory=list)


class SkillCreateRequest(BaseModel):
    drafts: list[SkillDraftPayload] = Field(..., min_length=1, max_length=2)


def _resolve_skill_identity(skills: list, skill_name: str):
    target = (skill_name or "").strip()
    for skill in skills:
        canonical_name = Path(skill.path).name or skill.name
        if target in {skill.name, canonical_name}:
            return skill, canonical_name
    return None, None


def _create_from_drafts(drafts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from researchclaw.agents.skills_manager import SkillsManager
    from researchclaw.app.services.skill_creator import materialize_preview_drafts

    manager = SkillsManager()
    normalized = materialize_preview_drafts(drafts)
    return [
        manager.create_skill(draft["slug"], draft["markdown"])
        for draft in normalized
    ]


@router.get("")
async def list_skills():
    """List all available skills."""
    try:
        from researchclaw.agents.skills_manager import SkillsManager

        manager = SkillsManager()
        skills = manager.list_available_skills()
        return {"skills": skills}
    except Exception as e:
        logger.exception("Failed to list skills")
        return {"skills": [], "error": str(e)}


@router.get("/active")
async def list_active_skills():
    """List currently active (enabled) skills."""
    try:
        from researchclaw.agents.skills_manager import SkillsManager

        manager = SkillsManager()
        active = manager.list_active_skills()
        return {"active_skills": active}
    except Exception as e:
        return {"active_skills": [], "error": str(e)}


@router.post("/enable")
async def enable_skill(request: SkillToggleRequest):
    """Enable a skill."""
    try:
        from researchclaw.agents.skills_manager import SkillsManager

        manager = SkillsManager()
        manager.enable_skill(request.skill_name)
        return {"status": "enabled", "skill": request.skill_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disable")
async def disable_skill(request: SkillToggleRequest):
    """Disable a skill."""
    try:
        from researchclaw.agents.skills_manager import SkillsManager

        manager = SkillsManager()
        manager.disable_skill(request.skill_name)
        return {"status": "disabled", "skill": request.skill_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preview")
async def preview_skills(request: SkillPreviewRequest):
    """Preview markdown-only skills with qwen3-vl without installing them."""
    try:
        from researchclaw.app.services.skill_creator import preview_markdown_skills

        drafts = await preview_markdown_skills(
            request.requirements.strip(),
            request.preferred_count,
        )
        return {"status": "previewed", "drafts": drafts}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except httpx.HTTPError as e:
        logger.exception("Skill creator preview request failed")
        raise HTTPException(
            status_code=502,
            detail=f"Skill creator model request failed: {e}",
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Failed to preview skills")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create")
async def create_previewed_skills(request: SkillCreateRequest):
    """Install previewed markdown-only skills into customized and active skills."""
    try:
        created = _create_from_drafts([draft.model_dump() for draft in request.drafts])
        return {"status": "created", "skills": created}
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to create previewed skills")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_skills(request: SkillPreviewRequest):
    """Backward-compatible preview+create endpoint."""
    try:
        from researchclaw.app.services.skill_creator import preview_markdown_skills

        drafts = await preview_markdown_skills(
            request.requirements.strip(),
            request.preferred_count,
        )
        created = _create_from_drafts(drafts)
        return {"status": "created", "skills": created}
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except httpx.HTTPError as e:
        logger.exception("Skill creator model request failed")
        raise HTTPException(
            status_code=502,
            detail=f"Skill creator model request failed: {e}",
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Failed to generate skills")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/install")
async def install_skill(request: SkillInstallRequest):
    """Install a skill from the skills hub."""
    try:
        from researchclaw.agents.skills_hub import SkillsHubClient

        client = (
            SkillsHubClient(base_url=request.hub_url)
            if request.hub_url
            else SkillsHubClient()
        )
        result = client.install(request.skill_id)
        return {
            "status": "installed",
            "skill": request.skill_id,
            "result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hub/search")
async def search_hub(q: str = "", tags: str = ""):
    """Search skills in the hub."""
    try:
        from researchclaw.agents.skills_hub import SkillsHubClient

        client = SkillsHubClient()
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        results = client.search(query=q, tags=tag_list)
        return {"results": results}
    except Exception as e:
        return {"results": [], "error": str(e)}


@router.delete("/{skill_name}")
async def delete_generated_skill(skill_name: str):
    """Delete a generated custom skill."""
    try:
        from researchclaw.agents.skills_manager import SkillsManager

        manager = SkillsManager()
        skill, canonical_name = _resolve_skill_identity(
            manager.list_available_skills(),
            skill_name,
        )
        if skill is None or not canonical_name:
            raise HTTPException(
                status_code=404,
                detail=f"Skill '{skill_name}' not found",
            )
        if skill.source != "customized" or not skill.deletable:
            raise HTTPException(
                status_code=403,
                detail="Only Skill Creator generated skills can be deleted",
            )
        if not manager.delete_skill(canonical_name):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete skill '{canonical_name}'",
            )
        return {"status": "deleted", "skill": canonical_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete generated skill")
        raise HTTPException(status_code=500, detail=str(e))
