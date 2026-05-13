"""Transcript parser; dispatches between local Ollama, OpenAI, and Anthropic.

Backend choice (setting `parser_backend`):
    local      → Ollama only; never call cloud. Raises on Ollama failure.
    openai     → OpenAI only (gpt-4o-mini).
    anthropic  → Anthropic Claude Haiku only.
    auto       → Try Ollama first; on any error, fall through to OpenAI then
                 Anthropic (whichever has a key).
    none       → Skip parsing, return raw transcript as body.

Default is `auto` so the app prefers local models but stays useful when the
local stack is offline.
"""

from __future__ import annotations

import json
import os

from .db import db_get_setting
from .ollama_parse import parse_transcript_locally
from .anthropic_parse import parse_transcript_with_anthropic


def _stub(transcript: str) -> dict:
    return {"type": "note", "title": "", "body": transcript, "tags": "", "priority": "normal"}


def _openai_parse(transcript: str) -> dict:
    api_key = (os.getenv("OPENAI_API_KEY", "").strip()
               or (db_get_setting("openai_api_key", "") or "").strip())
    if not api_key:
        return _stub(transcript)
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """Parse the following voice transcript into structured note/task data.
Return a JSON object with these fields:
- type: "note" or "task" (default "note")
- title: a short descriptive title (generate one from the content if not explicitly stated)
- body: the main content/body text (everything that isn't a field directive)
- tags: comma-separated relevant tags (infer from context if not explicitly stated)
- priority: "low", "normal", or "high" (default "normal")

The user may explicitly say things like "title is ...", "tags are ...", "priority is high",
"this is a task". They may also just speak naturally; in that case generate a concise title,
put everything in the body, infer 1-3 relevant tags, and infer priority from urgency cues.

Return ONLY valid JSON, no markdown fences.""",
            },
            {"role": "user", "content": transcript},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    try:
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return _stub(transcript)


def parse_transcript_with_ai(transcript: str) -> dict:
    backend = (db_get_setting("parser_backend", "auto") or "auto").lower()
    ollama_model = db_get_setting("ollama_model", "")
    ollama_url = db_get_setting("ollama_base_url", "")

    if backend == "none":
        return _stub(transcript)

    if backend == "openai":
        return _openai_parse(transcript)

    if backend == "anthropic":
        try:
            return parse_transcript_with_anthropic(transcript)
        except Exception:
            return _stub(transcript)

    if backend == "local":
        try:
            return parse_transcript_locally(transcript, model=ollama_model, base_url=ollama_url)
        except Exception:
            return _stub(transcript)

    # backend == "auto" or anything unrecognised
    # Try local first, then OpenAI if its key is reachable, then Anthropic.
    try:
        return parse_transcript_locally(transcript, model=ollama_model, base_url=ollama_url)
    except Exception:
        pass
    openai_key = (os.getenv("OPENAI_API_KEY", "").strip()
                  or (db_get_setting("openai_api_key", "") or "").strip())
    if openai_key:
        try:
            return _openai_parse(transcript)
        except Exception:
            pass
    anthropic_key = (os.getenv("ANTHROPIC_API_KEY", "").strip()
                     or (db_get_setting("anthropic_api_key", "") or "").strip())
    if anthropic_key:
        try:
            return parse_transcript_with_anthropic(transcript)
        except Exception:
            pass
    return _stub(transcript)
