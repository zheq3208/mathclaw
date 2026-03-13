"""Helpers for deterministic math resource retrieval."""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..constant import WORKING_DIR

_YEAR_RE = re.compile(r"(20\d{2})")
_SPACE_RE = re.compile(r"\s+")
_FILLER_RE = re.compile(
    r"^(\u8bf7|\u8bf7\u95ee|\u5e2e\u6211|\u7ed9\u6211|\u6211\u60f3\u8981|\u6211\u60f3\u627e|\u6211\u9700\u8981|\u5e2e\u5fd9|\u9ebb\u70e6|\u627e\u4e00\u4e0b|\u641c\u4e00\u4e0b|\u641c\u641c|\u627e\u627e|\u63a8\u8350\u4e00\u4e0b|\u63a8\u8350\u4e0b)\s*",
)

_MATH_TERMS = ("\u6570\u5b66", "math", "mathematics")
_MATH_TOPIC_TERMS = (
    "\u5bfc\u6570",
    "\u51fd\u6570",
    "\u6570\u5217",
    "\u6982\u7387",
    "\u7edf\u8ba1",
    "\u5411\u91cf",
    "\u51e0\u4f55",
    "\u7acb\u4f53\u51e0\u4f55",
    "\u89e3\u6790\u51e0\u4f55",
    "\u5706\u9525\u66f2\u7ebf",
    "\u4e09\u89d2\u51fd\u6570",
    "\u4e0d\u7b49\u5f0f",
    "\u65b9\u7a0b",
    "\u4e8c\u6b21\u51fd\u6570",
    "\u4e00\u6b21\u51fd\u6570",
    "\u96c6\u5408",
    "\u590d\u6570",
    "\u6781\u9650",
)
_RESOURCE_TYPE_KEYWORDS = {
    "exam_paper": (
        "\u8bd5\u5377",
        "\u8bd5\u9898",
        "\u5377\u5b50",
        "\u771f\u9898",
        "\u539f\u5377",
        "\u6a21\u62df\u5377",
        "\u6708\u8003\u5377",
        "\u671f\u4e2d\u5377",
        "\u671f\u672b\u5377",
        "\u7b54\u6848",
        "\u89e3\u6790",
        "pdf",
        "\u7535\u5b50\u7248",
        "\u4e0b\u8f7d",
    ),
    "video": (
        "\u89c6\u9891",
        "\u6559\u5b66\u89c6\u9891",
        "\u8bb2\u89e3\u89c6\u9891",
        "\u8bfe\u7a0b",
        "\u7f51\u8bfe",
        "\u8bb2\u9898\u89c6\u9891",
        "\u5f55\u64ad",
    ),
    "book": (
        "\u6559\u8f85",
        "\u6559\u8f85\u4e66",
        "\u8f85\u5bfc\u4e66",
        "\u7ec3\u4e60\u518c",
        "\u8d44\u6599\u4e66",
        "\u6559\u6750",
        "\u4e66",
    ),
    "resource": (
        "\u8d44\u6599",
        "\u8d44\u6e90",
        "\u9898\u5e93",
        "\u5408\u96c6",
        "\u603b\u7ed3",
        "\u7b14\u8bb0",
    ),
}
_SEARCH_INTENT_TERMS = (
    "\u627e",
    "\u641c",
    "\u63a8\u8350",
    "\u6709\u6ca1\u6709",
    "\u60f3\u8981",
    "\u6211\u9700\u8981",
    "\u7ed9\u6211",
    "\u5e2e\u6211",
    "\u9ebb\u70e6",
    "\u6c42",
)
_EXAM_CONTEXT_TERMS = (
    "\u9ad8\u8003",
    "\u65b0\u9ad8\u8003",
    "\u65b0\u8bfe\u6807",
    "\u65b0\u8bfe\u6807i\u5377",
    "\u65b0\u8bfe\u6807ii\u5377",
    "\u5168\u56fd\u7532\u5377",
    "\u5168\u56fd\u4e59\u5377",
    "\u7532\u5377",
    "\u4e59\u5377",
    "\u4e00\u5377",
    "\u4e8c\u5377",
    "1\u5377",
    "2\u5377",
    "\u4e2d\u8003",
)
_NEGATIVE_TERMS = (
    "\u9999\u6e2f",
    "hkdse",
    "\u6e2f\u6fb3",
    "\u6210\u4eba\u9ad8\u8003",
    "\u81ea\u8003",
)
_OTHER_SUBJECT_TERMS = (
    "\u8bed\u6587",
    "\u82f1\u8bed",
    "\u7269\u7406",
    "\u5316\u5b66",
    "\u751f\u7269",
    "\u5386\u53f2",
    "\u5730\u7406",
    "\u653f\u6cbb",
)
_ALIAS_REPLACEMENTS = (
    ("\u65b0\u9ad8\u8003\u4e00\u5377", "\u65b0\u8bfe\u6807I\u5377"),
    ("\u65b0\u9ad8\u80031\u5377", "\u65b0\u8bfe\u6807I\u5377"),
    ("\u65b0\u9ad8\u8003\u4e8c\u5377", "\u65b0\u8bfe\u6807II\u5377"),
    ("\u65b0\u9ad8\u80032\u5377", "\u65b0\u8bfe\u6807II\u5377"),
    ("\u65b0\u8bfe\u6807\u4e00\u5377", "\u65b0\u8bfe\u6807I\u5377"),
    ("\u65b0\u8bfe\u6807\u4e8c\u5377", "\u65b0\u8bfe\u6807II\u5377"),
    ("\u2160\u5377", "I\u5377"),
    ("\u2161\u5377", "II\u5377"),
)
_TYPE_LABELS = {
    "exam_paper": "\u8bd5\u5377/\u771f\u9898",
    "video": "\u6559\u5b66\u89c6\u9891",
    "book": "\u6559\u8f85/\u8d44\u6599\u4e66",
    "resource": "\u5b66\u4e60\u8d44\u6599",
}
_EXACT_EXAM_TERMS = (
    "\u65b0\u8bfe\u6807i\u5377",
    "\u65b0\u8bfe\u6807ii\u5377",
    "\u5168\u56fd\u7532\u5377",
    "\u5168\u56fd\u4e59\u5377",
    "\u7532\u5377",
    "\u4e59\u5377",
    "i\u5377",
    "ii\u5377",
)
_GENERIC_COLLECTION_TERMS = (
    "\u5168\u56fd\u5404\u5730",
    "\u5168\u79d1",
    "\u5408\u96c6",
    "\u6c47\u603b",
    "\u51fa\u7089",
)


