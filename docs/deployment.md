# Deployment

Three ways to run Voice Notes, ranked by who they're for.

## 1. Pre-built installer (most users)

Released artifacts for each tag at `https://github.com/Agenius-AI-Labs/voice-notes-desktop/releases`.

### Windows

- File: `VoiceNotesDesktop-<version>-windows.exe` (~280-350 MB).
- Double-click. Windows SmartScreen warns because we don't have a code-signing certificate. Click "More info" → "Run anyway".
- The installer or the bundled exe handles the rest. Windows will prompt for microphone permission on first capture.
- **Uninstall:** Settings → Apps → Voice Notes Desktop → Uninstall.

### macOS

- File: `VoiceNotesDesktop-<version>.dmg` (universal arm64 + x86_64).
- Open the DMG and drag the app into Applications.
- First launch: Gatekeeper blocks because we don't have an Apple Developer signing cert yet. Right-click the app → Open → confirm.
- macOS will prompt for microphone permission on first capture (System Settings → Privacy & Security → Microphone).
- **Uninstall:** drag the app to Trash. Per-user data lives at `~/Library/Application Support/voice-notes/`.

### Linux

- File: `VoiceNotesDesktop-<version>.AppImage` (x86_64).
- `chmod +x VoiceNotesDesktop-*.AppImage && ./VoiceNotesDesktop-*.AppImage`.
- Requires PulseAudio or PipeWire for mic capture (default on Ubuntu, Fedora, Arch, etc.).
- Requires `libxcb`, `libglib`, etc. Most modern distros have these pre-installed; if not, your package manager will surface the missing libs.
- **Uninstall:** delete the AppImage. Per-user data lives at `~/.local/share/voice-notes/` (or `$XDG_DATA_HOME/voice-notes/`).

## 2. pip install (developers and Python users)

```bash
pip install voice-notes-desktop
voice-notes
```

For local development:
```bash
git clone https://github.com/Agenius-AI-Labs/voice-notes-desktop.git
cd voice-notes-desktop
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Unix:     source .venv/bin/activate
pip install -e ".[all,dev]"
voice-notes
```

Optional extras:
- `voice-notes-desktop[wakeword]` — adds openWakeWord (Active Listening). Default-included with `[all]`.
- `voice-notes-desktop[openai]` — adds the OpenAI client (cloud AI parsing).
- `voice-notes-desktop[dev]` — adds ruff, pytest, pytest-qt, pillow (for building icons).

## 3. docker-compose for supporting services

The desktop app stays native. Docker is for the supporting services some users want to self-host. The most common is a local LLM via [Ollama](https://ollama.com).

```yaml
# docker-compose.yml (in the repo root, ship in a later release)
services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
volumes:
  ollama-data:
```

Then in Voice Notes → Settings → AI parsing → pick "Ollama (local)", set base URL to `http://localhost:11434`.

If you'd rather not run Docker, Ollama installs as a native app on Windows / macOS / Linux from [ollama.com](https://ollama.com). The app talks to it over HTTP either way.

## Where your data lives

| OS | Path |
|---|---|
| Windows | `%APPDATA%\voice-notes\` |
| macOS | `~/Library/Application Support/voice-notes/` |
| Linux | `$XDG_DATA_HOME/voice-notes/` (defaults to `~/.local/share/voice-notes/`) |

Override with `VOICE_NOTES_DATA_DIR=/some/path` if you want portable installs (e.g., on a USB drive).

Contents:
- `voice_notes.db` — SQLite with all your notes, tasks, todos, and settings.
- WAL files alongside (created during writes, removed on close).
- `scratch/` — short-lived WAV captures, removed after each transcription.
- `voice-notes.log` — rotating app log (1 MB × 3 backups).

The Whisper model cache lives in `~/.cache/huggingface/hub/` (faster-whisper default), separate from app data. Delete it to force re-download.

## API keys

OpenAI / Anthropic API keys are stored in your OS keyring under the service name `voice-notes-desktop`:

| OS | Backing store |
|---|---|
| Windows | Credential Manager |
| macOS | Keychain |
| Linux | Secret Service (GNOME Keyring, KWallet via D-Bus) |

If no keyring backend is available (a headless Linux box, for example), the keys fall back to the SQLite `settings` table. Read precedence in the parser modules is: environment variable → keyring → DB. Setting `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in your shell always wins.

To delete a stored key:
- macOS: open Keychain Access, find `voice-notes-desktop`, delete the entry.
- Windows: `Credential Manager` → Web Credentials or Generic Credentials → search for `voice-notes-desktop`.
- Linux: `seahorse` (GNOME Keyring GUI) or `secret-tool clear service voice-notes-desktop account openai`.

Or use the Settings dialog in the app: clear the field and Save.

## GPU acceleration (optional)

If you have an Nvidia GPU and want 10-30x faster transcription:

1. Install Nvidia drivers (most modern setups already have them).
2. Install CUDA Toolkit 12 and cuDNN 9 from [nvidia.com/cuda-downloads](https://developer.nvidia.com/cuda-downloads).
3. Restart. Launch Voice Notes. Status after a transcription should read `Transcribed in 423 ms (cuda/float16)`.

If you see `cpu/int8` instead, CUDA isn't reachable from Python. Common causes:
- `cudnn` DLLs not on PATH (Windows).
- CUDA Toolkit 11 instead of 12 (faster-whisper 1.x needs 12).
- Missing `libcudnn8.so` symlinks (Linux).

No GPU? You're on `cpu/int8` and that's fine for `base.en` or smaller models. On a recent laptop you'll get ~1-2x realtime, which is fine for short clips.

## AI parsing (optional)

Three options, set in Settings → AI parsing:

| Backend | Network? | Cost | Setup |
|---|---|---|---|
| None | No | Free | Default. Raw transcript saves as-is. |
| Ollama | Local only | Free | Install Ollama (native or Docker), `ollama pull llama3.2`, set base URL in Settings. |
| OpenAI | Cloud | ~$0.0001/transcript with gpt-4o-mini | Paste API key in Settings. |

`auto` mode tries Ollama first and falls back to OpenAI. Good for "I want local but cloud as backup".

## Custom wake words

See [custom-wake-word.md](custom-wake-word.md). Short version: train a `.onnx` in the openWakeWord Colab notebook, drop the file path into Settings → Active Listening → Custom model file.
