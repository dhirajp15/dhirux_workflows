"""Lazy Strands runtime helpers."""

from __future__ import annotations

import asyncio
import queue
import threading
from collections.abc import Generator
from typing import Any, Optional

from . import config as agentic_config
from .qwen_worker_model import QwenWorkerModel
from .tools import current_time_utc
import worker_manager


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
    return f"{message}\n\nPolicy reminder: respond only in English."


def _is_time_query(message: str) -> bool:
    q = message.lower()
    keys = [
        "what time",
        "current time",
        "time now",
        "time in utc",
        "utc time",
        "beijing time",
        "denver time",
    ]
    return any(k in q for k in keys)


def _format_time_response() -> str:
    times = current_time_utc()
    return (
        f"The current time in Beijing is {times['beijing']}. "
        f"Denver is usually 13 to 14 hours behind Beijing depending on daylight saving time, "
        f"and the current time in Denver is {times['denver']}.\n\n"
        "If you need exact live time, please check a reliable online clock or a device set to Mountain Time.\n\n"
        "Which time do you need now: UTC, Beijing, or Denver? "
        "I can also help summarize recent transcripts or run other tasks."
    )


def run_agent_text(message: str, session_id: Optional[str] = None) -> str:
    """Execute one agent turn and return text output."""
    if _is_time_query(message):
        return _format_time_response()
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
        yield _format_time_response()
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
