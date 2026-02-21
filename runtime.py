"""Lazy Strands runtime helpers."""

from __future__ import annotations

import asyncio
import queue
import re
import threading
from datetime import datetime, timezone
from collections.abc import Generator
from typing import Any, Optional
from zoneinfo import ZoneInfo

from . import config as agentic_config
from .qwen_worker_model import QwenWorkerModel
from .tools import current_time_utc
import worker_manager

_COMMON_TZ_ALIASES: dict[str, str] = {
    "utc": "UTC",
    "gmt": "UTC",
    "zulu": "UTC",
    "denver": "America/Denver",
    "mountain": "America/Denver",
    "mst": "America/Denver",
    "mdt": "America/Denver",
    "new york": "America/New_York",
    "est": "America/New_York",
    "edt": "America/New_York",
    "chicago": "America/Chicago",
    "cst": "America/Chicago",
    "cdt": "America/Chicago",
    "los angeles": "America/Los_Angeles",
    "la": "America/Los_Angeles",
    "pst": "America/Los_Angeles",
    "pdt": "America/Los_Angeles",
    "london": "Europe/London",
    "bst": "Europe/London",
    "paris": "Europe/Paris",
    "berlin": "Europe/Berlin",
    "dubai": "Asia/Dubai",
    "tokyo": "Asia/Tokyo",
    "singapore": "Asia/Singapore",
    "beijing": "Asia/Shanghai",
    "shanghai": "Asia/Shanghai",
    "india": "Asia/Kolkata",
    "ist": "Asia/Kolkata",
}


def is_strands_available() -> bool:
    try:
        import strands
        return hasattr(strands, "Agent")
    except Exception:
        return False


def build_agent() -> Any:
    """Build a Strands agent using the custom local Qwen worker model."""
    try:
        from strands import Agent
    except Exception as exc:
        raise RuntimeError(
            "Strands SDK is unavailable. Install official SDK package that provides module "
            "'strands' (for example from official docs/repo), then restart the app."
        ) from exc

    model = QwenWorkerModel(model_id=agentic_config.AGENTIC_MODEL_ID)
    return Agent(model=model, system_prompt=agentic_config.AGENTIC_SYSTEM_PROMPT, tools=[current_time_utc])


def _english_only_input(message: str) -> str:
    return (
        f"{message}\n\n"
        "Policy reminders:\n"
        "- Respond in English only.\n"
        "- If unsure, say: I don't know based on available information.\n"
        "- Do not fabricate facts or profile links.\n"
        "- Do not output URLs unless they are verified tool outputs."
    )


def _is_time_query(message: str) -> bool:
    q = message.lower().strip()
    q_norm = re.sub(r"[^\w\s]", " ", q)
    q_norm = re.sub(r"\s+", " ", q_norm).strip()
    return bool(re.search(r"\btime\b", q_norm)) or any(k in q_norm for k in ("utc", "gmt", "timezone"))


def _extract_requested_timezone(message: str) -> str | None:
    # 1) IANA style timezone from user text, e.g. "Asia/Tokyo"
    for raw in re.findall(r"\b([A-Za-z]+/[A-Za-z_]+)\b", message):
        tz_name = raw.replace("_", "_")
        try:
            ZoneInfo(tz_name)
            return tz_name
        except Exception:
            pass

    # 2) Common aliases/cities/abbreviations
    q_norm = re.sub(r"[^\w\s/]", " ", message.lower())
    q_norm = re.sub(r"\s+", " ", q_norm).strip()
    for alias, tz_name in sorted(_COMMON_TZ_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", q_norm):
            return tz_name

    return None


def _format_time_response(message: str) -> str:
    times = current_time_utc()
    requested_tz = _extract_requested_timezone(message)

    if requested_tz and requested_tz != "UTC":
        now_utc = datetime.now(timezone.utc)
        local_time = now_utc.astimezone(ZoneInfo(requested_tz)).strftime("%Y-%m-%d %H:%M:%S %Z")
        return (
            f"The current UTC time is {times['utc']}.\n"
            f"The current time in {requested_tz} is {local_time}.\n\n"
            "I can also help summarize recent transcripts or run other tasks."
        )

    if "timezone" in message.lower() and requested_tz is None:
        return (
            f"The current UTC time is {times['utc']}.\n\n"
            "I could not recognize the requested timezone. "
            "Please provide an IANA timezone like `America/Denver` or `Asia/Tokyo`."
        )

    return (
        f"The current UTC time is {times['utc']}.\n\n"
        "If you need exact live time, please check a reliable online clock.\n\n"
        "I can also help summarize recent transcripts or run other tasks."
    )


def run_agent_text(message: str, session_id: Optional[str] = None) -> str:
    """Execute one agent turn and return text output."""
    if _is_time_query(message):
        return _format_time_response(message)
    agent = build_agent()
    kwargs = {"session_id": session_id} if session_id else {}
    result = agent(_english_only_input(message), **kwargs)
    text = getattr(result, "text", None)
    if isinstance(text, str):
        return text
    return str(result)


def stream_agent_text(message: str, session_id: Optional[str] = None) -> Generator[str, None, None]:
    """Execute one agent turn and yield text deltas as they arrive."""
    if _is_time_query(message):
        yield _format_time_response(message)
        return

    if not is_strands_available():
        sid = session_id or "agentic-default"
        for token in worker_manager.stream_chat(_english_only_input(message), sid):
            yield token
        return

    agent = build_agent()
    out_queue: queue.Queue[Any] = queue.Queue()
    done = object()

    async def _run() -> None:
        try:
            state = {"session_id": session_id} if session_id else {}
            async for event in agent.stream_async(_english_only_input(message), invocation_state=state):
                if isinstance(event, dict) and "data" in event:
                    chunk = str(event.get("data", ""))
                    if chunk:
                        out_queue.put(chunk)
        except Exception as exc:
            out_queue.put(f"\n[stream_error] {exc}")
        finally:
            out_queue.put(done)

    def _runner() -> None:
        asyncio.run(_run())

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()

    while True:
        item = out_queue.get()
        if item is done:
            break
        yield str(item)
