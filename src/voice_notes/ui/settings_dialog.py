"""Settings dialog — Voice / Transcription / Active Listening / Appearance.

Replaces the cramped sidebar settings of v2. All values persist via
core.db.db_set_setting; theme + AL settings emit signals so the running app
reacts immediately (theme swap, AL listener restart).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core.db import db_get_setting, db_set_setting
from ..core.keystore import get_secret, set_secret
from ..core.wakeword import get_oww_models, HAS_OWW
from .helpers import restyle
from .signals import AppSignals


_AL_KEYS = ("al_model", "al_model_path", "al_threshold", "al_silence_secs", "al_vad_threshold")


def _section(title: str, parent=None) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame(parent)
    frame.setProperty("class", "settingsSection")
    box = QVBoxLayout(frame)
    box.setContentsMargins(20, 16, 20, 16)
    box.setSpacing(10)

    label = QLabel(title, frame)
    label.setProperty("class", "settingsSectionLabel")
    box.addWidget(label)
    return frame, box


def _field_row(label_text: str, widget: QWidget, hint: str = "", parent=None) -> QWidget:
    holder = QWidget(parent)
    layout = QVBoxLayout(holder)
    layout.setContentsMargins(0, 4, 0, 0)
    layout.setSpacing(4)

    lbl = QLabel(label_text, holder)
    lbl.setProperty("class", "fieldLabel")
    layout.addWidget(lbl)
    layout.addWidget(widget)
    if hint:
        h = QLabel(hint, holder)
        h.setProperty("class", "fieldHint")
        h.setWordWrap(True)
        layout.addWidget(h)
    return holder


class SettingsDialog(QDialog):
    """Modal settings panel.

    Emits `al_settings_changed()` when AL parameters changed AND the listener
    is currently running, so MainWindow can restart it cleanly.
    """

    al_settings_changed = Signal()

    def __init__(self, signals: AppSignals, al_running: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(560, 680)
        self._signals = signals
        self._al_running = al_running
        self._initial_al = {k: db_get_setting(k, "") for k in _AL_KEYS}

        self._build()
        self._load()

    # ── Build ─────────────────────────────────────────────────

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header
        header = QFrame(self)
        header.setObjectName("dialogHeader")
        header_l = QHBoxLayout(header)
        header_l.setContentsMargins(28, 18, 28, 16)
        title = QLabel("Settings", header)
        title.setProperty("class", "h1")
        header_l.addWidget(title)
        header_l.addStretch(1)
        outer.addWidget(header)

        # Body (scroll)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        body_w = QWidget(scroll)
        body = QVBoxLayout(body_w)
        body.setContentsMargins(28, 18, 28, 18)
        body.setSpacing(16)

        body.addWidget(self._build_appearance())
        body.addWidget(self._build_transcription())
        body.addWidget(self._build_parser())
        body.addWidget(self._build_active_listening())
        body.addStretch(1)

        scroll.setWidget(body_w)
        outer.addWidget(scroll, 1)

        # Footer
        footer = QFrame(self)
        footer.setObjectName("dialogFooter")
        footer_l = QHBoxLayout(footer)
        footer_l.setContentsMargins(28, 14, 28, 14)
        footer_l.setSpacing(8)
        rerun = QPushButton("Re-run setup", footer)
        rerun.setObjectName("ghost")
        rerun.setCursor(Qt.PointingHandCursor)
        rerun.setToolTip("Re-open the first-run wizard")
        rerun.clicked.connect(self._on_rerun_wizard)
        footer_l.addWidget(rerun)

        footer_l.addStretch(1)

        cancel = QPushButton("Cancel", footer)
        cancel.setObjectName("ghost")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        footer_l.addWidget(cancel)

        save = QPushButton("Save", footer)
        save.setObjectName("primary")
        save.setCursor(Qt.PointingHandCursor)
        save.setDefault(True)
        save.clicked.connect(self._on_save)
        footer_l.addWidget(save)

        outer.addWidget(footer)

    # ── Sections ──────────────────────────────────────────────

    def _build_appearance(self) -> QFrame:
        frame, box = _section("Appearance", self)

        seg_holder = QWidget(frame)
        seg_layout = QHBoxLayout(seg_holder)
        seg_layout.setContentsMargins(0, 0, 0, 0)
        seg_layout.setSpacing(0)

        self._theme_group = QButtonGroup(self)
        self._theme_group.setExclusive(True)

        options = [("cyberpunk", "Cyberpunk"), ("dark", "Dark"), ("light", "Light")]
        for i, (key, label) in enumerate(options):
            btn = QPushButton(label, seg_holder)
            btn.setObjectName("themeSeg")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("active", False)
            btn.setProperty("themeKey", key)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda _checked=False, k=key, b=btn: self._on_theme_pick(k, b))
            seg_layout.addWidget(btn)
            self._theme_group.addButton(btn, i)

        # Round only the outer segment edges so the row reads as one pill.
        last = seg_layout.count() - 1
        seg_layout.itemAt(0).widget().setStyleSheet(
            "border-top-left-radius: 8px; border-bottom-left-radius: 8px; border-right: none;"
        )
        seg_layout.itemAt(last).widget().setStyleSheet(
            "border-top-right-radius: 8px; border-bottom-right-radius: 8px;"
        )

        box.addWidget(_field_row("Theme", seg_holder, "Restyles instantly when saved.", frame))
        return frame

    def _build_parser(self) -> QFrame:
        frame, box = _section("Transcript parser (LLM)", self)

        self._parser_backend = QComboBox(frame)
        self._parser_backend.addItem("Local (Ollama), preferred", "local")
        self._parser_backend.addItem("OpenAI (gpt-4o-mini)", "openai")
        self._parser_backend.addItem("Anthropic Claude Haiku", "anthropic")
        self._parser_backend.addItem("Auto: local, then OpenAI, then Anthropic", "auto")
        self._parser_backend.addItem("None, keep raw transcript", "none")
        box.addWidget(_field_row(
            "Backend",
            self._parser_backend,
            "Which LLM turns your dictation into structured note/task fields.",
            frame,
        ))

        self._openai_api_key = QLineEdit(frame)
        self._openai_api_key.setPlaceholderText("sk-...")
        self._openai_api_key.setEchoMode(QLineEdit.Password)
        box.addWidget(_field_row(
            "OpenAI API key",
            self._openai_api_key,
            "Used when backend is OpenAI or auto. Read first from $OPENAI_API_KEY.",
            frame,
        ))

        self._anthropic_api_key = QLineEdit(frame)
        self._anthropic_api_key.setPlaceholderText("sk-ant-...")
        self._anthropic_api_key.setEchoMode(QLineEdit.Password)
        box.addWidget(_field_row(
            "Anthropic API key",
            self._anthropic_api_key,
            "Used when backend is Anthropic or auto. Read first from $ANTHROPIC_API_KEY.",
            frame,
        ))

        self._ollama_url = QLineEdit(frame)
        self._ollama_url.setPlaceholderText("http://localhost:11434")
        box.addWidget(_field_row(
            "Ollama base URL",
            self._ollama_url,
            "Local Ollama endpoint.",
            frame,
        ))

        self._ollama_model = QLineEdit(frame)
        self._ollama_model.setPlaceholderText("qwen2.5:7b-instruct-q5_K_M")
        box.addWidget(_field_row(
            "Ollama model",
            self._ollama_model,
            "Any JSON-capable chat model from your local registry.",
            frame,
        ))

        return frame

    def _build_transcription(self) -> QFrame:
        frame, box = _section("Transcription", self)

        self._whisper_combo = QComboBox(frame)
        self._whisper_combo.addItems([
            "tiny.en",
            "tiny",
            "base.en",
            "base",
            "small.en",
            "small",
            "distil-small.en",
            "medium.en",
            "medium",
            "distil-medium.en",
            "large-v2",
            "large-v3",
            "distil-large-v3",
        ])

        box.addWidget(_field_row(
            "Whisper model",
            self._whisper_combo,
            "Smaller and .en variants are fastest. distil-* trades a small "
            "accuracy hit for ~5-6x speed. base.en is the safe default.",
            frame,
        ))
        return frame

    def _build_active_listening(self) -> QFrame:
        frame, box = _section("Active Listening (wake word)", self)

        if not HAS_OWW:
            warn = QLabel("⚠  openwakeword is not installed — pip install openwakeword", frame)
            warn.setProperty("class", "fieldHint")
            box.addWidget(warn)

        self._al_model_combo = QComboBox(frame)
        models = get_oww_models()
        self._al_model_combo.addItems(models)
        box.addWidget(_field_row(
            "Wake-word model",
            self._al_model_combo,
            "Built-in phrase. Overridden by a custom model file below if set.",
            frame,
        ))

        # Custom model file (overrides built-in)
        custom_row = QWidget(frame)
        custom_layout = QHBoxLayout(custom_row)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.setSpacing(6)
        self._al_model_path = QLineEdit(custom_row)
        self._al_model_path.setPlaceholderText("Path to a custom .onnx or .tflite (leave blank to use built-in)")
        custom_layout.addWidget(self._al_model_path, 1)
        browse_btn = QPushButton("Browse…", custom_row)
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.clicked.connect(self._on_browse_custom_model)
        custom_layout.addWidget(browse_btn)
        clear_btn = QPushButton("Clear", custom_row)
        clear_btn.setObjectName("ghost")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(lambda: self._al_model_path.clear())
        custom_layout.addWidget(clear_btn)
        box.addWidget(_field_row(
            "Custom model file",
            custom_row,
            "Drop in a .onnx trained via the openWakeWord Colab notebook.",
            frame,
        ))

        # Help links: openWakeWord training + project README
        links = QLabel(
            'Train your own phrase via the '
            '<a href="https://github.com/dscripka/openWakeWord/blob/main/notebooks/automatic_model_training.ipynb" '
            'style="color: #38bdf8; text-decoration: none;">openWakeWord Colab notebook</a>'
            '  ·  '
            '<a href="https://github.com/dscripka/openWakeWord" '
            'style="color: #38bdf8; text-decoration: none;">openWakeWord docs</a>',
            frame,
        )
        links.setOpenExternalLinks(True)
        links.setTextInteractionFlags(Qt.TextBrowserInteraction)
        links.setProperty("class", "fieldHint")
        links.setWordWrap(True)
        box.addWidget(links)

        self._al_threshold = QDoubleSpinBox(frame)
        self._al_threshold.setRange(0.05, 0.95)
        self._al_threshold.setSingleStep(0.05)
        self._al_threshold.setDecimals(2)
        box.addWidget(_field_row(
            "Score threshold",
            self._al_threshold,
            "How confident the wake-word detector must be. 0.5 is the default.",
            frame,
        ))

        self._al_silence = QDoubleSpinBox(frame)
        self._al_silence.setRange(0.5, 10.0)
        self._al_silence.setSingleStep(0.25)
        self._al_silence.setDecimals(2)
        self._al_silence.setSuffix(" s")
        box.addWidget(_field_row(
            "Silence cutoff",
            self._al_silence,
            "Stop recording after this much continuous silence.",
            frame,
        ))

        self._al_vad = QDoubleSpinBox(frame)
        self._al_vad.setRange(0.001, 0.1)
        self._al_vad.setSingleStep(0.001)
        self._al_vad.setDecimals(3)
        box.addWidget(_field_row(
            "VAD threshold",
            self._al_vad,
            "RMS energy below this counts as silence. 0.008 is the default.",
            frame,
        ))

        return frame

    # ── Load + Save ───────────────────────────────────────────

    def _load(self) -> None:
        # Theme
        theme_key = (db_get_setting("theme_v3", "cyberpunk") or "cyberpunk").lower()
        if theme_key not in ("dark", "light", "cyberpunk"):
            theme_key = "cyberpunk"
        for btn in self._theme_group.buttons():
            picked = btn.property("themeKey") == theme_key
            btn.setChecked(picked)
            btn.setProperty("active", picked)
            restyle(btn)

        # Whisper
        wm = db_get_setting("whisper_model", "base") or "base"
        idx = self._whisper_combo.findText(wm)
        if idx >= 0:
            self._whisper_combo.setCurrentIndex(idx)

        # Parser backend
        backend = (db_get_setting("parser_backend", "auto") or "auto").lower()
        idx = self._parser_backend.findData(backend)
        if idx >= 0:
            self._parser_backend.setCurrentIndex(idx)
        self._openai_api_key.setText(get_secret("openai"))
        self._anthropic_api_key.setText(get_secret("anthropic"))
        self._ollama_url.setText(db_get_setting("ollama_base_url", "") or "")
        self._ollama_model.setText(db_get_setting("ollama_model", "") or "")

        # AL
        al_model = db_get_setting("al_model", "hey_jarvis") or "hey_jarvis"
        idx = self._al_model_combo.findText(al_model)
        if idx >= 0:
            self._al_model_combo.setCurrentIndex(idx)
        self._al_model_path.setText(db_get_setting("al_model_path", "") or "")

        try: self._al_threshold.setValue(float(db_get_setting("al_threshold", "0.5") or 0.5))
        except ValueError: self._al_threshold.setValue(0.5)
        try: self._al_silence.setValue(float(db_get_setting("al_silence_secs", "1.5") or 1.5))
        except ValueError: self._al_silence.setValue(1.5)
        try: self._al_vad.setValue(float(db_get_setting("al_vad_threshold", "0.008") or 0.008))
        except ValueError: self._al_vad.setValue(0.008)

    def _on_theme_pick(self, key: str, btn: QPushButton) -> None:
        for b in self._theme_group.buttons():
            picked = b is btn
            b.setProperty("active", picked)
            restyle(b)

    def _selected_theme(self) -> str:
        for b in self._theme_group.buttons():
            if b.isChecked():
                return b.property("themeKey") or "cyberpunk"
        return "cyberpunk"

    @Slot()
    def _on_save(self) -> None:
        # Theme
        theme = self._selected_theme()
        if theme != db_get_setting("theme_v3", "cyberpunk"):
            db_set_setting("theme_v3", theme)
            self._signals.theme_changed.emit(theme)

        # Whisper
        db_set_setting("whisper_model", self._whisper_combo.currentText() or "base")

        # Parser backend
        db_set_setting("parser_backend", self._parser_backend.currentData() or "auto")
        set_secret("openai", self._openai_api_key.text().strip())
        set_secret("anthropic", self._anthropic_api_key.text().strip())
        db_set_setting("ollama_base_url", self._ollama_url.text().strip())
        db_set_setting("ollama_model", self._ollama_model.text().strip())

        # AL
        new_al = {
            "al_model":          self._al_model_combo.currentText() or "hey_jarvis",
            "al_model_path":     self._al_model_path.text().strip(),
            "al_threshold":      f"{self._al_threshold.value():.2f}",
            "al_silence_secs":   f"{self._al_silence.value():.2f}",
            "al_vad_threshold":  f"{self._al_vad.value():.3f}",
        }
        for k, v in new_al.items():
            db_set_setting(k, v)

        if self._al_running and any(self._initial_al[k] != new_al[k] for k in _AL_KEYS):
            self.al_settings_changed.emit()

        self.accept()

    @Slot()
    def _on_rerun_wizard(self) -> None:
        # Reset the flag so the next launch shows the wizard, OR launch it
        # right now from inside Settings. Launching now is the better UX.
        from .setup_wizard import SetupWizard
        wiz = SetupWizard(self)
        wiz.exec()
        # Reload settings into the dialog so picks made in the wizard appear.
        self._load()

    @Slot()
    def _on_browse_custom_model(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Select a custom wake-word model",
            self._al_model_path.text().strip() or "",
            "openWakeWord model (*.onnx *.tflite)",
        )
        if path:
            self._al_model_path.setText(path)

