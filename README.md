# AgeniusNote

[![Latest release](https://img.shields.io/github/v/release/Agenius-AI-Labs/agenius-note?sort=semver&color=38bdf8&label=download)](https://github.com/Agenius-AI-Labs/agenius-note/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-22d3ee.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Platforms](https://img.shields.io/badge/platforms-Win%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#install)

> Talk to your computer. Get organized text. Stays on your machine.

A voice-first scratchpad for Windows, macOS, and Linux. Push-to-talk dictation, always-listening wake words, local speech-to-text (Whisper), optional AI parsing (Ollama, OpenAI, or Anthropic Claude). Quick todos in a right-side pane. A scratchpad workspace for fire-and-forget transcripts you paste elsewhere.

Local-first by default. Your voice doesn't leave the machine unless you give it a cloud key.

> Previously released as **voice-notes-desktop**. Renamed to AgeniusNote in v0.2.0. Existing installs auto-migrate their data and keyring entries on first launch.

<p align="center">
  <img src="docs/screenshots/hero.png" alt="AgeniusNote screenshot" width="900">
</p>

## Why this exists

AgeniusNote started as a tool the author kept wanting and not finding. Three jobs it was built to do:

**1. Capture tasks, notes, and short-term reminders without breaking flow.**
You're heads-down in something. A reminder hits you. Today the options are: stop, open Notion / Things / Todoist / a sticky note, type, alt-tab back. Or you swallow it and hope you remember. AgeniusNote is one click of a mic (or the wake word), 5 seconds of speech, done. The transcript is saved, the AI tags it if you let it, and you're back in the flow.

**2. Be a paste-buffer between AI tools.**
If you work with multiple LLM chat windows open (Claude in one, ChatGPT in another, a local Ollama somewhere else), you spend a lot of time copying responses around, summarizing them out loud to yourself, then re-typing them into the next prompt. The **Quick Note panel** (right column, below your todos) is purpose-built for this: dictate freely, the transcript appends with each take, click **Copy**, paste anywhere. No DB writes, no AI parsing, no friction. Talk a thought through, hit Copy, paste the verbal sketch into your next prompt, move on.

**3. Brain-dump while exploring something new.**
You're poking at a new app or codebase. You'd usually narrate to yourself anyway: "OK, this button does X, but when I click it I get Y, and that's weird because the docs say Z." AgeniusNote lets you actually capture that stream-of-consciousness while your hands stay on the mouse. Active Listening with a wake word means you don't even break visual focus. Later, the transcript is a step-by-step record of what you tried and what surprised you, which is gold for writing it up or filing a bug.

Built by an engineer who runs all three of these workflows daily. The design choices reflect that: keystrokes hidden behind a mic press, parsing optional and replaceable, your data on disk where you can grep it, no telemetry, MIT license.

## Install

### Windows
1. Download `AgeniusNote-<version>-windows.zip` from [Releases](https://github.com/Agenius-AI-Labs/agenius-note/releases).
2. Unzip and run `agenius-note.exe`. SmartScreen warns; click "More info" then "Run anyway" (we don't have a code-signing cert yet).
3. Allow microphone access when Windows prompts.
4. The first-run wizard downloads the speech-to-text model (~75 MB) so your first mic click is instant.

### macOS
1. Download `AgeniusNote-<version>-macos.zip` from [Releases](https://github.com/Agenius-AI-Labs/agenius-note/releases).
2. Unzip, drag `agenius-note.app` to Applications.
3. First launch: Gatekeeper may complain; right-click then Open then confirm (we aren't notarized yet).
4. Same first-run wizard.

### Linux
1. Download `AgeniusNote-<version>-linux.tar.gz`.
2. Extract and run `./agenius-note/agenius-note`.
3. PulseAudio or PipeWire is required for mic capture.

### From source (developers)

```bash
git clone https://github.com/Agenius-AI-Labs/agenius-note.git
cd agenius-note
pip install -e ".[all]"
agenius-note
```

Or skip the install and run the package directly: `python -m agenius_note`.

Requires Python 3.10+, a microphone, and ~500 MB free disk for the app plus cached models.

## Features

- **Push-to-talk** in the Capture workspace. Click the mic, speak, body fills as soon as transcription returns. AI parses out title / tags / priority / type in a second pass without blocking the UI.
- **Active Listening** with a wake word (default: `hey_jarvis`). Say the phrase, dictate, app auto-stops on silence.
- **Quick Note panel** in the right column (under your todos). Fire-and-forget transcripts. No DB writes, no parsing. Talk, copy, clear. When the panel has focus, Active Listening transcripts land there raw instead of in Capture.
- **Quick Todo pane** on the right. Type or say `"quick todo: water the plants"` and it lands in the running todo list. Check off items as you go.
- **Local speech-to-text** via [faster-whisper](https://github.com/SYSTRAN/faster-whisper). Auto-detects CUDA for GPU acceleration (10-30x realtime on a recent Nvidia card). Falls back to CPU.
- **Optional AI parsing** via local [Ollama](https://ollama.com), OpenAI's gpt-4o-mini, or Anthropic Claude Haiku. Or none, if you just want raw transcripts.
- **Custom wake words** via [openWakeWord](https://github.com/dscripka/openWakeWord). Train your own phrase in Colab, drop the `.onnx` into Settings.
- **Themed UI** in PySide6: dark, light, and cyberpunk. Inter + JetBrains Mono.

## How it works

Three workspaces plus a persistent right-side column:

| Surface | What it does |
|---|---|
| Capture | Voice or typed input, AI-parsed into structured notes/tasks, saved to SQLite. |
| Tasks | List of saved tasks. Click to edit. |
| Notes | List of saved notes. Click to edit. |
| Right column (top half) | Quick Todos pane. Add via text or voice ("quick todo: ..."). Check off when done. |
| Right column (bottom half) | Quick Note panel. Voice or typed scratchpad. Transcript appends with each take. Copy or Clear. Nothing persists. |

## Custom wake words: safety note

The "Custom model file" setting in Settings then Active Listening loads a `.onnx`
or `.tflite` file through onnxruntime. Only load files you trained yourself
(via the [openWakeWord Colab notebook](https://github.com/dscripka/openWakeWord/blob/main/notebooks/automatic_model_training.ipynb))
or downloaded from [openWakeWord's official model zoo](https://github.com/dscripka/openWakeWord).
A malicious `.onnx` file from an untrusted source could exploit a future
onnxruntime vulnerability.

## Privacy

- Speech-to-text runs locally. No audio leaves your machine.
- AI parsing is **off by default**. Enable Ollama for local LLM, or OpenAI / Anthropic for cloud. Skip all three for raw transcripts.
- No telemetry. The app makes one network call on first launch: downloading the Whisper model from Hugging Face Hub. After that, fully offline-capable.
- Your data lives in your OS's standard user-data location (see [Deployment](docs/deployment.md)). Delete the folder to delete everything.

## Documentation

- [Architecture](docs/architecture.md), signal flow, threading, schema.
- [Deployment](docs/deployment.md), install paths in depth, where data lives, GPU setup.
- [Custom wake words](docs/custom-wake-word.md), train your own phrase via Colab.
- [Contributing](CONTRIBUTING.md), dev setup, code style, PR process.

## Stack

PySide6 · faster-whisper · openWakeWord · Pillow · OpenAI / Anthropic / Ollama (optional) · SQLite

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
