"""Sidebar — 220px nav with section labels, accent-glow active state, footer status dot.

Matches AgeniusDesk's sidebar pattern:
- 18px logo with accent-coloured second word
- 10px uppercase section labels (1.2px tracking)
- Nav buttons with left accent-border on active
- AL toggle pinned mid-list
- Footer with pulsing status dot + version + gear icon
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .helpers import restyle
from .widgets.status_dot import StatusDot


class _SectionLabel(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text.upper(), parent)
        self.setProperty("class", "sectionLabel")


class _Divider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "divider")
        self.setFixedHeight(1)


class Sidebar(QFrame):
    """Left navigation sidebar.

    Emits `nav_changed(str)` when the user picks a destination.
    Emits `al_toggle_requested(bool)` when the AL row is toggled.
    Emits `settings_requested()` when the gear is clicked.
    """

    nav_changed          = Signal(str)
    al_toggle_requested  = Signal(bool)
    settings_requested   = Signal()

    NAV_ITEMS = (
        ("capture", "🎙  Capture"),
        ("task",    "✓  Tasks"),
        ("note",    "📝  Notes"),
    )

    def __init__(self, parent=None, version: str = "v3.0.0-dev"):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(220)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self._version = version
        self._buttons: dict[str, QPushButton] = {}
        self._active_key: str = "capture"
        self._al_on: bool = False

        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Logo ───────────────────────────────────────────────
        logo_row = QWidget(self)
        logo_layout = QHBoxLayout(logo_row)
        logo_layout.setContentsMargins(16, 18, 16, 4)
        logo_layout.setSpacing(0)  # butt "Agenius" and "Note" together to match AgeniusDesk

        logo_a = QLabel("Agenius", logo_row)
        logo_a.setObjectName("sidebarLogo")
        logo_b = QLabel("Note", logo_row)
        logo_b.setObjectName("sidebarLogoAccent")
        logo_layout.addWidget(logo_a)
        logo_layout.addWidget(logo_b)
        logo_layout.addStretch(1)
        outer.addWidget(logo_row)

        version_label = QLabel(self._version, self)
        version_label.setObjectName("sidebarVersion")
        outer.addWidget(version_label)

        # ── Workspace section ──────────────────────────────────
        outer.addWidget(_SectionLabel("Workspace", self))
        for key, label in self.NAV_ITEMS:
            btn = self._make_nav_btn(label, key)
            outer.addWidget(btn)
            self._buttons[key] = btn

        outer.addWidget(_Divider(self))

        # ── Modes section ──────────────────────────────────────
        outer.addWidget(_SectionLabel("Modes", self))
        self._al_btn = self._make_nav_btn("👂  Active Listening", "_al_toggle")
        self._al_btn.clicked.disconnect()  # bypass nav_changed; use a toggle instead
        self._al_btn.clicked.connect(self._on_al_clicked)
        self._al_btn.setProperty("active", False)
        outer.addWidget(self._al_btn)

        # Spacer to push footer down
        outer.addStretch(1)

        # ── Footer ─────────────────────────────────────────────
        footer = QFrame(self)
        footer.setObjectName("sidebarFooter")
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(14, 10, 10, 10)
        f_layout.setSpacing(8)

        self._status_dot = StatusDot(footer, state="idle")
        f_layout.addWidget(self._status_dot)

        self._status_text = QLabel("Idle", footer)
        self._status_text.setObjectName("sidebarFooterText")
        f_layout.addWidget(self._status_text)

        f_layout.addStretch(1)

        gear = QPushButton("⚙", footer)
        gear.setObjectName("gearBtn")
        gear.setCursor(Qt.PointingHandCursor)
        gear.setFixedSize(28, 28)
        gear.setToolTip("Settings")
        gear.clicked.connect(self.settings_requested.emit)
        f_layout.addWidget(gear)

        outer.addWidget(footer)

        # Default selection
        self.set_active("capture")


    def _make_nav_btn(self, label: str, key: str) -> QPushButton:
        btn = QPushButton(label, self)
        btn.setObjectName("navBtn")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn.setMinimumHeight(34)
        btn.setProperty("active", False)
        btn.clicked.connect(lambda _checked=False, k=key: self._on_nav_clicked(k))
        return btn

    # ── Public API ────────────────────────────────────────────

    def set_active(self, key: str) -> None:
        self._active_key = key
        for k, btn in self._buttons.items():
            btn.setProperty("active", k == key)
            restyle(btn)

    def set_status(self, text: str, dot_state: str = "idle") -> None:
        self._status_text.setText(text)
        self._status_dot.set_state(dot_state)

    def set_al_active(self, on: bool) -> None:
        self._al_on = bool(on)
        self._al_btn.setProperty("active", self._al_on)
        restyle(self._al_btn)

    # ── Internals ─────────────────────────────────────────────

    def _on_nav_clicked(self, key: str) -> None:
        if key != self._active_key:
            self.set_active(key)
        self.nav_changed.emit(key)

    def _on_al_clicked(self) -> None:
        self._al_on = not self._al_on
        self._al_btn.setProperty("active", self._al_on)
        restyle(self._al_btn)
        self.al_toggle_requested.emit(self._al_on)
