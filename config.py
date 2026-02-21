"""Configuration for Strands-based workflows."""

from __future__ import annotations

import os


AGENTIC_ENABLED = os.getenv("AGENTIC_ENABLED", "1") == "1"
AGENTIC_SYSTEM_PROMPT = os.getenv(
    "AGENTIC_SYSTEM_PROMPT",
    (
        "You are Dhirux Agentic Workflow Orchestrator. "
        "Use concise, actionable responses and call tools when useful. "
        "You must always respond in English only. Never respond in any other language. "
        "If you do not know a fact, say exactly: 'I don't know based on available information.' "
        "Do not invent people details, organizations, events, or profile links. "
        "Never output any URL unless it came from a verified tool result."
    ),
)
AGENTIC_MODEL_ID = os.getenv("AGENTIC_MODEL_ID", "local-qwen-worker")
AGENTIC_ALLOW_CLASSIC_FALLBACK = os.getenv("AGENTIC_ALLOW_CLASSIC_FALLBACK", "1") == "1"
