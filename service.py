"""Service facade for agentic workflows."""

from __future__ import annotations

import re
from collections.abc import Generator

from . import config as agentic_config
from .runtime import _format_time_response, _is_time_query, is_strands_available, run_agent_text, stream_agent_text
import worker_manager


class AgenticService:
    """Thin service boundary used by Flask routes."""

    def enabled(self) -> bool:
        return agentic_config.AGENTIC_ENABLED

    def ready(self) -> bool:
        return self.enabled() and is_strands_available()

    @staticmethod
    def _english_only_input(message: str) -> str:
        return (
            f"{message}\n\n"
            "Policy reminders:\n"
            "- Respond in English only.\n"
            "- If unsure, say: I don't know based on available information.\n"
            "- Do not fabricate facts or profile links.\n"
            "- Do not output URLs unless they are verified tool outputs."
        )

    @staticmethod
    def _needs_external_verification(message: str) -> bool:
        q = message.lower()
        hints = (
            "who is ",
            "search ",
            "profile",
            "twitter",
            "linkedin",
            "instagram",
            "facebook",
            "website",
            "url",
            "link",
        )
        return any(h in q for h in hints)

    @staticmethod
    def _verification_block_message() -> str:
        return (
            "I don't know based on available information. "
            "I cannot verify people profiles or external links because no web-search tool is enabled."
        )

    @staticmethod
    def _sanitize_output(text: str) -> str:
        out = (text or "").strip()
        if not out:
            return out

        # Hard language guard: block CJK script output.
        if re.search(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7a3]", out):
            return (
                "I can only respond in English. "
                "Please rephrase your request and I will answer in English."
            )

        # Hard link guard: reject unverified URLs.
        if re.search(r"https?://|www\.", out, flags=re.IGNORECASE):
            return (
                "I don't know based on available information. "
                "I cannot share unverified links."
            )
        return out

    def _stream_with_guards(self, chunks: Generator[str, None, None]) -> Generator[str, None, None]:
        """Yield streaming chunks while enforcing lightweight safety checks."""
        full = ""
        blocked = False
        for token in chunks:
            t = str(token)
            full += t
            if re.search(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7a3]", full):
                yield (
                    "I can only respond in English. "
                    "Please rephrase your request and I will answer in English."
                )
                blocked = True
                break
            if re.search(r"https?://|www\.", full, flags=re.IGNORECASE):
                yield (
                    "I don't know based on available information. "
                    "I cannot share unverified links."
                )
                blocked = True
                break
            yield t
        if blocked:
            return

    def chat(self, message: str, session_id: str) -> str:
        if not self.enabled():
            raise RuntimeError("Agentic workflows are disabled (AGENTIC_ENABLED=0).")
        if _is_time_query(message):
            return _format_time_response(message)
        if self._needs_external_verification(message):
            return self._verification_block_message()
        if self.ready():
            return self._sanitize_output(run_agent_text(message=message, session_id=session_id))
        if agentic_config.AGENTIC_ALLOW_CLASSIC_FALLBACK:
            raw = worker_manager.dispatch_chat(self._english_only_input(message), session_id)
            return self._sanitize_output(raw)
        raise RuntimeError(
            "Agentic mode requires official Strands SDK module 'strands', but it is unavailable."
        )

    def stream_chat(self, message: str, session_id: str) -> Generator[str, None, None]:
        if not self.enabled():
            raise RuntimeError("Agentic workflows are disabled (AGENTIC_ENABLED=0).")
        if _is_time_query(message):
            yield _format_time_response(message)
            return
        if self._needs_external_verification(message):
            yield self._verification_block_message()
            return
        if self.ready():
            yield from self._stream_with_guards(
                stream_agent_text(message=message, session_id=session_id)
            )
            return
        if agentic_config.AGENTIC_ALLOW_CLASSIC_FALLBACK:
            yield from self._stream_with_guards(
                worker_manager.stream_chat(self._english_only_input(message), session_id)
            )
            return
        raise RuntimeError(
            "Agentic mode requires official Strands SDK module 'strands', but it is unavailable."
        )