@dataclass(slots=True)
class ResourceQueryContext:
    raw_text: str
    normalized_text: str
    search_query: str
    year: str | None
    stage: str
    resource_types: tuple[str, ...]
    topic_terms: tuple[str, ...]
    wants_pdf: bool


@dataclass(slots=True)
class RankedResourceResult:
    title: str
    url: str
    snippet: str
    score: int
    source_host: str
    matched_terms: tuple[str, ...]


def _normalize_text(text: str) -> str:
    normalized = text.strip().lower()
    for old, new in _ALIAS_REPLACEMENTS:
        normalized = normalized.replace(old.lower(), new.lower())
    normalized = normalized.replace("\u5377\u5b50", "\u8bd5\u5377")
    normalized = _SPACE_RE.sub(" ", normalized)
    return normalized.strip()


def _extract_resource_types(normalized: str) -> tuple[str, ...]:
    found = []
    for key, terms in _RESOURCE_TYPE_KEYWORDS.items():
        if any(term in normalized for term in terms):
            found.append(key)
    if not found and any(term in normalized for term in _EXAM_CONTEXT_TERMS):
        found.append("exam_paper")
    return tuple(found)


def _extract_topic_terms(normalized: str) -> tuple[str, ...]:
    topics = [term for term in _MATH_TOPIC_TERMS if term in normalized]
    return tuple(topics)


