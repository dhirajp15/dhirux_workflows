# dhirux_workflows

Strands-based orchestration package for Dhirux AI.

## Goal
- Keep agentic code isolated from Flask feature modules.
- Route text generation through the existing Qwen chat worker path so GPU mutex behavior is preserved.

## Entry points
- `runtime.py`: lazy Strands imports and agent construction.
- `qwen_worker_model.py`: custom model provider wrapper that uses `worker_manager.stream_chat`.
- `service.py`: service facade used by Flask routes.
- `tools.py`: workflow tools (includes `current_time_utc`).

## API route
- `POST /api/agentic/chat`
- `GET /api/agentic/health`
