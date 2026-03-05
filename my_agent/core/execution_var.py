import contextvars
import os

from dotenv import load_dotenv

load_dotenv()


class Secrets:
    INFISICAL_CLIENT_ID = os.environ.get("INFISICAL_CLIENT_ID", "")
    INFISICAL_CLIENT_TOKEN = os.environ.get("INFISICAL_CLIENT_TOKEN", "")
    INFISICAL_PROJECT_ID = os.environ.get("INFISICAL_PROJECT_ID", "")


class Environment:
    ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")


# ---------------------------------------------------------------------------
# Per-request session ID (thread-safe via contextvars)
# ---------------------------------------------------------------------------
_current_session_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_current_session_id", default="default"
)


def set_current_session_id(session_id: str) -> None:
    """Set the session/thread ID for the current async context."""
    _current_session_id.set(session_id)


def get_current_session_id() -> str:
    """Get the session/thread ID for the current async context."""
    return _current_session_id.get()
