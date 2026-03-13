"""Generate markdown-only skills from free-form requirements."""

from __future__ import annotations

import json
import logging
import re
import textwrap
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from researchclaw.agents.skills_manager import SkillsManager
from researchclaw.providers.store import ProviderStore

logger = logging.getLogger(__name__)

_DEFAULT_GENERATOR_MODEL = "qwen/qwen3-vl-8b-instruct"
_CATEGORY_HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("讲解", ("讲解", "解释", "socratic", "teach", "tutor", "引导")),
    ("解题", ("解题", "求解", "方程", "证明", "problem", "solve")),
    ("练习", ("练习", "变式", "训练", "drill", "quiz", "题目")),
    ("复习", ("复习", "review", "spaced", "记忆", "回顾")),
    ("错题", ("错题", "错因", "订正", "mistake", "error")),
    ("诊断", ("诊断", "薄弱", "评估", "assess", "analyze")),
    ("总结", ("总结", "归纳", "摘要", "synth", "summary")),
]


@dataclass(slots=True)
class GeneratedSkillDraft:
    slug: str
    title: str
    description: str
    markdown: str
    categories: list[str]


def _coerce_json_object(content: str) -> dict[str, Any]:
    cleaned = (content or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        payload = json.loads(cleaned, strict=False)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, re.S)
    if not match:
        raise ValueError("Skill creator model did not return valid JSON")

    payload = json.loads(match.group(0), strict=False)
    if not isinstance(payload, dict):
        raise ValueError("Skill creator model returned an unexpected payload")
    return payload


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug[:48].strip("-")
    return slug or "custom-skill"


def _unique_slug(base: str, used: set[str]) -> str:
    candidate = _slugify(base)
    if candidate not in used:
        used.add(candidate)
        return candidate

    index = 2
    while True:
        next_candidate = f"{candidate}-{index}"
        if next_candidate not in used:
            used.add(next_candidate)
            return next_candidate
        index += 1


def _strip_frontmatter(markdown: str) -> str:
    text = (markdown or "").strip()
    if not text.startswith("---"):
        return text

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text

    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return "\n".join(lines[idx + 1 :]).strip()
    return text


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
                continue
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
                continue
            if isinstance(text, dict) and isinstance(text.get("value"), str):
                parts.append(text["value"].strip())
                continue
            content_value = item.get("content")
            if isinstance(content_value, str) and content_value.strip():
                parts.append(content_value.strip())
        return "\n".join(parts).strip()
    return ""


def _yaml_scalar(value: str) -> str:
    return json.dumps((value or "").strip(), ensure_ascii=False)


def _normalize_categories(value: Any) -> list[str]:
    categories: list[str] = []
    if isinstance(value, str):
        categories.extend([part.strip() for part in re.split(r"[,/|、，]", value) if part.strip()])
    elif isinstance(value, list):
        categories.extend(
            str(part).strip()
            for part in value
            if str(part).strip()
        )
    elif isinstance(value, dict):
        categories.extend(
            str(part).strip()
            for part in value.values()
            if str(part).strip()
        )

    deduped: list[str] = []
    seen: set[str] = set()
    for item in categories:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item[:16])
    return deduped[:3]


def _infer_categories(*texts: str) -> list[str]:
    merged = " ".join(texts).lower()
    categories: list[str] = []
    for label, keywords in _CATEGORY_HINTS:
        if any(keyword.lower() in merged for keyword in keywords):
            categories.append(label)
    if not categories:
        categories.append("通用")
    return categories[:3]


def _fallback_body(title: str, description: str, requirements: str) -> str:
    summary = requirements.strip().replace("\r", "")
    return (
        "# Role\n"
        f"{title} focuses on this goal: {description or title}.\n\n"
        "# When to Use\n"
        f"- Use this skill when the user request matches: {summary}.\n"
        "- Use it for explanation and guidance, not for running tools or writing code.\n\n"
        "# Workflow\n"
        "1. Restate the user goal in simple language.\n"
        "2. Break the task into a short, reusable teaching flow.\n"
        "3. Keep outputs structured and easy to follow.\n"
        "4. Ask at most one clarifying question only when required.\n\n"
        "# Guardrails\n"
        "- Do not invent APIs, scripts, or automations.\n"
        "- Do not claim capabilities outside text guidance.\n"
        "- Keep the interaction focused on the requested learning task.\n\n"
        "# Response Style\n"
        "- Be concise.\n"
        "- Prefer checklists, short sections, and concrete examples.\n"
    )


def _compose_markdown(
    title: str,
    description: str,
    body: str,
    model_name: str,
    categories: list[str],
) -> str:
    body_text = body.strip() or _fallback_body(title, description, title)
    frontmatter = [
        "---",
        f"name: {_yaml_scalar(title)}",
        f"description: {_yaml_scalar(description)}",
        "generated: true",
        "deletable: true",
        'created_by: "skill_creator"',
        f"generator_model: {_yaml_scalar(model_name)}",
    ]
    if categories:
        frontmatter.append("categories:")
        frontmatter.extend(f"  - {_yaml_scalar(category)}" for category in categories)
    frontmatter.extend(["---", ""])
    return "\n".join(frontmatter) + body_text + "\n"


