"""Anthropic Claude backend for transcript parsing.

Mirrors the OpenAI path: same system prompt, returns a dict with
type/title/body/tags/priority. Uses Claude Haiku for low-cost, low-latency
parsing. Returns a stub on auth failure so the app stays usable.
"""

from __future__ import annotations

import json
import os
import re

from .db import db_get_setting

_SYSTEM_PROMPT = """Parse the following voice transcript into structured note/task data.
Return a JSON object with these fields:
- type: "note" or "task" (default "note")
- title: a short descriptive title (generate one from the content if not explicitly stated)
- body: the main content/body text (everything that isn't a field directive)
- tags: comma-separated relevant tags (infer from context if not explicitly stated)
- priority: "low", "normal", or "high" (default "normal")

The user may explicitly say things like "title is ...", "tags are ...", "priority is high",
"this is a task". They may also just speak naturally; in that case generate a concise title,
put everything in the body, infer 1-3 relevant tags, and infer priority from urgency cues.

Return ONLY valid JSON, no markdown fences, no prose."""


def _stub(transcript: str) -> dict:
    return {
        "type": "note",
        "title": "",
        "body": transcript,
        "tags": "",
        "priority": "normal",
    }


def _extract_json(text: str) -> str:
    """Strip ```json fences or trailing text if the model added any.

    Defensive even though we ask for raw JSON only. Returns the first
    JSON-looking substring; caller does json.loads.
    """
    text = text.strip()
    if text.startswith("```"):
        # Drop the opening fence and optional language tag, drop the closing fence.
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_transcript_with_anthropic(transcript: str, model: str = "claude-haiku-4-5") -> dict:
    """Call Claude Haiku to parse the transcript. Falls back to stub on any error."""
    api_key = (os.getenv("ANTHROPIC_API_KEY", "").strip()
               or (db_get_setting("anthropic_api_key", "") or "").strip())
    if not api_key:
        return _stub(transcript)

    try:
        from anthropic import Anthropic
    except ImportError:
        # Missing optional dependency; caller treats this as parser failure.
        raise RuntimeError(
            "anthropic SDK not installed. Install via "
            "`pip install voice-notes-desktop[anthropic]` or `pip install anthropic`."
        )

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=512,
        temperature=0.1,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": transcript}],
    )

    if not resp.content:
        return _stub(transcript)
    raw = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
    if not raw.strip():
        return _stub(transcript)

    try:
        return json.loads(_extract_json(raw))
    except Exception:
        return _stub(transcript)
