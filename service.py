"""Service facade for agentic workflows."""

from __future__ import annotations

from collections.abc import Generator

from . import config as agentic_config
from .runtime import is_strands_available, run_agent_text, stream_agent_text
import worker_manager


class AgenticService:
    """Thin service boundary used by Flask routes."""

    def enabled(self) -> bool:
        return agentic_config.AGENTIC_ENABLED

    def ready(self) -> bool:
        return self.enabled() and is_strands_available()

    @staticmethod
    def _english_only_input(message: str) -> str:
        return f"{message}\n\nPolicy reminder: respond only in English."

    def chat(self, message: str, session_id: str) -> str:
        if not self.enabled():
            raise RuntimeError("Agentic workflows are disabled (AGENTIC_ENABLED=0).")
        if self.ready():
            return run_agent_text(message=message, session_id=session_id)
        if agentic_config.AGENTIC_ALLOW_CLASSIC_FALLBACK:
            return worker_manager.dispatch_chat(self._english_only_input(message), session_id)
        raise RuntimeError(
            "Agentic mode requires official Strands SDK module 'strands', but it is unavailable."
        )

    def stream_chat(self, message: str, session_id: str) -> Generator[str, None, None]:
        if not self.enabled():
            raise RuntimeError("Agentic workflows are disabled (AGENTIC_ENABLED=0).")
        if self.ready():
            yield from stream_agent_text(message=message, session_id=session_id)
            return
        if agentic_config.AGENTIC_ALLOW_CLASSIC_FALLBACK:
            for token in worker_manager.stream_chat(self._english_only_input(message), session_id):
                yield token
            return
        raise RuntimeError(
            "Agentic mode requires official Strands SDK module 'strands', but it is unavailable."
        )