def build_resource_query_context(text: str) -> ResourceQueryContext | None:
    normalized = _normalize_text(text)
    if not normalized:
        return None

    resource_types = _extract_resource_types(normalized)
    topic_terms = _extract_topic_terms(normalized)
    has_math = any(term in normalized for term in _MATH_TERMS) or bool(topic_terms)
    has_search_intent = any(term in normalized for term in _SEARCH_INTENT_TERMS)
    has_exam_context = any(term in normalized for term in _EXAM_CONTEXT_TERMS)
    has_year = _YEAR_RE.search(normalized) is not None

    if not resource_types:
        return None
    if not has_math and not has_exam_context:
        return None
    if not has_search_intent and not (has_exam_context or has_year or topic_terms):
        return None

    stage = "generic"
    if "\u4e2d\u8003" in normalized:
        stage = "zhongkao"
    elif any(term in normalized for term in ("\u9ad8\u8003", "\u65b0\u9ad8\u8003", "\u65b0\u8bfe\u6807", "\u7532\u5377", "\u4e59\u5377", "\u4e00\u5377", "\u4e8c\u5377")):
        stage = "gaokao"

    search_query = _FILLER_RE.sub("", normalized).strip()
    search_query = re.sub(r"^(\u627e|\u641c|\u63a8\u8350|\u6c42)\s*", "", search_query)

    if "\u6570\u5b66" not in search_query and "math" not in search_query:
        search_query = f"{search_query} \u6570\u5b66"

    if "exam_paper" in resource_types and not any(term in search_query for term in ("\u8bd5\u5377", "\u8bd5\u9898", "\u771f\u9898", "\u7b54\u6848", "\u89e3\u6790")):
        search_query = f"{search_query} \u8bd5\u5377"
    if "video" in resource_types and not any(term in search_query for term in ("\u89c6\u9891", "\u8bfe\u7a0b", "\u8bb2\u89e3")):
        search_query = f"{search_query} \u6559\u5b66\u89c6\u9891"
    if "book" in resource_types and not any(term in search_query for term in ("\u6559\u8f85", "\u8f85\u5bfc\u4e66", "\u7ec3\u4e60\u518c", "\u6559\u6750")):
        search_query = f"{search_query} \u6559\u8f85"

    explicit_pdf = (
        "pdf" in normalized
        or "\u7535\u5b50\u7248" in normalized
        or "\u4e0b\u8f7d" in normalized
    )
    wants_pdf = explicit_pdf or "exam_paper" in resource_types
    if wants_pdf and "pdf" not in search_query:
        search_query = f"{search_query} pdf"

    search_query = _SPACE_RE.sub(" ", search_query).strip()
    year_match = _YEAR_RE.search(normalized)
    return ResourceQueryContext(
        raw_text=text.strip(),
        normalized_text=normalized,
        search_query=search_query,
        year=year_match.group(1) if year_match else None,
        stage=stage,
        resource_types=resource_types,
        topic_terms=topic_terms,
        wants_pdf=wants_pdf,
    )


