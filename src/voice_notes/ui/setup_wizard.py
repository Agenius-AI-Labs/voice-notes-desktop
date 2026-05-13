"""First-run setup wizard.

Six pages: Welcome → Whisper model → Wake word → AI backend → Downloads → Done.
Saves all picks via db_set_setting and flips first_run_complete=1 on finish.

The Downloads page kicks off the model fetches when entered so the user
isn't waiting at the mic on first click.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from ..core.db import db_get_setting, db_set_setting
from ..core.downloads import DownloadManager
from ..core.wakeword import HAS_OWW, get_oww_models

_ASSETS = Path(__file__).resolve().parents[1] / "assets"


WHISPER_OPTIONS = [
    # (id, label, size, blurb)
    ("tiny.en",   "Tiny (English)",   "~39 MB",  "Fastest, lowest accuracy. Good on slow CPUs."),
    ("base.en",   "Base (English)",   "~74 MB",  "Recommended. Solid quality, fast on most machines."),
    ("small.en",  "Small (English)",  "~244 MB", "Higher accuracy. Slower on CPU; great with a GPU."),
    ("medium.en", "Medium (English)", "~769 MB", "Best accuracy. GPU strongly recommended."),
]


def _h1(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("font-size: 20px; font-weight: 700;")
    return lbl


def _muted(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color: rgba(180, 200, 230, 0.7); font-size: 12px;")
    return lbl


# ── Pages ─────────────────────────────────────────────────────


class WelcomePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle(" ")
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.addWidget(_h1("Welcome to Voice Notes"))
        layout.addWidget(_muted(
            "Let's get you set up. This takes about a minute and downloads "
            "the speech-to-text model so your first mic click is instant."
        ))
        layout.addStretch(1)
        layout.addWidget(_muted(
            "You can change any of these choices later in Settings."
        ))


class WhisperPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle(" ")
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(_h1("Pick a transcription model"))
        layout.addWidget(_muted(
            "Whisper transcribes your speech. Bigger models are more accurate "
            "but slower on CPU."
        ))

        self._group = QButtonGroup(self)
        current = db_get_setting("whisper_model", "base.en") or "base.en"

        for model_id, label, size, blurb in WHISPER_OPTIONS:
            row = QWidget(self)
            row_l = QHBoxLayout(row)
            row_l.setContentsMargins(0, 4, 0, 4)
            row_l.setSpacing(10)
            rb = QRadioButton(row)
            rb.setText(f"{label}  ·  {size}")
            rb.setProperty("model_id", model_id)
            if model_id == current:
                rb.setChecked(True)
            self._group.addButton(rb)
            row_l.addWidget(rb)
            row_l.addWidget(_muted(blurb), 1)
            layout.addWidget(row)

        if not any(b.isChecked() for b in self._group.buttons()):
            self._group.buttons()[1].setChecked(True)  # base.en

        layout.addStretch(1)

    def chosen_model(self) -> str:
        for b in self._group.buttons():
            if b.isChecked():
                return b.property("model_id") or "base.en"
        return "base.en"

    def validatePage(self) -> bool:
        db_set_setting("whisper_model", self.chosen_model())
        return True


class WakeWordPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle(" ")
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(_h1("Wake word (optional)"))
        layout.addWidget(_muted(
            "Active Listening watches for a wake phrase, then auto-records. "
            "You can always push-to-talk instead. Custom models can be trained "
            "later via the openWakeWord Colab notebook (linked in Settings)."
        ))

        self._enable = QCheckBox("Enable wake-word activation", self)
        current_path = (db_get_setting("al_model_path", "") or "").strip()
        already_on = bool(current_path) or db_get_setting("al_enabled", "0") == "1"
        self._enable.setChecked(already_on)
        layout.addWidget(self._enable)

        if not HAS_OWW:
            layout.addWidget(_muted(
                "openwakeword is not installed in this environment. "
                "This step will be skipped."
            ))
            self._enable.setChecked(False)
            self._enable.setEnabled(False)

        self._combo = QComboBox(self)
        models = get_oww_models()
        self._combo.addItems(models)
        current = db_get_setting("al_model", "hey_jarvis") or "hey_jarvis"
        idx = self._combo.findText(current)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)

        combo_row = QWidget(self)
        cr = QHBoxLayout(combo_row)
        cr.setContentsMargins(20, 0, 0, 0)
        cr.setSpacing(10)
        cr.addWidget(QLabel("Wake phrase:"))
        cr.addWidget(self._combo, 1)
        layout.addWidget(combo_row)

        self._enable.toggled.connect(combo_row.setEnabled)
        combo_row.setEnabled(self._enable.isChecked())

        layout.addStretch(1)

    def wants_download(self) -> bool:
        return HAS_OWW and self._enable.isChecked()

    def validatePage(self) -> bool:
        db_set_setting("al_enabled", "1" if self._enable.isChecked() else "0")
        db_set_setting("al_model", self._combo.currentText() or "hey_jarvis")
        return True


class AIBackendPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle(" ")
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(_h1("AI parsing (optional)"))
        layout.addWidget(_muted(
            "Voice Notes can extract a title, tags, and priority from each "
            "transcript. Skip to keep raw text only. Configure later in Settings."
        ))

        self._group = QButtonGroup(self)
        current = (db_get_setting("parser_backend", "none") or "none").lower()

        self._rb_none = QRadioButton("None, save raw transcript only")
        self._rb_openai = QRadioButton("OpenAI (cloud, paid, fast)")
        self._rb_anthropic = QRadioButton("Anthropic Claude Haiku (cloud, paid, fast)")
        self._rb_ollama = QRadioButton("Ollama (local, free, requires Ollama install)")
        for rb in (self._rb_none, self._rb_openai, self._rb_anthropic, self._rb_ollama):
            self._group.addButton(rb)
            layout.addWidget(rb)

        # OpenAI key field
        self._openai_key = QLineEdit()
        self._openai_key.setPlaceholderText("sk-...")
        self._openai_key.setEchoMode(QLineEdit.Password)
        existing = db_get_setting("openai_api_key", "") or ""
        if existing:
            self._openai_key.setText(existing)
        key_row = QWidget(self)
        kr = QHBoxLayout(key_row)
        kr.setContentsMargins(20, 0, 0, 0)
        kr.setSpacing(10)
        kr.addWidget(QLabel("OpenAI key:"))
        kr.addWidget(self._openai_key, 1)
        layout.addWidget(key_row)

        # Anthropic key field
        self._anthropic_key = QLineEdit()
        self._anthropic_key.setPlaceholderText("sk-ant-...")
        self._anthropic_key.setEchoMode(QLineEdit.Password)
        existing_a = db_get_setting("anthropic_api_key", "") or ""
        if existing_a:
            self._anthropic_key.setText(existing_a)
        ank_row = QWidget(self)
        ank = QHBoxLayout(ank_row)
        ank.setContentsMargins(20, 0, 0, 0)
        ank.setSpacing(10)
        ank.addWidget(QLabel("Anthropic key:"))
        ank.addWidget(self._anthropic_key, 1)
        layout.addWidget(ank_row)

        # Ollama URL field
        self._ollama_url = QLineEdit()
        self._ollama_url.setPlaceholderText("http://localhost:11434")
        existing_url = db_get_setting("ollama_base_url", "http://localhost:11434") or ""
        self._ollama_url.setText(existing_url or "http://localhost:11434")
        url_row = QWidget(self)
        ur = QHBoxLayout(url_row)
        ur.setContentsMargins(20, 0, 0, 0)
        ur.setSpacing(10)
        ur.addWidget(QLabel("Ollama URL:"))
        ur.addWidget(self._ollama_url, 1)
        layout.addWidget(url_row)

        # Apply current choice
        if current == "openai":
            self._rb_openai.setChecked(True)
        elif current == "anthropic":
            self._rb_anthropic.setChecked(True)
        elif current in ("local", "ollama", "auto"):
            self._rb_ollama.setChecked(True)
        else:
            self._rb_none.setChecked(True)

        self._rb_none.toggled.connect(lambda _on: self._sync_rows())
        self._rb_openai.toggled.connect(lambda _on: self._sync_rows())
        self._rb_anthropic.toggled.connect(lambda _on: self._sync_rows())
        self._rb_ollama.toggled.connect(lambda _on: self._sync_rows())
        self._sync_rows()

        layout.addStretch(1)

    def _sync_rows(self) -> None:
        self._openai_key.parentWidget().setEnabled(self._rb_openai.isChecked())
        self._anthropic_key.parentWidget().setEnabled(self._rb_anthropic.isChecked())
        self._ollama_url.parentWidget().setEnabled(self._rb_ollama.isChecked())

    def validatePage(self) -> bool:
        if self._rb_openai.isChecked():
            db_set_setting("parser_backend", "openai")
            db_set_setting("openai_api_key", self._openai_key.text().strip())
        elif self._rb_anthropic.isChecked():
            db_set_setting("parser_backend", "anthropic")
            db_set_setting("anthropic_api_key", self._anthropic_key.text().strip())
        elif self._rb_ollama.isChecked():
            db_set_setting("parser_backend", "local")
            db_set_setting("ollama_base_url", self._ollama_url.text().strip() or "http://localhost:11434")
        else:
            db_set_setting("parser_backend", "none")
        return True


class DownloadsPage(QWizardPage):
    def __init__(self, wizard_ref):
        super().__init__()
        self._wizard = wizard_ref
        self._all_done = False
        self.setTitle(" ")
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(_h1("Downloading models"))
        self._caption = _muted(
            "Hang tight. Fetching the speech-to-text model and wake-word "
            "files so your first mic click is instant."
        )
        layout.addWidget(self._caption)

        self._progress = QProgressBar(self)
        self._progress.setRange(0, 0)  # indeterminate during work
        layout.addWidget(self._progress)

        self._status = QLabel("Waiting…", self)
        self._status.setStyleSheet("font-family: 'JetBrains Mono', 'Consolas', monospace; font-size: 12px;")
        layout.addWidget(self._status)

        self._errors = QLabel("", self)
        self._errors.setWordWrap(True)
        self._errors.setStyleSheet("color: #f87171; font-size: 12px;")
        layout.addWidget(self._errors)

        layout.addStretch(1)

        self._mgr = DownloadManager(self)
        self._mgr.task_started.connect(self._on_started)
        self._mgr.task_done.connect(self._on_done)
        self._mgr.task_failed.connect(self._on_failed)
        self._mgr.all_done.connect(self._on_all_done)

    def initializePage(self) -> None:
        whisper_model = db_get_setting("whisper_model", "base.en") or "base.en"
        tasks = [{"type": "whisper", "model": whisper_model}]
        wake_page = self._wizard.page_wake
        if wake_page.wants_download():
            tasks.append({"type": "openwakeword"})

        self._status.setText("Starting…")
        self._errors.setText("")
        self._progress.setRange(0, 0)
        self._all_done = False
        self._wizard.button(QWizard.NextButton).setEnabled(False)
        self._wizard.button(QWizard.BackButton).setEnabled(False)
        self._mgr.start(tasks)

    def isComplete(self) -> bool:
        return self._all_done

    @Slot(str)
    def _on_started(self, label: str) -> None:
        self._status.setText(f"Downloading: {label}…")

    @Slot(str)
    def _on_done(self, label: str) -> None:
        self._status.setText(f"Finished: {label}")

    @Slot(str, str)
    def _on_failed(self, label: str, err: str) -> None:
        existing = self._errors.text()
        line = f"{label} failed: {err}"
        self._errors.setText(f"{existing}\n{line}".strip())

    @Slot(bool)
    def _on_all_done(self, ok: bool) -> None:
        self._all_done = True
        self._progress.setRange(0, 1)
        self._progress.setValue(1)
        if ok:
            self._status.setText("All downloads complete ✓")
        else:
            self._status.setText("Finished with errors, see below. You can retry later from Settings.")
        self._wizard.button(QWizard.NextButton).setEnabled(True)
        self._wizard.button(QWizard.BackButton).setEnabled(True)
        self.completeChanged.emit()


class DonePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle(" ")
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(_h1("You're all set"))
        layout.addWidget(_muted(
            "Click Finish to start using Voice Notes. Re-run this wizard any "
            "time from Settings → Re-run setup."
        ))
        layout.addStretch(1)


# ── Wizard ────────────────────────────────────────────────────


class SetupWizard(QWizard):
    """Run with .exec(). Returns QDialog.Accepted on Finish, Rejected on cancel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Voice Notes — Setup")
        self.setMinimumSize(640, 520)
        self.setWizardStyle(QWizard.ModernStyle)
        icon_path = _ASSETS / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.page_welcome = WelcomePage()
        self.page_whisper = WhisperPage()
        self.page_wake = WakeWordPage()
        self.page_ai = AIBackendPage()
        self.page_downloads = DownloadsPage(self)
        self.page_done = DonePage()

        self.addPage(self.page_welcome)
        self.addPage(self.page_whisper)
        self.addPage(self.page_wake)
        self.addPage(self.page_ai)
        self.addPage(self.page_downloads)
        self.addPage(self.page_done)

        self.setButtonText(QWizard.FinishButton, "Finish")
        self.setOption(QWizard.NoBackButtonOnStartPage, True)

    def accept(self) -> None:
        db_set_setting("first_run_complete", "1")
        super().accept()

    def reject(self) -> None:
        # User hit Cancel / closed the window. Don't nag them again — they
        # can re-run from Settings if they want.
        db_set_setting("first_run_complete", "1")
        super().reject()
