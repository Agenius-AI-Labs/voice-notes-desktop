"""Quick Note workspace.

Single-purpose dictation pad. No DB write, no AI parsing, no voice routing.
You talk, the transcript appends to a body field, and Copy / Clear let you
hand it off elsewhere.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QTimer, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.audio import Recorder
from ..core.stt import transcribe_with_meta
from .helpers import apply_mic_icon, restyle
from .signals import AppSignals


class QuickNotePanel(QWidget):
    """A scratchpad-style workspace for fast dictation + copy/paste."""

    # Local signals so transcription can hop back to the GUI thread without
    # piggy-backing on AppSignals (we don't want capture_panel to react).
    transcribed = Signal(str, dict)
    transcribe_failed = Signal(str)

    def __init__(self, signals: AppSignals, parent=None):
        super().__init__(parent)
        self._signals = signals
        self._recorder = Recorder()
        self._is_recording = False
        self._tick_secs = 0
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._on_tick)

        self._build()
        self._wire()

    # ── Build ─────────────────────────────────────────────────

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 28)
        outer.setSpacing(16)

        # Header row
        header = QHBoxLayout()
        header.setSpacing(12)
        h1 = QLabel("Quick Note", self)
        h1.setProperty("class", "h1")
        header.addWidget(h1)
        header.addStretch(1)
        self._status = QLabel("", self)
        self._status.setProperty("class", "muted mono")
        header.addWidget(self._status)
        outer.addLayout(header)

        # Card containing the body
        card = QFrame(self)
        card.setProperty("class", "card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(14)

        # Body label row
        body_row = QHBoxLayout()
        body_row.setSpacing(8)
        body_lbl = QLabel("Body", card)
        body_lbl.setProperty("class", "fieldLabel")
        body_row.addWidget(body_lbl)
        body_row.addStretch(1)
        self._copy_btn = QPushButton("Copy", card)
        self._copy_btn.setObjectName("ghost")
        self._copy_btn.setCursor(Qt.PointingHandCursor)
        self._copy_btn.setToolTip("Copy body to clipboard")
        self._copy_btn.clicked.connect(self._on_copy)
        body_row.addWidget(self._copy_btn)
        card_layout.addLayout(body_row)

        self._body = QTextEdit(card)
        self._body.setPlaceholderText(
            "Click the mic and talk, or type. Each transcription is appended.\n"
            "Copy hands the text off; Clear empties this pad."
        )
        self._body.setMinimumHeight(360)
        card_layout.addWidget(self._body, 1)

        # Action row: mic + clear
        action_row = QHBoxLayout()
        action_row.setSpacing(12)

        self._mic_btn = QPushButton(card)
        self._mic_btn.setObjectName("micBtn")
        self._mic_btn.setCursor(Qt.PointingHandCursor)
        self._mic_btn.setToolTip("Push-to-talk dictation  (Ctrl+Shift+Space)")
        apply_mic_icon(self._mic_btn, recording=False)
        self._mic_btn.clicked.connect(self._toggle_recording)
        action_row.addWidget(self._mic_btn)

        self._mic_label = QLabel("Click to dictate", card)
        self._mic_label.setProperty("class", "muted")
        action_row.addWidget(self._mic_label)
        action_row.addStretch(1)

        clear_btn = QPushButton("Clear", card)
        clear_btn.setObjectName("ghost")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self._on_clear)
        action_row.addWidget(clear_btn)

        card_layout.addLayout(action_row)
        outer.addWidget(card, 1)

    def _wire(self) -> None:
        self.transcribed.connect(self._on_transcribed)
        self.transcribe_failed.connect(self._on_transcribe_failed)

    # ── Recording flow ────────────────────────────────────────

    def _toggle_recording(self) -> None:
        if self._is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        try:
            self._recorder.start()
        except Exception as exc:
            self._set_status(f"Mic error: {exc}")
            return
        self._is_recording = True
        self._tick_secs = 0
        self._mic_btn.setProperty("recording", True)
        apply_mic_icon(self._mic_btn, recording=True)
        restyle(self._mic_btn)
        self._mic_label.setText("Recording…  (click to stop)")
        self._set_status("Recording 0s")
        self._tick_timer.start()

    def _stop_recording(self) -> None:
        self._is_recording = False
        self._tick_timer.stop()
        self._mic_btn.setProperty("recording", False)
        apply_mic_icon(self._mic_btn, recording=False)
        restyle(self._mic_btn)
        self._mic_label.setText("Transcribing…")
        self._set_status("Transcribing…")
        threading.Thread(target=self._transcribe_worker, daemon=True).start()

    def _on_tick(self) -> None:
        if not self._is_recording:
            return
        self._tick_secs += 1
        self._set_status(f"Recording {self._tick_secs}s")

    def _transcribe_worker(self) -> None:
        try:
            wav = self._recorder.stop()
        except Exception as exc:
            self.transcribe_failed.emit(f"Mic stop failed: {exc}")
            return
        if not wav:
            self.transcribe_failed.emit("Recording was empty")
            return
        try:
            text, meta = transcribe_with_meta(wav)
        except Exception as exc:
            self.transcribe_failed.emit(f"Transcription error: {exc}")
            return
        if not text:
            self.transcribe_failed.emit("No speech detected")
            return
        self.transcribed.emit(text, meta)

    # ── Slots ─────────────────────────────────────────────────

    @Slot(str, dict)
    def _on_transcribed(self, text: str, meta: dict) -> None:
        self._mic_label.setText("Click to dictate")
        existing = self._body.toPlainText().rstrip()
        if existing:
            # Append on a new line so chunks stay separable.
            self._body.setPlainText(existing + "\n" + text)
        else:
            self._body.setPlainText(text)
        # Move cursor to end so the user sees the latest addition.
        cursor = self._body.textCursor()
        cursor.movePosition(cursor.End)
        self._body.setTextCursor(cursor)

        device = meta.get("device", "")
        compute = meta.get("compute", "")
        elapsed = meta.get("elapsed_ms")
        if device and elapsed is not None:
            self._set_status(f"Appended in {elapsed} ms ({device}/{compute}) ✓")
        else:
            self._set_status("Appended ✓")

    @Slot(str)
    def _on_transcribe_failed(self, msg: str) -> None:
        self._mic_label.setText("Click to dictate")
        self._set_status(msg)

    @Slot()
    def _on_copy(self) -> None:
        text = self._body.toPlainText()
        if not text.strip():
            self._set_status("Body is empty, nothing to copy")
            return
        clip = QGuiApplication.clipboard()
        if clip is None:
            self._set_status("Clipboard unavailable")
            return
        clip.setText(text)
        self._set_status(f"Copied {len(text)} chars to clipboard ✓")
        QTimer.singleShot(
            1500,
            lambda: self._status.text().startswith("Copied ") and self._set_status(""),
        )

    @Slot()
    def _on_clear(self) -> None:
        self._body.clear()
        self._set_status("Cleared")

    # ── Internals ─────────────────────────────────────────────

    def _set_status(self, text: str) -> None:
        self._status.setText(text)