def rank_resource_results(
    context: ResourceQueryContext,
    raw_results: list[dict[str, Any]],
) -> list[RankedResourceResult]:
    ranked: list[RankedResourceResult] = []
    seen: set[str] = set()

    for item in raw_results:
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        snippet = str(item.get("content") or item.get("raw_content") or "").strip()
        if not title or not url or url in seen:
            continue
        seen.add(url)

        haystack = "\n".join((title, snippet, url)).lower()
        title_lower = title.lower()
        url_lower = url.lower()
        score = 0
        matches: list[str] = []

        if context.year:
            if context.year in haystack:
                score += 20
                matches.append(context.year)
            elif _YEAR_RE.search(haystack):
                score -= 8

        if "\u6570\u5b66" in haystack or "math" in haystack:
            score += 16
            matches.append("\u6570\u5b66")
        else:
            score -= 24

        if context.stage == "gaokao":
            if any(term in haystack for term in ("\u9ad8\u8003", "\u65b0\u9ad8\u8003", "\u65b0\u8bfe\u6807")):
                score += 12
                matches.append("\u9ad8\u8003")
            if "\u4e2d\u8003" in haystack:
                score -= 20
        elif context.stage == "zhongkao":
            if "\u4e2d\u8003" in haystack:
                score += 12
                matches.append("\u4e2d\u8003")
            if "\u9ad8\u8003" in haystack:
                score -= 20

        exact_exam_hits = [
            term for term in _EXACT_EXAM_TERMS
            if term in context.normalized_text and term in haystack
        ]
        if exact_exam_hits:
            score += 12 * len(exact_exam_hits)
            matches.extend(exact_exam_hits)
            if any(term in title_lower for term in exact_exam_hits):
                score += 8

        for topic in context.topic_terms:
            if topic in haystack:
                score += 10
                matches.append(topic)

        if "exam_paper" in context.resource_types:
            if any(term in haystack for term in ("\u8bd5\u5377", "\u8bd5\u9898", "\u771f\u9898", "\u7b54\u6848", "\u89e3\u6790")):
                score += 14
                matches.append("\u8bd5\u5377")
            if any(term in title_lower for term in ("\u8bd5\u5377", "\u8bd5\u9898", "\u771f\u9898")):
                score += 8
            if "\u6570\u5b66" in title_lower:
                score += 10
            if any(term in title_lower for term in _GENERIC_COLLECTION_TERMS):
                score -= 10
            if "www.163.com" in url_lower:
                score += 10
            elif "www.51jiaoxi.com" in url_lower:
                score += 8
            elif "www.sohu.com" in url_lower:
                score += 6

        if "video" in context.resource_types:
            if any(term in haystack for term in ("\u89c6\u9891", "\u8bb2\u89e3", "\u8bfe\u7a0b", "b\u7ad9", "youtube", "\u8bfe\u5802")):
                score += 14
                matches.append("\u89c6\u9891")
            else:
                score -= 12
            if "www.bilibili.com" in url_lower:
                score += 16
            elif "m.bilibili.com" in url_lower:
                score += 12
            elif "www.youtube.com" in url_lower:
                score += 6
            if "/search?" in url_lower or "keyword=" in url_lower:
                score -= 8

        if "book" in context.resource_types:
            if any(term in haystack for term in ("\u6559\u8f85", "\u8f85\u5bfc\u4e66", "\u7ec3\u4e60\u518c", "\u6559\u6750", "pdf")):
                score += 14
                matches.append("\u6559\u8f85")
            else:
                score -= 10
            if "zhuanlan.zhihu.com" in url_lower:
                score += 14
            elif "www.zhihu.com" in url_lower:
                score += 10
            elif "book.douban.com" in url_lower:
                score += 12
            elif "www.douban.com" in url_lower:
                score += 8
            if "amazon." in url_lower:
                score -= 18
            if any(term in context.raw_text for term in ("\u63a8\u8350", "\u51e0\u672c")) and any(term in url_lower for term in ("amazon.", "jd.com", "dangdang.com", "taobao.com", "tmall.com")):
                score -= 8

        if "resource" in context.resource_types:
            if any(term in haystack for term in ("\u8d44\u6599", "\u8d44\u6e90", "\u5408\u96c6", "\u9898\u5e93", "\u603b\u7ed3")):
                score += 8
                matches.append("\u8d44\u6599")

        if context.wants_pdf and ("pdf" in haystack or url.lower().endswith(".pdf")):
            score += 6
            matches.append("pdf")

        if any(term in haystack for term in _NEGATIVE_TERMS):
            score -= 18
        if any(term in title_lower for term in _OTHER_SUBJECT_TERMS) and "\u6570\u5b66" not in title_lower:
            score -= 16

        ranked.append(
            RankedResourceResult(
                title=title,
                url=url,
                snippet=snippet,
                score=score,
                source_host=urlparse(url).netloc or "unknown",
                matched_terms=tuple(sorted(set(matches))),
            ),
        )

    ranked.sort(
        key=lambda item: (
            item.score,
            len(item.matched_terms),
            len(item.title),
        ),
        reverse=True,
    )
    return ranked


