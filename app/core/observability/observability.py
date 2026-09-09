"""Central LangSmith configuration."""

import atexit

from app.core.config import get_settings


_configured = False


def _wait_for_traces() -> None:
    """Deliver queued traces before a short-lived process exits."""
    try:
        from langchain_core.tracers.langchain import wait_for_all_tracers

        wait_for_all_tracers()
    except Exception:
        # Observability must never prevent application shutdown.
        pass


def configure_langsmith() -> None:
    global _configured

    if _configured:
        return

    settings = get_settings()

    # If tracing is disabled in settings, nothing to register.
    if not settings.langchain_tracing_v2:
        _configured = True
        return

    # Some third-party libraries still read environment variables, so set
    # them from the canonical Settings values if they are not already set.
    import os

    os.environ.setdefault("LANGCHAIN_TRACING_V2", str(settings.langchain_tracing_v2).lower())
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.langchain_api_key)
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.langchain_project)

    atexit.register(_wait_for_traces)
    _configured = True