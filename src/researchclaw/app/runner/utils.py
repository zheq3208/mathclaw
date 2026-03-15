"""Runner utility functions.

Provides environment context building for agent queries and
message conversion utilities.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_env_context(
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    channel: Optional[str] = None,
    working_dir: Optional[str] = None,
    add_hint: bool = True,
) -> str:
    """Build environment context string with current request context.

    This text is prepended to the agent's system prompt so it knows
    about the current session, user, and working directory.

    Args:
        session_id: Current session ID
        user_id: Current user ID
        channel: Current channel name
        working_dir: Working directory path
        add_hint: Whether to add usage hints

    Returns:
        Formatted environment context string
    """
    parts = []
    if session_id is not None:
        parts.append(f"- Current session_id: {session_id}")
    if user_id is not None:
        parts.append(f"- Current user_id: {user_id}")
    if channel is not None:
        parts.append(f"- Current channel: {channel}")
    if working_dir is not None:
        parts.append(f"- Working directory: {working_dir}")

    if add_hint:
        parts.append(
            "- Important hints:\n"
            "  1. When completing tasks, prefer using skills first "
            "(e.g. for scheduled tasks, use cron skill). "
            "For unfamiliar skills, check relevant documentation first.\n"
            "  1.1 When user asks to create/update/delete scheduled jobs, "
            "use cron tools directly (cron_create_job/cron_list_jobs/"
            "cron_get_job/cron_pause_job/cron_resume_job/cron_delete_job/"
            "cron_run_job) instead of replying that scheduling is unsupported.\n"
            "  2. When using write_file to write files, if worried about "
            "overwriting existing content, use read_file first to check, "
            "then use edit_file for partial updates or appending.\n"
            "  3. For math tasks, first normalize the input with tools such as "
            "extract_math_document, inspect_math_media, or normalize_problem_json.\n"
            "  4. For solving and verification, prefer run_math_solve_verify_agent or solve_and_verify_math_problem before trusting a math answer; use sympy_solve_equation, sympy_check_equivalence, and verify_math_solution as exact backstops.\n"
            "  5. In tutoring mode, prefer run_guided_explanation_agent first; then use plan_guided_explanation, compose_guided_explanation_turn, generate_socratic_turn, and choose_hint_level for smaller guided steps.\n"
            "  6. After solving or grading, prefer run_math_weakness_diagnosis_agent or diagnose_math_weakness to diagnose wrong answers, missing steps, and weak prerequisite skills before updating long-term state with "
            "extract_math_knowledge and update_math_mastery.\n"
            "  7. After solving or diagnosing, prefer run_problem_variant_agent or generate_problem_variants to create isomorphic, easier, and harder follow-up practice; then use calibrate_problem_difficulty to sanity-check the level shift.\n"
            "  8. Before ending a teaching turn, prefer using generate_micro_quiz and "
            "grade_micro_quiz to check whether the student can solve 2-3 short items independently.\n"
            "  9. When the user wants spaced review, use schedule_review_reminder, "
            "list_review_reminders, or cancel_review_reminder instead of only suggesting reminders.",
        )

    return (
        "====================\n" + "\n".join(parts) + "\n===================="
    )


def extract_text_from_msg(msg: Any) -> str:
    """Extract text content from various message formats.

    Handles:
    - str content
    - list[dict] content blocks (text, thinking types)
    - Msg objects with .content attribute
    """
    content = getattr(msg, "content", msg)

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                btype = block.get("type", "text")
                if btype == "text":
                    parts.append(block.get("text", ""))
                elif btype == "thinking":
                    pass  # skip thinking blocks
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)

    return str(content) if content else ""


def build_chat_name_from_msgs(msgs: Any) -> str:
    """Build a chat name from the first message content.

    Extracts up to 20 chars from the first user message text as the
    chat display name.
    """
    if not msgs:
        return "New Chat"

    first = msgs[0] if isinstance(msgs, list) else msgs
    text = extract_text_from_msg(first)
    if text:
        return text[:20].strip() or "New Chat"
    return "Media Message"


def merge_request_inputs(requests: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge multiple request inputs into a single request.

    Concatenates input content from all requests while preserving
    the first request's metadata (session_id, user_id, etc.).

    Args:
        requests: List of request dicts with 'input' fields

    Returns:
        Merged request dict
    """
    if not requests:
        return {}
    if len(requests) == 1:
        return requests[0]

    merged = dict(requests[0])
    all_inputs = []
    for req in requests:
        inputs = req.get("input", [])
        if isinstance(inputs, list):
            all_inputs.extend(inputs)
        else:
            all_inputs.append(inputs)

    merged["input"] = all_inputs
    return merged
