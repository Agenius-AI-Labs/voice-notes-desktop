"""Quick Note pane.

Lives in the bottom half of the right column. Compact dictation scratchpad
for fire-and-forget transcripts you paste elsewhere. No DB write, no AI
parsing, no voice routing.

Active Listening transcripts land here automatically when the body has
keyboard focus (see MainWindow._al_transcribe_worker).
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QSize, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
)

from ..core.audio import Recorder
from ..core.stt import transcribe_with_meta
from .helpers import apply_mic_icon, restyle
from .signals import AppSignals


class QuickNotePanel(QFrame):
    """Compact scratchpad. Top header + body + small action row."""

    transcribed = Signal(str, dict)
    transcribe_failed = Signal(str)

    def __init__(self, signals: AppSignals, parent=None):
        super().__init__(parent)
        self.setObjectName("quickNotePanel")
        self._signals = signals
        self._recorder = Recorder()
        self._is_recording = False
        self._tick_secs = 0
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._on_tick)

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.setMinimumHeight(140)

        self._build()
        self._wire()

    # ── Build ─────────────────────────────────────────────────

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header: title  |  status  |  mic  Copy  Clear
        header = QFrame(self)
        header.setObjectName("qnHeader")
        h = QHBoxLayout(header)
        h.setContentsMargins(10, 10, 8, 6)
        h.setSpacing(8)

        title = QLabel("Quick Note", header)
        title.setObjectName("qnTitle")
        h.addWidget(title)

        self._status = QLabel("", header)
        self._status.setObjectName("qnStatus")
        h.addWidget(self._status, 1)

        # Compact mic icon-button (same styled glyph as Capture, header-sized).
        self._mic_btn = QPushButton(header)
        self._mic_btn.setObjectName("qnMicBtn")
        self._mic_btn.setCursor(Qt.PointingHandCursor)
        self._mic_btn.setToolTip("Push-to-talk dictation  (Ctrl+Shift+Space)")
        apply_mic_icon(self._mic_btn, recording=False)
        # Override the 48x48 default from apply_mic_icon with compact sizing.
        self._mic_btn.setIconSize(QSize(20, 20))
        self._mic_btn.setFixedSize(28, 28)
        self._mic_btn.clicked.connect(self._toggle_recording)
        h.addWidget(self._mic_btn)

        self._copy_btn = QPushButton("Copy", header)
        self._copy_btn.setObjectName("qnCopyBtn")
        self._copy_btn.setCursor(Qt.PointingHandCursor)
        self._copy_btn.setToolTip("Copy body to clipboard")
        self._copy_btn.clicked.connect(self._on_copy)
        h.addWidget(self._copy_btn)

        self._clear_btn = QPushButton("Clear", header)
        self._clear_btn.setObjectName("qnClearBtn")
        self._clear_btn.setCursor(Qt.PointingHandCursor)
        self._clear_btn.clicked.connect(self._on_clear)
        h.addWidget(self._clear_btn)

        outer.addWidget(header)

        # Body — takes all remaining space.
        body_host = QFrame(self)
        body_host.setObjectName("qnBodyHost")
        bl = QVBoxLayout(body_host)
        bl.setContentsMargins(10, 0, 10, 10)
        bl.setSpacing(0)
        self._body = QTextEdit(body_host)
        self._body.setObjectName("qnBody")
        self._body.setPlaceholderText(
            "Click the mic or type. Active Listening lands here when this "
            "field is focused."
        )
        bl.addWidget(self._body, 1)
        outer.addWidget(body_host, 1)

    def _wire(self) -> None:
        self.transcribed.connect(self._on_transcribed)
        self.transcribe_failed.connect(self._on_transcribe_failed)

    # ── Public ───────────────────────────────────────────────

    def has_body_focus(self) -> bool:
        """True if the scratchpad body currently has keyboard focus.

        Used by MainWindow to route AL transcripts here when the user is
        typing or has just clicked into the body.
        """
        return self._body.hasFocus()

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
        self._mic_btn.setIconSize(QSize(20, 20))  # apply_mic_icon resets to 48
        restyle(self._mic_btn)
        self._set_status("Recording 0s")
        self._tick_timer.start()

    def _stop_recording(self) -> None:
        self._is_recording = False
        self._tick_timer.stop()
        self._mic_btn.setProperty("recording", False)
        apply_mic_icon(self._mic_btn, recording=False)
        self._mic_btn.setIconSize(QSize(20, 20))
        restyle(self._mic_btn)
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
        existing = self._body.toPlainText().rstrip()
        if existing:
            self._body.setPlainText(existing + "\n" + text)
        else:
            self._body.setPlainText(text)
        cursor = self._body.textCursor()
        cursor.movePosition(cursor.End)
        self._body.setTextCursor(cursor)

        device = meta.get("device", "")
        compute = meta.get("compute", "")
        elapsed = meta.get("elapsed_ms")
        if device and elapsed is not None:
            self._set_status(f"+{elapsed}ms ({device}/{compute})")
        else:
            self._set_status("Appended")

    @Slot(str)
    def _on_transcribe_failed(self, msg: str) -> None:
        self._set_status(msg)

    @Slot()
    def _on_copy(self) -> None:
        text = self._body.toPlainText()
        if not text.strip():
            self._set_status("Empty")
            return
        clip = QGuiApplication.clipboard()
        if clip is None:
            self._set_status("Clipboard unavailable")
            return
        clip.setText(text)
        self._set_status(f"Copied {len(text)} chars")
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