def summarize_extract_payload(payload_text: str, max_chars: int = 220) -> str:
    try:
        payload = json.loads(payload_text)
    except Exception:
        payload = {}

    if not isinstance(payload, dict):
        return ""

    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return ""

    first = results[0] if isinstance(results[0], dict) else {}
    raw_content = str(first.get("raw_content") or first.get("content") or "").strip()
    if not raw_content:
        return ""

    lines: list[str] = []
    for raw_line in raw_content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("![]("):
            continue
        if len(line) < 4:
            continue
        lines.append(line)
        if sum(len(item) for item in lines) >= max_chars:
            break

    excerpt = " ".join(lines)
    excerpt = _SPACE_RE.sub(" ", excerpt).strip()
    if len(excerpt) > max_chars:
        excerpt = excerpt[: max_chars - 1].rstrip() + "\u2026"
    return excerpt


def parse_playwright_page_title(payload_text: str) -> str:
    match = re.search(r"- Page Title:\s*(.+)", payload_text)
    return match.group(1).strip() if match else ""


def build_resource_cache_path(query: str, session_id: str | None = None) -> Path:
    safe_query = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "-", query).strip("-")
    safe_query = safe_query[:80] or "resource-search"
    safe_session = re.sub(r"[^A-Za-z0-9._:-]+", "-", session_id or "").strip("-")
    suffix = f"-{safe_session[:24]}" if safe_session else ""
    out_dir = Path(WORKING_DIR) / "exam_bank"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{safe_query}{suffix}-{int(time.time())}.json"


def build_resource_cache_payload(
    context: ResourceQueryContext,
    results: list[RankedResourceResult],
    *,
    excerpt: str = "",
    verified_title: str = "",
    session_id: str | None = None,
) -> dict[str, Any]:
    return {
        "query": context.search_query,
        "raw_text": context.raw_text,
        "year": context.year,
        "stage": context.stage,
        "resource_types": list(context.resource_types),
        "topic_terms": list(context.topic_terms),
        "session_id": session_id or "",
        "verified_title": verified_title,
        "excerpt": excerpt,
        "results": [asdict(item) for item in results],
    }


def format_resource_lookup_response(
    context: ResourceQueryContext,
    results: list[RankedResourceResult],
    *,
    excerpt: str = "",
    verified_title: str = "",
) -> str:
    labels = [
        _TYPE_LABELS[key]
        for key in context.resource_types
        if key in _TYPE_LABELS
    ] or ["\u5b66\u4e60\u8d44\u6e90"]
    lines = [f"\u6211\u5148\u5e2e\u4f60\u67e5\u4e86\u201c{context.raw_text}\u201d\u76f8\u5173\u7684{'\u3001'.join(labels)}\u3002"]
    if verified_title:
        lines.append(f"\u5df2\u9a8c\u8bc1\u9875\u9762\u6807\u9898\uff1a{verified_title}")
    if excerpt:
        lines.append(f"\u9996\u6761\u7ed3\u679c\u6458\u8981\uff1a{excerpt}")

    for idx, item in enumerate(results[:3], 1):
        lines.append(f"{idx}. {item.title}")
        lines.append(f"\u6765\u6e90\uff1a{item.source_host}")
        lines.append(f"\u94fe\u63a5\uff1a{item.url}")
        if item.matched_terms:
            lines.append(f"\u5339\u914d\u70b9\uff1a{' / '.join(item.matched_terms)}")
        if item.snippet:
            snippet = _SPACE_RE.sub(" ", item.snippet).strip()
            if len(snippet) > 120:
                snippet = snippet[:119].rstrip() + "\u2026"
            lines.append(f"\u8bf4\u660e\uff1a{snippet}")

    lines.append("\u5982\u679c\u4f60\u8981\uff0c\u6211\u53ef\u4ee5\u7ee7\u7eed\u5e2e\u4f60\u7b5b\u6210\uff1a\u771f\u9898 / \u89c6\u9891 / \u6559\u8f85 / PDF \u7535\u5b50\u7248\u3002")
    return "\n".join(lines)