def _normalize_skill_payload(
    payload: dict[str, Any],
    requirements: str,
    model_name: str,
    existing_slugs: set[str] | None = None,
) -> list[GeneratedSkillDraft]:
    raw_skills = payload.get("skills")
    if isinstance(raw_skills, dict):
        raw_skills = [raw_skills]
    if not isinstance(raw_skills, list) or not raw_skills:
        raise ValueError("Skill creator model did not return any skills")

    used = set(existing_slugs or set())
    drafts: list[GeneratedSkillDraft] = []
    for index, item in enumerate(raw_skills[:2], start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or f"Skill {index}").strip()
        description = str(item.get("description") or "").strip()
        slug = _unique_slug(str(item.get("slug") or title or description), used)
        body = _strip_frontmatter(str(item.get("markdown") or item.get("body") or ""))
        if not description:
            description = f"Custom skill generated from: {requirements[:72].strip()}"
        categories = _normalize_categories(item.get("categories"))
        if not categories:
            categories = _infer_categories(title, description, body, requirements)
        markdown = _compose_markdown(
            title=title[:80],
            description=description[:140],
            body=body or _fallback_body(title, description, requirements),
            model_name=model_name,
            categories=categories,
        )
        drafts.append(
            GeneratedSkillDraft(
                slug=slug,
                title=title[:80],
                description=description[:140],
                markdown=markdown,
                categories=categories,
            ),
        )

    if not drafts:
        raise ValueError("Skill creator model returned no usable skills")
    return drafts


def _pick_generation_provider() -> dict[str, Any]:
    store = ProviderStore()
    providers = store.list_providers()

    def is_valid(item: dict[str, Any]) -> bool:
        return bool(
            item.get("api_key") and item.get("base_url") and item.get("model_name"),
        )

    qwen_candidates = [
        item
        for item in providers
        if is_valid(item)
        and "qwen3-vl" in str(item.get("model_name") or "").lower()
    ]

    for group in (
        [item for item in qwen_candidates if item.get("enabled")],
        [item for item in qwen_candidates if item.get("name") == "openrouter-qwen-vl"],
        qwen_candidates,
    ):
        if group:
            return group[0]

    raise RuntimeError(
        "No qwen3-vl provider is configured. Configure openrouter-qwen-vl first.",
    )


async def _request_skill_payload(
    provider: dict[str, Any],
    requirements: str,
    preferred_count: int,
) -> dict[str, Any]:
    base_url = str(provider.get("base_url") or "").rstrip("/")
    api_key = str(provider.get("api_key") or "").strip()
    model_name = str(provider.get("model_name") or "").strip()
    if not base_url or not api_key or not model_name:
        raise RuntimeError("The qwen3-vl provider is missing base_url, api_key, or model_name")

    system_prompt = textwrap.dedent(
        f"""
        You are Skill Creator for MathClaw, a middle-school and high-school math tutoring product.
        Generate at most {preferred_count} markdown-only skills from the user requirement.

        Hard rules:
        - Prefer 1 skill unless the requirement clearly spans two distinct reusable workflows.
        - Return pure markdown skills only. No Python, no scripts, no tools, no API instructions.
        - Write skills for an AI assistant, not for an end user.
        - Keep each skill focused, concise, and reusable.
        - For each skill, return a short title, a short description, a short category list, and the markdown BODY of SKILL.md.
        - The markdown must NOT include YAML frontmatter.
        - Categories must be 1-3 short Chinese tags chosen from the task intent, such as 讲解, 解题, 练习, 复习, 错题, 诊断, 总结.
        - Each markdown body should include these sections:
          # Role
          # When to Use
          # Workflow
          # Guardrails
          # Response Style
        - Do not wrap the JSON in markdown fences.

        Return JSON only in this exact shape:
        {{
          "skills": [
            {{
              "title": "Short title",
              "slug": "short-hyphen-slug",
              "description": "One-line description",
              "categories": ["讲解", "练习"],
              "markdown": "# Role\\n..."
            }}
          ]
        }}
        """
    ).strip()

    user_prompt = textwrap.dedent(
        f"""
        User requirement:
        {requirements.strip()}

        Return JSON only.
        """
    ).strip()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if "openrouter.ai" in base_url:
        headers["HTTP-Referer"] = "https://mathclaw.local"
        headers["X-Title"] = "MathClaw Skill Creator"

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 3200,
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    choices = data.get("choices") or []
    if not choices:
        raise ValueError("Skill creator model returned no choices")

    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    content = _message_text(message.get("content"))
    if not content:
        raise ValueError("Skill creator model returned empty content")
    return _coerce_json_object(content)


def _serialize_drafts(drafts: list[GeneratedSkillDraft]) -> list[dict[str, Any]]:
    return [
        {
            "slug": draft.slug,
            "title": draft.title,
            "description": draft.description,
            "markdown": draft.markdown,
            "categories": draft.categories,
        }
        for draft in drafts
    ]


async def preview_markdown_skills(
    requirements: str,
    preferred_count: int = 2,
) -> list[dict[str, Any]]:
    request_text = (requirements or "").strip()
    if len(request_text) < 8:
        raise ValueError("Please provide a more specific skill requirement")

    provider = _pick_generation_provider()
    payload = await _request_skill_payload(provider, request_text, preferred_count)
    existing = {
        Path(skill.path).name
        for skill in SkillsManager().list_available_skills()
        if getattr(skill, "path", "")
    }
    drafts = _normalize_skill_payload(
        payload,
        requirements=request_text,
        model_name=str(provider.get("model_name") or _DEFAULT_GENERATOR_MODEL),
        existing_slugs=existing,
    )
    return _serialize_drafts(drafts)


def materialize_preview_drafts(
    drafts: list[dict[str, Any]],
    *,
    model_name: str = _DEFAULT_GENERATOR_MODEL,
) -> list[dict[str, Any]]:
    if not drafts:
        raise ValueError("No preview drafts were provided")

    normalized = _normalize_skill_payload(
        {"skills": drafts},
        requirements="preview confirmation",
        model_name=model_name,
        existing_slugs=set(),
    )
    return _serialize_drafts(normalized)


async def generate_markdown_skills(
    requirements: str,
    preferred_count: int = 2,
) -> list[dict[str, Any]]:
    return await preview_markdown_skills(requirements, preferred_count)
