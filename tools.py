"""Agentic tools for dhirux_workflows."""

from __future__ import annotations

from datetime import datetime, timezone

from strands.tools import tool


@tool
def current_time_utc() -> dict[str, str]:
    """Return the current time in UTC."""
    now_utc = datetime.now(timezone.utc)
    return {
        "utc": now_utc.strftime("%Y-%m-%d %H:%M:%S %Z"),
    }
