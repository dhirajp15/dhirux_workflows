"""Custom Strands model provider backed by the existing Qwen worker queue."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterable, Dict, List

import worker_manager


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, dict) and "text" in block:
                parts.append(str(block.get("text", "")))
        return "\n".join(p for p in parts if p).strip()
    return str(content).strip()


def _last_user_message(messages: List[Dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return _extract_text(msg.get("content", ""))
    return ""


@dataclass
class QwenWorkerModel:
    """Route model execution through the existing worker_manager chat mutex path."""

    model_id: str = "local-qwen-worker"
    _config: Dict[str, Any] = field(default_factory=dict)

    def get_config(self) -> Dict[str, Any]:
        return {"model_id": self.model_id, **self._config}

    def update_config(self, **kwargs: Any) -> None:
        self._config.update(kwargs)

    async def stream(
        self,
        messages: List[Dict[str, Any]],
        tool_specs: List[Dict[str, Any]] | None = None,
        system_prompt: str | None = None,
        *,
        tool_choice: Dict[str, Any] | None = None,
        system_prompt_content: List[Dict[str, Any]] | None = None,
        invocation_state: Dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[Dict[str, Any]]:
        del tool_specs, system_prompt, tool_choice, system_prompt_content, invocation_state

        invocation_state = kwargs.get("invocation_state") or {}
        session_id = str(invocation_state.get("session_id") or kwargs.get("session_id") or "agentic-default")
        prompt = _last_user_message(messages)
        if not prompt:
            yield {"messageStart": {"role": "assistant"}}
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
            yield {"metadata": {"usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}, "metrics": {"latencyMs": 0}}}
            return

        t0 = time.time()
        out = ""
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {}}}
        for token in worker_manager.stream_chat(prompt, session_id):
            out += token
            yield {"contentBlockDelta": {"delta": {"text": token}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield {
            "metadata": {
                "usage": {
                    "inputTokens": max(1, len(prompt.split())),
                    "outputTokens": max(1, len(out.split())) if out.strip() else 0,
                    "totalTokens": max(1, len(prompt.split())) + (max(1, len(out.split())) if out.strip() else 0),
                },
                "metrics": {"latencyMs": int((time.time() - t0) * 1000)},
            }
        }
