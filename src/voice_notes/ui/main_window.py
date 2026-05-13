"""MainWindow — central wiring for v3.

Layout:
    [ Sidebar | (ALStatusBar over QStackedWidget(capture | tasks | notes)) ]

Owns:
    - AppSignals (cross-thread bus)
    - WakeWordListener / RecorderVAD lifecycle for Active Listening
    - SettingsDialog launcher
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QTimer, Slot
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.ai_parse import parse_transcript_with_ai
from ..core.audio import RecorderVAD
from ..core.db import db_get_setting, db_list, db_set_setting, qt_create
from ..core.stt import get_device_label, transcribe_with_meta
from ..core.voice_routes import try_route_to_todo
from ..core.wakeword import HAS_OWW, WakeWordListener, display_label_for
from ..theme import get_theme, render
from .al_status_bar import ALStatusBar
from .capture_panel import CapturePanel
from .list_panel import ListPanel
from .quick_note_panel import QuickNotePanel
from .quick_todos_panel import QuickTodosPanel
from .settings_dialog import SettingsDialog
from .signals import AppSignals
from .sidebar import Sidebar


class MainWindow(QMainWindow):
    NAV_TO_INDEX = {"capture": 0, "quick_note": 1, "task": 2, "note": 3}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Voice Notes")
        self.resize(1280, 820)
        self.setMinimumSize(900, 600)

        self.signals = AppSignals(self)
        self._wl: WakeWordListener | None = None
        self._al_rec: RecorderVAD | None = None
        self._al_active: bool = False
        self._al_recording: bool = False
        self._al_models_ready: bool = False

        self._build()
        self._wire()

        last = db_get_setting("v3_last_nav", "capture") or "capture"
        if last not in self.NAV_TO_INDEX:
            last = "capture"
        self._sidebar.set_active(last)
        self._stack.setCurrentIndex(self.NAV_TO_INDEX[last])

    # ── Build ─────────────────────────────────────────────────

    def _build(self) -> None:
        central = QWidget(self)
        central.setObjectName("mainArea")
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._sidebar = Sidebar(central)
        outer.addWidget(self._sidebar)

        right_col = QWidget(central)
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._al_bar = ALStatusBar(right_col)
        right_layout.addWidget(self._al_bar)

        self._stack = QStackedWidget(right_col)
        self._capture = CapturePanel(self.signals, self._stack)
        self._stack.addWidget(self._capture)
        self._quick_note = QuickNotePanel(self.signals, self._stack)
        self._stack.addWidget(self._quick_note)
        self._tasks = ListPanel("task", self.signals, self._stack)
        self._notes = ListPanel("note", self.signals, self._stack)
        self._stack.addWidget(self._tasks)
        self._stack.addWidget(self._notes)
        right_layout.addWidget(self._stack, 1)

        outer.addWidget(right_col, 1)

        # Right-side quick todos pane (collapsible).
        self._todos_panel = QuickTodosPanel(self.signals, central)
        outer.addWidget(self._todos_panel)

        self.setCentralWidget(central)

    # ── Wire ──────────────────────────────────────────────────

    def _wire(self) -> None:
        self._sidebar.nav_changed.connect(self._on_nav_changed)
        self._sidebar.settings_requested.connect(self._on_settings)
        self._sidebar.al_toggle_requested.connect(self._on_al_toggle)

        self.signals.theme_changed.connect(self._on_theme_changed)
        self.signals.al_state_changed.connect(self._on_al_state_changed)
        self.signals.al_ready.connect(self._on_al_ready)
        self.signals.al_error.connect(self._on_al_error)
        self.signals.al_wakeword_hit.connect(self._on_wakeword_hit)
        self.signals.al_recording_done.connect(self._on_al_recording_done)
        self.signals.al_cycle_complete.connect(self._restart_listener_only)

        # Keep the AL bar + sidebar in sync with the actual phase:
        # transcribing → parsing. al_cycle_complete handles the return to
        # listening so we only need to flip in on transcription_done.
        self.signals.transcription_done.connect(self._on_transcription_done_global)

        self._tasks.item_clicked.connect(self._on_card_clicked)
        self._notes.item_clicked.connect(self._on_card_clicked)

    # ── Global status sync ────────────────────────────────────

    @Slot(str)
    def _on_transcription_done_global(self, _text: str) -> None:
        if not self._al_active:
            return
        device = get_device_label()
        msg = f"Parsing… ({device})" if device else "Parsing…"
        self._sidebar.set_status(msg, "checking")
        self._al_bar.set_state("parsing")

    # ── Nav / theme / settings ────────────────────────────────

    @Slot(str)
    def _on_nav_changed(self, key: str) -> None:
        idx = self.NAV_TO_INDEX.get(key)
        if idx is None:
            return
        self._stack.setCurrentIndex(idx)
        db_set_setting("v3_last_nav", key)

    @Slot()
    def _on_settings(self) -> None:
        dlg = SettingsDialog(self.signals, al_running=self._al_active, parent=self)
        dlg.al_settings_changed.connect(self._restart_active_listening)
        dlg.exec()

    @Slot(str)
    def _on_theme_changed(self, name: str) -> None:
        app = QApplication.instance()
        if app is None:
            return
        app.setStyleSheet(render(get_theme(name)))
        db_set_setting("theme_v3", name)

    @Slot(int)
    def _on_card_clicked(self, item_id: int) -> None:
        rows = db_list(q="")
        match = next((r for r in rows if int(r["id"]) == int(item_id)), None)
        if match is None:
            return
        self._capture.load_item_for_edit(match)
        self._sidebar.set_active("capture")
        self._stack.setCurrentIndex(self.NAV_TO_INDEX["capture"])

    # ── Active Listening: lifecycle ───────────────────────────

    @Slot(bool)
    def _on_al_toggle(self, on: bool) -> None:
        if on:
            self._start_active_listening()
        else:
            self._stop_active_listening()

    def _effective_wakeword_model(self) -> str:
        """Custom file path wins; falls back to built-in dropdown choice."""
        custom = (db_get_setting("al_model_path", "") or "").strip()
        if custom:
            return custom
        return db_get_setting("al_model", "hey_jarvis") or "hey_jarvis"

    def _start_active_listening(self) -> None:
        if not HAS_OWW:
            self._sidebar.set_status("openwakeword not installed", "offline")
            self._sidebar.set_al_active(False)
            self._al_bar.set_state("idle")
            return

        self._al_active = True
        model = self._effective_wakeword_model()
        label = display_label_for(model)
        self._sidebar.set_al_active(True)
        self._sidebar.set_status(f"Loading {label}…", "checking")
        self.signals.al_state_changed.emit("loading")
        self._al_bar.set_state("loading", label)
        self._spawn_listener(model)

    def _spawn_listener(self, model: str) -> None:
        try:
            threshold = float(db_get_setting("al_threshold", "0.5") or 0.5)
        except ValueError:
            threshold = 0.5

        signals = self.signals

        def on_wakeword():
            signals.al_wakeword_hit.emit()

        def on_error(err):
            signals.al_error.emit(err)

        def on_ready():
            signals.al_ready.emit(model)

        self._wl = WakeWordListener(
            model, on_wakeword, on_error=on_error, on_ready=on_ready,
            score_threshold=threshold, cooldown_secs=3.0,
        )
        self._wl.start()

    def _stop_active_listening(self) -> None:
        self._al_active = False
        if self._wl is not None:
            self._wl.stop()
            self._wl = None
        if self._al_rec is not None and self._al_recording:
            try:
                self._al_rec.stop()
            except Exception:
                pass
        self._al_rec = None
        self._al_recording = False
        self._sidebar.set_al_active(False)
        self._sidebar.set_status("Idle", "idle")
        self.signals.al_state_changed.emit("idle")
        self._al_bar.set_state("idle")

    @Slot()
    def _restart_active_listening(self) -> None:
        if not self._al_active:
            return
        self._stop_active_listening()
        QTimer.singleShot(150, self._start_active_listening)

    # ── Active Listening: state-machine slots ─────────────────

    @Slot(str)
    def _on_al_ready(self, model: str) -> None:
        if not self._al_active:
            return
        self._al_models_ready = True
        label = display_label_for(model)
        self.signals.al_state_changed.emit("listening")
        self._al_bar.set_state("listening", label)
        self._sidebar.set_status(f"Listening for ‘{label}’", "active")

    @Slot(str)
    def _on_al_error(self, err: str) -> None:
        self._stop_active_listening()
        self._sidebar.set_status(f"AL error: {err[:32]}", "offline")
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(
            self,
            "Active Listening — Model Error",
            f"Failed to load wake-word model:\n\n{err}\n\n"
            "Try a different model under Settings → Active Listening.",
        )

    @Slot()
    def _on_wakeword_hit(self) -> None:
        if self._al_recording or not self._al_active:
            return
        if self._wl is not None:
            self._wl.stop()
            self._wl = None
        label = display_label_for(self._effective_wakeword_model())
        self._al_recording = True
        self.signals.al_state_changed.emit("wake-detected")
        self._al_bar.set_state("wake-detected", label)
        self._sidebar.set_status("Wake word detected", "active")
        QTimer.singleShot(220, self._begin_al_recording)

    def _begin_al_recording(self) -> None:
        if not self._al_recording:
            return

        try:
            vad_thresh = float(db_get_setting("al_vad_threshold", "0.008") or 0.008)
        except ValueError:
            vad_thresh = 0.008
        try:
            silence_s = float(db_get_setting("al_silence_secs", "1.5") or 1.5)
        except ValueError:
            silence_s = 1.5

        signals = self.signals

        def on_silence():
            # Stops the recorder and ships the wav back to the GUI thread.
            try:
                wav = self._al_rec.stop() if self._al_rec is not None else b""
            except Exception:
                wav = b""
            signals.al_recording_done.emit(wav or b"")

        self._al_rec = RecorderVAD()
        try:
            self._al_rec.start_vad(on_silence, vad_threshold=vad_thresh,
                                   silence_secs=silence_s, max_secs=30.0)
        except Exception as exc:
            self._al_recording = False
            self._al_rec = None
            self._sidebar.set_status(f"AL recording error: {exc}", "offline")
            self._restart_listener_only()
            return

        self.signals.al_state_changed.emit("recording")
        self._al_bar.set_state("recording")
        self._sidebar.set_status("Recording…", "active")

    @Slot(bytes)
    def _on_al_recording_done(self, wav: bytes) -> None:
        self._al_recording = False
        self._al_rec = None

        if not wav:
            self._sidebar.set_status("No audio captured", "offline")
            self._restart_listener_only()
            return

        self.signals.al_state_changed.emit("transcribing")
        self._al_bar.set_state("transcribing")
        self._sidebar.set_status("Transcribing…", "checking")
        threading.Thread(target=self._al_transcribe_worker, args=(wav,), daemon=True).start()

    def _al_transcribe_worker(self, wav: bytes) -> None:
        """Runs in a background thread.

        Cross-thread rule: this thread has no Qt event loop, so we MUST NOT
        call QTimer.singleShot or any direct GUI mutator. Emit signals only —
        Qt routes them to the GUI thread via QueuedConnection.
        """
        try:
            text, meta = transcribe_with_meta(wav)
        except Exception as exc:
            self.signals.transcription_error.emit(f"Transcription error: {exc}")
            self.signals.al_cycle_complete.emit()
            return
        if not text:
            self.signals.transcription_error.emit("No speech detected")
            self.signals.al_cycle_complete.emit()
            return

        # Voice routing: if this looks like a quick todo, insert and skip the
        # transcription_done emit (which would paint+auto-save a note) and the
        # AI parse. Surface confirmation via parse_done with _routed_todo, same
        # as the push-to-talk path in capture_panel.
        todo_text = try_route_to_todo(text)
        if todo_text:
            try:
                qt_create(todo_text, source="voice")
                self.signals.quick_todos_changed.emit()
                self.signals.parse_done.emit({"_routed_todo": todo_text}, text)
            except Exception as exc:
                self.signals.transcription_error.emit(f"Quick todo insert failed: {exc}")
            self.signals.al_cycle_complete.emit()
            return

        # Workspace-aware routing: if the user is currently on the Quick Note
        # workspace, AL transcripts go there (raw text, no AI parse). Anywhere
        # else, fall through to the Capture path (transcription_done + parse).
        active = getattr(self._sidebar, "_active_key", "capture")
        if active == "quick_note":
            self._quick_note.transcribed.emit(text, meta)
            self.signals.al_cycle_complete.emit()
            return

        self.signals.transcription_done.emit(text)
        try:
            parsed = parse_transcript_with_ai(text)
        except Exception as exc:
            self.signals.parse_done.emit({"_error": str(exc), "body": text}, text)
            self.signals.al_cycle_complete.emit()
            return
        self.signals.parse_done.emit(parsed or {}, text)
        self.signals.al_cycle_complete.emit()

    @Slot()
    def _restart_listener_only(self) -> None:
        if not self._al_active:
            return
        model = self._effective_wakeword_model()
        self._spawn_listener(model)
        label = display_label_for(model)
        self.signals.al_state_changed.emit("listening")
        self._al_bar.set_state("listening", label)
        self._sidebar.set_status(f"Listening for ‘{label}’", "active")

    @Slot(str)
    def _on_al_state_changed(self, state: str) -> None:
        # Reserved for any global side-effects keyed off the state machine
        # (currently the per-widget slots above own their own updates).
        pass

    # ── Shutdown ──────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        if self._al_active:
            self._stop_active_listening()
        super().closeEvent(event)
