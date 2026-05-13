"""Capture panel — mic + transcript + edit form.

Replaces v2's "CAPTURE" pane (lines 1094–1143). Push-to-talk flow:
    click mic → Recorder.start() → tick timer → click again → Recorder.stop()
    → bg thread runs transcribe() + parse_transcript_with_ai()
    → signals.parse_done → form populated → auto-save
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QTimer, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.ai_parse import parse_transcript_with_ai
from ..core.audio import Recorder
from ..core.db import db_create, db_update, qt_create
from ..core.stt import transcribe_with_meta
from ..core.voice_routes import try_route_to_todo
from .helpers import apply_mic_icon, restyle
from .signals import AppSignals


class CapturePanel(QWidget):
    """Center column for capturing notes/tasks via mic or keyboard."""

    # Convenience: re-emitted when an item is created/updated so MainWindow can
    # refresh the relevant list panel.
    item_saved = Signal(int, str)  # item_id, item_type

    def __init__(self, signals: AppSignals, parent=None):
        super().__init__(parent)
        self._signals = signals
        self._recorder = Recorder()
        self._is_recording = False
        self._editing_id: int | None = None
        self._editing_existing: bool = False  # True only when load_item_for_edit() ran
        self._painted_raw: bool = False  # True when raw transcript already filled body
        self._tick_secs = 0
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._on_tick)

        self._build()
        self._wire_signals()

    # ── Build ─────────────────────────────────────────────────

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 28)
        outer.setSpacing(16)

        # Header row
        header = QHBoxLayout()
        header.setSpacing(12)
        h1 = QLabel("Capture", self)
        h1.setProperty("class", "h1")
        header.addWidget(h1)
        header.addStretch(1)
        self._status = QLabel("", self)
        self._status.setProperty("class", "muted mono")
        header.addWidget(self._status)
        outer.addLayout(header)

        # Form card
        card = QFrame(self)
        card.setProperty("class", "card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(14)

        # Row 1: TYPE + PRIORITY
        row1 = QHBoxLayout()
        row1.setSpacing(16)

        type_col = QVBoxLayout()
        type_col.setSpacing(6)
        type_lbl = QLabel("Type", card)
        type_lbl.setProperty("class", "fieldLabel")
        self._type = QComboBox(card)
        self._type.addItems(["note", "task"])
        type_col.addWidget(type_lbl)
        type_col.addWidget(self._type)
        row1.addLayout(type_col, 1)

        pri_col = QVBoxLayout()
        pri_col.setSpacing(6)
        pri_lbl = QLabel("Priority", card)
        pri_lbl.setProperty("class", "fieldLabel")
        self._priority = QComboBox(card)
        self._priority.addItems(["low", "normal", "high"])
        self._priority.setCurrentText("normal")
        pri_col.addWidget(pri_lbl)
        pri_col.addWidget(self._priority)
        row1.addLayout(pri_col, 1)

        card_layout.addLayout(row1)

        # Tags
        tags_lbl = QLabel("Tags  (comma-separated)", card)
        tags_lbl.setProperty("class", "fieldLabel")
        self._tags = QLineEdit(card)
        self._tags.setPlaceholderText("idea, urgent, side-project")
        card_layout.addWidget(tags_lbl)
        card_layout.addWidget(self._tags)

        # Title
        title_lbl = QLabel("Title", card)
        title_lbl.setProperty("class", "fieldLabel")
        self._title = QLineEdit(card)
        self._title.setPlaceholderText("Short, descriptive title")
        card_layout.addWidget(title_lbl)
        card_layout.addWidget(self._title)

        # Body (label row with Copy button on the right)
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
        self._copy_btn.clicked.connect(self._on_copy_body)
        body_row.addWidget(self._copy_btn)
        card_layout.addLayout(body_row)

        self._body = QTextEdit(card)
        self._body.setPlaceholderText("Speak or type. Dictation auto-fills this.")
        self._body.setMinimumHeight(180)
        card_layout.addWidget(self._body, 1)

        # Action row: Mic + Done + Clear
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
        clear_btn.clicked.connect(self._clear_form)
        action_row.addWidget(clear_btn)

        done_btn = QPushButton("Done", card)
        done_btn.setObjectName("primary")
        done_btn.setCursor(Qt.PointingHandCursor)
        done_btn.clicked.connect(self._on_done)
        action_row.addWidget(done_btn)

        card_layout.addLayout(action_row)

        outer.addWidget(card, 1)

    # ── Signal wiring ─────────────────────────────────────────

    def _wire_signals(self) -> None:
        self._signals.transcription_done.connect(self._on_transcription_done)
        self._signals.transcription_error.connect(self._on_transcription_error)
        self._signals.parse_done.connect(self._on_parse_done)

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
        self._set_status("Transcribing & parsing…")
        threading.Thread(target=self._transcribe_worker, daemon=True).start()

    def _on_tick(self) -> None:
        if not self._is_recording:
            return
        self._tick_secs += 1
        self._set_status(f"Recording {self._tick_secs}s")

    def _transcribe_worker(self) -> None:
        """Runs in a background thread; emits signals back to GUI thread."""
        try:
            wav = self._recorder.stop()
        except Exception as exc:
            self._signals.transcription_error.emit(f"Mic stop failed: {exc}")
            return
        if not wav:
            self._signals.transcription_error.emit("Recording was empty")
            return
        try:
            text, meta = transcribe_with_meta(wav)
        except Exception as exc:
            self._signals.transcription_error.emit(f"Transcription error: {exc}")
            return
        if not text:
            self._signals.transcription_error.emit("No speech detected")
            return
        self._last_stt_meta = meta

        # Voice routing: prefix like "quick todo: ..." inserts to right pane
        # and skips the AI parse + voice_items insert entirely.
        todo_text = try_route_to_todo(text)
        if todo_text:
            try:
                qt_create(todo_text, source="voice")
                self._signals.quick_todos_changed.emit()
                # Tell the GUI thread to clear status / show confirmation.
                self._signals.parse_done.emit({"_routed_todo": todo_text}, text)
            except Exception as exc:
                self._signals.transcription_error.emit(f"Quick todo insert failed: {exc}")
            return

        self._signals.transcription_done.emit(text)
        try:
            parsed = parse_transcript_with_ai(text)
        except Exception as exc:
            self._signals.parse_done.emit({"_error": str(exc), "body": text}, text)
            return
        self._signals.parse_done.emit(parsed or {}, text)

    # ── Slots (GUI thread) ────────────────────────────────────

    @Slot(str)
    def _on_transcription_done(self, text: str) -> None:
        """Paint transcript into the body immediately so the user sees text
        before gpt-4o-mini finishes parsing."""
        self._mic_label.setText("Enriching…")
        existing = self._body.toPlainText().strip()
        if existing:
            self._body.append("")
            self._body.append(text)
        else:
            self._body.setPlainText(text)
        self._painted_raw = True
        # Persist now so a slow / failed parse doesn't lose the transcript.
        self._auto_save()
        meta = getattr(self, "_last_stt_meta", {}) or {}
        device = meta.get("device", "")
        compute = meta.get("compute", "")
        elapsed = meta.get("elapsed_ms")
        if device and elapsed is not None:
            self._set_status(f"Transcribed in {elapsed} ms ({device}/{compute}), parsing…")
        else:
            self._set_status("Transcribed, parsing…")

    @Slot(str)
    def _on_transcription_error(self, msg: str) -> None:
        self._mic_label.setText("Click to dictate")
        self._painted_raw = False
        self._set_status(msg)

    @Slot(dict, str)
    def _on_parse_done(self, parsed: dict, raw: str) -> None:
        self._mic_label.setText("Click to dictate")
        if "_routed_todo" in parsed:
            self._set_status(f"Added to todos: {parsed['_routed_todo']} ✓")
            self._painted_raw = False
            return
        if "_error" in parsed:
            self._apply_raw(raw, parsed["_error"])
        else:
            self._apply_parsed(parsed, raw)
        self._painted_raw = False

    # ── Form helpers ──────────────────────────────────────────

    def _apply_parsed(self, parsed: dict, raw: str) -> None:
        # Allow AI to set type/priority on fresh voice captures (where
        # _editing_id is set only because we auto-saved the raw transcript).
        # Block only when the user explicitly loaded an existing row to edit.
        allow_field_overwrite = not self._editing_existing

        item_type = (parsed.get("type") or "").lower()
        if item_type in ("note", "task") and allow_field_overwrite:
            self._type.setCurrentText(item_type)

        priority = (parsed.get("priority") or "").lower()
        if priority in ("low", "normal", "high") and allow_field_overwrite:
            self._priority.setCurrentText(priority)

        title = (parsed.get("title") or "").strip()
        if title and not self._title.text().strip():
            self._title.setText(title)

        body = (parsed.get("body") or "").strip()
        if body:
            if self._painted_raw:
                # Body already holds the raw transcript from _on_transcription_done.
                # Only replace it if the AI returned a materially different version
                # (e.g., cleaned punctuation or removed field directives).
                current = self._body.toPlainText().strip()
                if body != raw.strip() and body != current:
                    self._body.setPlainText(body)
            else:
                existing = self._body.toPlainText().strip()
                if existing:
                    self._body.append("")
                    self._body.append(body)
                else:
                    self._body.setPlainText(body)

        tags = parsed.get("tags") or ""
        if isinstance(tags, list):
            tags = ", ".join(tags)
        tags = str(tags).strip()
        if tags and not self._tags.text().strip():
            self._tags.setText(tags)

        self._auto_save()
        preview = raw.strip().replace("\n", " ")
        self._set_status(f"Auto-saved ✓  ·  {preview[:64]}")

    def _apply_raw(self, raw: str, error: str | None = None) -> None:
        if not self._painted_raw:
            existing = self._body.toPlainText().strip()
            if existing:
                self._body.append("")
                self._body.append(raw)
            else:
                self._body.setPlainText(raw)
        self._auto_save()
        if error:
            self._set_status(f"AI parse failed ({error}), raw transcript saved ✓")
        else:
            self._set_status("Raw transcript saved ✓")

    def _auto_save(self) -> None:
        item_type = self._type.currentText() or "note"
        title = self._title.text().strip()
        body = self._body.toPlainText().strip()
        priority = self._priority.currentText() or "normal"
        raw_tags = [t.strip().lower() for t in self._tags.text().split(",") if t.strip()][:12]

        if not (title or body):
            return

        if self._editing_id is not None:
            row = db_update(self._editing_id, {
                "item_type": item_type, "title": title, "body": body,
                "priority": priority, "tags": raw_tags,
            })
        else:
            row = db_create(item_type, title, body, priority, raw_tags, "voice-transcript")
            self._editing_id = row["id"]

        self._signals.items_changed.emit(item_type)
        self.item_saved.emit(int(row["id"]), item_type)

    # ── Public API ────────────────────────────────────────────

    def load_item_for_edit(self, item: dict) -> None:
        """Load an existing row into the form for editing."""
        self._editing_id = int(item["id"])
        self._editing_existing = True
        self._type.setCurrentText(item.get("item_type") or "note")
        self._priority.setCurrentText(item.get("priority") or "normal")
        self._title.setText(item.get("title") or "")
        self._body.setPlainText(item.get("body") or "")
        tags = item.get("tags") or []
        if isinstance(tags, str):
            import json
            try:
                tags = json.loads(tags)
            except Exception:
                tags = []
        self._tags.setText(", ".join(tags))
        self._set_status(f"Editing #{item['id']}, make changes then click Done.")

    # ── Internals ─────────────────────────────────────────────

    def _set_status(self, text: str) -> None:
        self._status.setText(text)

    def _on_copy_body(self) -> None:
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
        QTimer.singleShot(1500, lambda: self._status.text().startswith("Copied ") and self._set_status(""))

    def _clear_form(self) -> None:
        self._editing_id = None
        self._editing_existing = False
        self._type.setCurrentText("note")
        self._priority.setCurrentText("normal")
        self._title.clear()
        self._body.clear()
        self._tags.clear()
        self._set_status("Form cleared")

    def _on_done(self) -> None:
        self._auto_save()
        self._editing_id = None
        self._editing_existing = False
        self._type.setCurrentText("note")
        self._priority.setCurrentText("normal")
        self._title.clear()
        self._body.clear()
        self._tags.clear()
        self._set_status("Saved ✓")
