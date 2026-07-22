import importlib
import os
from pathlib import Path


class WeeklyReviewConfigurationError(RuntimeError):
    """Raised when weekly-review configuration is invalid or unavailable."""


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
