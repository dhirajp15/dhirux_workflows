"""Agentic tools for dhirux_workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from strands.tools import tool


@tool
def current_time_utc() -> dict[str, str]:
    """Return the current time in UTC, Beijing, and Denver."""
    now_utc = datetime.now(timezone.utc)
    now_beijing = now_utc.astimezone(ZoneInfo("Asia/Shanghai"))
    now_denver = now_utc.astimezone(ZoneInfo("America/Denver"))
    return {
        "utc": now_utc.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "beijing": now_beijing.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "denver": now_denver.strftime("%Y-%m-%d %H:%M:%S %Z"),
    }
