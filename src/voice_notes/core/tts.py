"""ElevenLabs TTS — voice list + audio generation.

Lifted verbatim from voice_notes_desktop_v2.py lines 468–505.
"""

from __future__ import annotations

import os
from urllib.parse import quote

import numpy as np

_VOICE_CACHE: dict[str, list[dict] | None] = {"voices": None}


def el_get_voices() -> list[dict]:
    cached = _VOICE_CACHE["voices"]
    if cached is not None:
        return cached
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        return []
    import requests
    resp = requests.get(
        "https://api.elevenlabs.io/v1/voices",
        headers={"xi-api-key": api_key},
        timeout=10,
    )
    if resp.status_code != 200:
        return []
    data = resp.json()
    voices = [
        {"voice_id": v["voice_id"], "name": v["name"]}
        for v in data.get("voices", [])
    ]
    _VOICE_CACHE["voices"] = voices
    return voices


def el_generate_audio(text: str, voice_id: str) -> np.ndarray:
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY not set")
    import requests
    safe_voice = quote(voice_id, safe="")
    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{safe_voice}?output_format=pcm_16000",
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={"text": text, "model_id": "eleven_multilingual_v2"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"ElevenLabs API error {resp.status_code}: {resp.text[:200]}")
    return np.frombuffer(resp.content, dtype=np.int16).astype(np.float32) / 32768.0
