import importlib
import json
import os
from pathlib import Path
import sqlite3
from datetime import date, timedelta
from typing import Any, Callable


class WeeklyReviewConfigurationError(RuntimeError):
    """Raised when weekly-review configuration is invalid or unavailable."""


class WeeklyReviewResponseError(ValueError):
    """Raised when the model response is missing required weekly-review fields."""


def _load_dotenv_if_available(env_file: str | None = None) -> None:
    try:
        dotenv_module = importlib.import_module("dotenv")
    except ModuleNotFoundError:
        return

    load_dotenv = getattr(dotenv_module, "load_dotenv", None)
    if load_dotenv is None:
        return

    if env_file is None:
        load_dotenv(override=False)
        return

    load_dotenv(dotenv_path=Path(env_file), override=False)


def load_weekly_review_api_key(*, env_file: str | None = None) -> str:
    _load_dotenv_if_available(env_file)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        return api_key

    raise WeeklyReviewConfigurationError(
        "Weekly review requires ANTHROPIC_API_KEY. Add it to your environment or .env."
    )


def create_anthropic_client(*, env_file: str | None = None):
    api_key = load_weekly_review_api_key(env_file=env_file)
    try:
        anthropic_module = importlib.import_module("anthropic")
    except ModuleNotFoundError as exc:
        raise WeeklyReviewConfigurationError(
            "Weekly review requires the anthropic package. Install it with `python3 -m pip install anthropic`."
        ) from exc

    anthropic_client_class = getattr(anthropic_module, "Anthropic", None)
    if anthropic_client_class is None:
        raise WeeklyReviewConfigurationError(
            "anthropic package is installed but missing Anthropic client."
        )

    return anthropic_client_class(api_key=api_key)


def _extract_text_content(message_response: Any) -> str:
    content_blocks = getattr(message_response, "content", None)
    if not isinstance(content_blocks, list):
        raise WeeklyReviewResponseError("Model response did not include content blocks.")

    text_parts: list[str] = []
    for block in content_blocks:
        text_value = getattr(block, "text", None)
        if isinstance(text_value, str) and text_value.strip():
            text_parts.append(text_value.strip())

    if not text_parts:
        raise WeeklyReviewResponseError("Model response was empty.")

    return "\n".join(text_parts)


def _normalize_model_payload(model_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(model_text)
    except json.JSONDecodeError as exc:
        raise WeeklyReviewResponseError("Model response was not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise WeeklyReviewResponseError("Model response must be a JSON object.")

    assessment = payload.get("assessment")
    if assessment not in {"ahead", "on_track", "behind"}:
        raise WeeklyReviewResponseError(
            "Model response assessment must be one of: ahead, on_track, behind."
        )

    summary_text = payload.get("summary_text")
    if not isinstance(summary_text, str) or not summary_text.strip():
        raise WeeklyReviewResponseError("Model response must include non-empty summary_text.")

    suggestions = payload.get("suggestions")
    if not isinstance(suggestions, list) or not (1 <= len(suggestions) <= 3):
        raise WeeklyReviewResponseError("Model response must include 1 to 3 suggestions.")

    normalized_suggestions: list[str] = []
    for raw_suggestion in suggestions:
        if not isinstance(raw_suggestion, str) or not raw_suggestion.strip():
            raise WeeklyReviewResponseError("Each suggestion must be non-empty text.")
        normalized_suggestions.append(raw_suggestion.strip())

    return {
        "assessment": assessment,
        "summary_text": summary_text.strip(),
        "suggestions": normalized_suggestions,
    }


def _collect_review_context(database_path: str) -> dict[str, Any]:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        goal_row = connection.execute(
            """
            SELECT title, description, target_date, status
            FROM goal
            WHERE id = 1
            """
        ).fetchone()

        entry_rows = connection.execute(
            """
            SELECT id, date, notes, reflection, engagement
            FROM entry
            ORDER BY date
            """
        ).fetchall()
        tag_rows = connection.execute(
            """
            SELECT entry_id, tag
            FROM entry_tag
            ORDER BY tag
            """
        ).fetchall()

        summary_rows = connection.execute(
            """
            SELECT week_start, week_end, assessment, summary_text, created_at
            FROM weekly_summary
            ORDER BY created_at, id
            """
        ).fetchall()
    finally:
        connection.close()

    tags_by_entry_id: dict[int, list[str]] = {}
    for tag_row in tag_rows:
        entry_id = int(tag_row["entry_id"])
        tags_by_entry_id.setdefault(entry_id, []).append(str(tag_row["tag"]))

    entries: list[dict[str, Any]] = []
    for entry_row in entry_rows:
        entry_id = int(entry_row["id"])
        entries.append(
            {
                "date": str(entry_row["date"]),
                "notes": str(entry_row["notes"]),
                "reflection": str(entry_row["reflection"]),
                "engagement": int(entry_row["engagement"]),
                "tags": tags_by_entry_id.get(entry_id, []),
            }
        )

    prior_summaries: list[dict[str, str]] = []
    for summary_row in summary_rows:
        prior_summaries.append(
            {
                "week_start": str(summary_row["week_start"]),
                "week_end": str(summary_row["week_end"]),
                "assessment": str(summary_row["assessment"]),
                "summary_text": str(summary_row["summary_text"]),
                "created_at": str(summary_row["created_at"]),
            }
        )

    goal = {
        "title": "",
        "description": "",
        "target_date": None,
        "status": "active",
    }
    if goal_row is not None:
        goal = {
            "title": str(goal_row["title"]),
            "description": str(goal_row["description"]),
            "target_date": str(goal_row["target_date"]) if goal_row["target_date"] else None,
            "status": str(goal_row["status"]),
        }

    return {
        "goal": goal,
        "entries": entries,
        "prior_summaries": prior_summaries,
    }


def generate_weekly_review(
    *,
    database_path: str,
    client_factory: Callable[[], Any] = create_anthropic_client,
    run_day: date | None = None,
    model: str = "claude-sonnet-4-5",
) -> dict[str, Any]:
    effective_run_day = run_day or date.today()
    week_end = effective_run_day
    week_start = effective_run_day - timedelta(days=6)

    review_context = _collect_review_context(database_path)
    prompt_payload = {
        "week_window": {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
        },
        "goal": review_context["goal"],
        "entries": review_context["entries"],
        "prior_weekly_summaries": review_context["prior_summaries"],
    }

    prompt = (
        "You are a weekly productivity reviewer.\n"
        "Assess whether the user is ahead, on_track, or behind based on engagement trends and reflections.\n"
        "Propose, do not decide: suggestions must be optional and non-directive.\n"
        "Do not scold and do not give false reassurance.\n"
        "Return ONLY valid JSON with this exact shape:\n"
        '{"assessment":"ahead|on_track|behind","summary_text":"...","suggestions":["...", "..."]}\n'
        "Suggestions must be 1-3 short, concrete goal tweaks.\n"
        f"Review context JSON:\n{json.dumps(prompt_payload, ensure_ascii=True)}"
    )

    client = client_factory()
    message_response = client.messages.create(
        model=model,
        max_tokens=700,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    response_text = _extract_text_content(message_response)
    normalized_payload = _normalize_model_payload(response_text)
    normalized_payload["week_start"] = week_start.isoformat()
    normalized_payload["week_end"] = week_end.isoformat()
    return normalized_payload
