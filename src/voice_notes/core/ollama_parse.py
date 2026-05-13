"""Local Ollama JSON parser for dictation transcripts.

Calls `<base_url>/api/chat` with `format: "json"` so the model is forced to
emit strict JSON. Default model is qwen2.5:7b-instruct-q5_K_M.

When `base_url` is empty, the parser probes `http://localhost:11434` only.
Configure a non-local Ollama endpoint via Settings if you run it elsewhere.
"""

from __future__ import annotations

import json

import requests

DEFAULT_MODEL = "qwen2.5:7b-instruct-q5_K_M"
DEFAULT_BASE_URLS = ("http://localhost:11434",)
_TIMEOUT_PROBE = 1.5
_TIMEOUT_CHAT = 30.0

_SYSTEM_PROMPT = """Parse the following voice transcript into structured note/task data.
Return a JSON object with these fields:
- type: "note" or "task" (default "note")
- title: a short descriptive title (generate one from the content if not explicitly stated)
- body: the main content/body text (everything that isn't a field directive)
- tags: comma-separated relevant tags (infer from context if not explicitly stated)
- priority: "low", "normal", or "high" (default "normal")

The user may explicitly say things like "title is ...", "tags are ...", "priority is high",
"this is a task". They may also just speak naturally — in that case generate a concise title,
put everything in the body, infer 1-3 relevant tags, and infer priority from urgency cues.

Return ONLY valid JSON, no markdown fences, no commentary, no thinking blocks."""


def _probe(base_url: str) -> bool:
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=_TIMEOUT_PROBE)
        return r.status_code == 200
    except requests.RequestException:
        return False


def _resolve_base(configured: str) -> str | None:
    """Return the first reachable base URL — configured, then defaults."""
    candidates: list[str] = []
    if configured.strip():
        candidates.append(configured.strip().rstrip("/"))
    candidates.extend(DEFAULT_BASE_URLS)
    seen: set[str] = set()
    for url in candidates:
        if url in seen:
            continue
        seen.add(url)
        if _probe(url):
            return url
    return None


def parse_transcript_locally(
    transcript: str,
    model: str = "",
    base_url: str = "",
) -> dict:
    """Send the transcript to Ollama and return a dict in the standard shape.

    Raises RuntimeError on any unrecoverable failure (no endpoint, bad response).
    The caller decides whether to fall through to OpenAI.
    """
    chosen_model = model.strip() or DEFAULT_MODEL
    chosen_base = _resolve_base(base_url)
    if chosen_base is None:
        raise RuntimeError("No Ollama endpoint reachable")

    payload = {
        "model": chosen_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
    }
    try:
        resp = requests.post(
            f"{chosen_base}/api/chat",
            json=payload,
            timeout=_TIMEOUT_CHAT,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc

    if resp.status_code != 200:
        raise RuntimeError(f"Ollama HTTP {resp.status_code}: {resp.text[:160]}")

    try:
        body = resp.json()
        content = body.get("message", {}).get("content", "")
    except ValueError as exc:
        raise RuntimeError(f"Ollama response not JSON: {exc}") from exc

    if not content:
        raise RuntimeError("Ollama returned empty content")

    # Some models prefix with <think>...</think> blocks even with format:json.
    # Strip anything before the first '{'.
    idx = content.find("{")
    if idx > 0:
        content = content[idx:]

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Ollama JSON parse failed: {exc}") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError(f"Ollama returned non-object JSON: {type(parsed).__name__}")
    return parsed
