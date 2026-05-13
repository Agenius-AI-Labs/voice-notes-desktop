# Voice Notes Desktop

> Talk to your computer. Get organized text. Stays on your machine.

A voice-first scratchpad for Windows, macOS, and Linux. Push-to-talk dictation, always-listening wake words, local speech-to-text (Whisper), optional AI parsing (Ollama or OpenAI). Quick todos in a right-side pane. A scratchpad workspace for fire-and-forget transcripts you paste elsewhere.

Local-first by default. Your voice doesn't leave the machine unless you give it an OpenAI key.

<p align="center">
  <img src="docs/screenshots/hero.png" alt="Voice Notes Desktop screenshot" width="900">
</p>

## Install

### Windows
1. Download `VoiceNotesDesktop-<version>-windows.exe` from [Releases](https://github.com/Agenius-AI-Labs/voice-notes-desktop/releases).
2. Double-click. SmartScreen warns; click "More info" → "Run anyway" (we don't have a code-signing cert yet).
3. Allow microphone access when Windows prompts.
4. The first-run wizard downloads the speech-to-text model (~75 MB) so your first mic click is instant.

### macOS
1. Download `VoiceNotesDesktop-<version>.dmg` from [Releases](https://github.com/Agenius-AI-Labs/voice-notes-desktop/releases).
2. Drag to Applications.
3. First launch: Gatekeeper may complain; right-click → Open → confirm (we aren't notarized yet).
4. Same first-run wizard.

### Linux
1. Download `VoiceNotesDesktop-<version>.AppImage`.
2. `chmod +x VoiceNotesDesktop-*.AppImage` and run it.
3. PulseAudio or PipeWire is required for mic capture.

### From source (developers)

```bash
git clone https://github.com/Agenius-AI-Labs/voice-notes-desktop.git
cd voice-notes-desktop
pip install -e ".[all]"
voice-notes
```

Or skip the install and run the package directly: `python -m voice_notes`.

Requires Python 3.10+, a microphone, and ~500 MB free disk for the app plus cached models.

## Features

- **Push-to-talk** in the Capture workspace. Click the mic, speak, body fills as soon as transcription returns. AI parses out title / tags / priority / type in a second pass without blocking the UI.
- **Active Listening** with a wake word (default: `hey_jarvis`). Say the phrase, dictate, app auto-stops on silence.
- **Quick Note workspace** for fire-and-forget transcripts. No DB writes, no parsing. Talk, copy, clear.
- **Quick Todo pane** on the right. Type or say `"quick todo: water the plants"` and it lands in the running todo list. Check off items as you go.
- **Local speech-to-text** via [faster-whisper](https://github.com/SYSTRAN/faster-whisper). Auto-detects CUDA for GPU acceleration (10-30x realtime on a recent Nvidia card). Falls back to CPU.
- **Optional AI parsing** via local [Ollama](https://ollama.com) or OpenAI's gpt-4o-mini. Or none, if you just want raw transcripts.
- **Custom wake words** via [openWakeWord](https://github.com/dscripka/openWakeWord). Train your own phrase in Colab, drop the `.onnx` into Settings.
- **Themed UI** in PySide6: dark, light, and cyberpunk. Inter + JetBrains Mono.

## How it works

Three workspaces plus a persistent right-side pane:

| Workspace | What it does |
|---|---|
| Capture | Voice or typed input, AI-parsed into structured notes/tasks, saved to SQLite. |
| Quick Note | Voice or typed scratchpad. Transcript appends with each take. Copy or Clear. Nothing persists. |
| Tasks | List of saved tasks. Click to edit. |
| Notes | List of saved notes. Click to edit. |
| Quick Todos pane | Right-side. Add via text or voice ("quick todo: ..."). Check off when done. |

## Custom wake words: safety note

The "Custom model file" setting in Settings → Active Listening loads a `.onnx`
or `.tflite` file through onnxruntime. Only load files you trained yourself
(via the [openWakeWord Colab notebook](https://github.com/dscripka/openWakeWord/blob/main/notebooks/automatic_model_training.ipynb))
or downloaded from [openWakeWord's official model zoo](https://github.com/dscripka/openWakeWord).
A malicious `.onnx` file from an untrusted source could exploit a future
onnxruntime vulnerability.

## Privacy

- Speech-to-text runs locally. No audio leaves your machine.
- AI parsing is **off by default**. Enable Ollama for local LLM, or OpenAI for cloud. Skip both for raw transcripts.
- No telemetry. The app makes one network call on first launch: downloading the Whisper model from Hugging Face Hub. After that, fully offline-capable.
- Your data lives in your OS's standard user-data location (see [Deployment](docs/deployment.md)). Delete the folder to delete everything.

## Documentation

- [Architecture](docs/architecture.md) — signal flow, threading, schema.
- [Deployment](docs/deployment.md) — install paths in depth, where data lives, GPU setup.
- [Custom wake words](docs/custom-wake-word.md) — train your own phrase via Colab.
- [Contributing](CONTRIBUTING.md) — dev setup, code style, PR process.

## Stack

PySide6 · faster-whisper · openWakeWord · Pillow · OpenAI / Ollama (optional) · SQLite

## Status

Beta. Daily-driven by the author. APIs may shift between v0.x releases. v1.0 lands once the install paths are stable across all three OSes and the test coverage is meaningful.

## License

MIT. See [LICENSE](LICENSE).

## Acknowledgments

Built on top of excellent open-source work. Particular thanks to:
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) for CTranslate2-backed Whisper inference.
- [openWakeWord](https://github.com/dscripka/openWakeWord) for free, trainable wake-word detection.
- [PySide6](https://doc.qt.io/qtforpython-6/) for the cross-platform UI.

Created by [Michael Frostbutter](https://github.com/Mfrostbutter) under [Agenius AI Labs](https://ageniusailabs.com).
