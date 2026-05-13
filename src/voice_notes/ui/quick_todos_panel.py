"""Right-side quick-todo pane.

Fixed 280px wide, collapsible to 36px. Quick-add via text box + Enter or +.
Scrollable list of checkboxes; checking marks done (strike-through). Delete
on hover. Clear-done button purges completed items.

Voice command path (handled in workers, not here): when a transcript starts
with "quick todo:", "remind me to", etc., the worker inserts via qt_create()
and emits signals.quick_todos_changed; this panel listens and refreshes.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core.db import (
    db_get_setting,
    db_set_setting,
    qt_clear_done,
    qt_create,
    qt_delete,
    qt_list,
    qt_toggle,
)
from .signals import AppSignals


EXPANDED_WIDTH = 280
COLLAPSED_WIDTH = 36


class _TodoRow(QFrame):
    """One row in the todo list: [checkbox] [text] [× delete on hover]."""

    toggle_requested = Signal(int)
    delete_requested = Signal(int)

    def __init__(self, todo: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("qtRow")
        self._id = int(todo["id"])
        self._done = bool(todo.get("done"))

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 4, 6, 4)
        row.setSpacing(8)

        self._cb = QCheckBox(self)
        self._cb.setObjectName("qtCheck")
        self._cb.setChecked(self._done)
        self._cb.toggled.connect(self._on_toggled)
        row.addWidget(self._cb)

        self._label = QLabel(todo.get("text") or "", self)
        self._label.setObjectName("qtRowText")
        self._label.setWordWrap(True)
        self._label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._apply_struck()
        row.addWidget(self._label, 1)

        self._del = QPushButton("×", self)
        self._del.setObjectName("qtRowDelete")
        self._del.setCursor(Qt.PointingHandCursor)
        self._del.setFixedSize(20, 20)
        self._del.setToolTip("Delete")
        self._del.clicked.connect(lambda: self.delete_requested.emit(self._id))
        row.addWidget(self._del)

    def _apply_struck(self) -> None:
        font: QFont = self._label.font()
        font.setStrikeOut(self._done)
        self._label.setFont(font)
        self._label.setProperty("done", self._done)
        self._label.style().unpolish(self._label)
        self._label.style().polish(self._label)

    def _on_toggled(self, checked: bool) -> None:
        self._done = checked
        self._apply_struck()
        self.toggle_requested.emit(self._id)


class QuickTodosPanel(QFrame):
    """Collapsible right-side todo panel."""

    def __init__(self, signals: AppSignals, parent=None):
        super().__init__(parent)
        self.setObjectName("quickTodosPanel")
        self._signals = signals
        self._collapsed = (db_get_setting("qt_panel_collapsed", "0") or "0") == "1"

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self._build()
        self._wire()
        self._apply_collapsed()
        self.refresh()

    # ── Build ─────────────────────────────────────────────────

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header row: chevron + title + count
        header = QFrame(self)
        header.setObjectName("qtHeader")
        h = QHBoxLayout(header)
        h.setContentsMargins(8, 12, 10, 8)
        h.setSpacing(8)

        self._chevron = QPushButton("›", header)
        self._chevron.setObjectName("qtChevron")
        self._chevron.setCursor(Qt.PointingHandCursor)
        self._chevron.setFixedSize(22, 22)
        self._chevron.setToolTip("Collapse todos")
        self._chevron.clicked.connect(self._toggle_collapsed)
        h.addWidget(self._chevron)

        self._title = QLabel("Todos", header)
        self._title.setObjectName("qtTitle")
        h.addWidget(self._title)

        self._count = QLabel("0", header)
        self._count.setObjectName("qtCount")
        h.addWidget(self._count)

        h.addStretch(1)

        self._clear_btn = QPushButton("Clear done", header)
        self._clear_btn.setObjectName("qtClearBtn")
        self._clear_btn.setCursor(Qt.PointingHandCursor)
        self._clear_btn.setToolTip("Remove completed items")
        self._clear_btn.clicked.connect(self._on_clear_done)
        h.addWidget(self._clear_btn)

        outer.addWidget(header)

        # Add row
        add_row = QFrame(self)
        add_row.setObjectName("qtAddRow")
        a = QHBoxLayout(add_row)
        a.setContentsMargins(10, 4, 10, 8)
        a.setSpacing(6)

        self._input = QLineEdit(add_row)
        self._input.setObjectName("qtInput")
        self._input.setPlaceholderText("Add a todo, press Enter")
        self._input.returnPressed.connect(self._on_add)
        a.addWidget(self._input, 1)

        self._add_btn = QPushButton("+", add_row)
        self._add_btn.setObjectName("qtAddBtn")
        self._add_btn.setCursor(Qt.PointingHandCursor)
        self._add_btn.setToolTip("Add")
        self._add_btn.clicked.connect(self._on_add)
        a.addWidget(self._add_btn)

        outer.addWidget(add_row)

        # Voice-trigger hint, persistent under the input so users discover
        # routing prefixes without having to read the docs.
        self._voice_hint = QLabel(
            'Or say: "quick todo: …", "todo: …", "remind me to …"',
            self,
        )
        self._voice_hint.setObjectName("qtVoiceHint")
        self._voice_hint.setWordWrap(True)
        self._voice_hint.setToolTip(
            "Spoken prefixes that route a transcript here instead of saving it as a note:\n"
            "  • quick todo: …\n"
            "  • todo: …\n"
            "  • to-do: …\n"
            "  • remind me to …\n"
            "  • add to my list …\n"
            "  • add to the list …\n"
            "Hyphens are normalized (so 'quick-to-do' also matches)."
        )
        outer.addWidget(self._voice_hint)

        # Scrollable list
        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("qtScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.NoFrame)

        self._list_host = QWidget()
        self._list_host.setObjectName("qtListHost")
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(6, 6, 6, 6)
        self._list_layout.setSpacing(2)

        # Empty placeholder sits inside the scroll area so it shows up
        # where rows would, not parked at the bottom of the panel.
        self._empty_label = QLabel(
            "No todos yet.\nAdd one above or say\n“quick todo: …”",
            self._list_host,
        )
        self._empty_label.setObjectName("qtEmpty")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setVisible(False)
        self._list_layout.addWidget(self._empty_label)
        self._list_layout.addStretch(1)

        self._scroll.setWidget(self._list_host)
        outer.addWidget(self._scroll, 1)

    def _wire(self) -> None:
        self._signals.quick_todos_changed.connect(self.refresh)

    # ── Collapse ──────────────────────────────────────────────

    def _toggle_collapsed(self) -> None:
        self._collapsed = not self._collapsed
        db_set_setting("qt_panel_collapsed", "1" if self._collapsed else "0")
        self._apply_collapsed()

    def _apply_collapsed(self) -> None:
        if self._collapsed:
            self.setFixedWidth(COLLAPSED_WIDTH)
            self._chevron.setText("‹")
            self._chevron.setToolTip("Expand todos")
            self._title.setVisible(False)
            self._count.setVisible(False)
            self._clear_btn.setVisible(False)
            self._input.parentWidget().setVisible(False)
            self._voice_hint.setVisible(False)
            self._scroll.setVisible(False)
        else:
            self.setFixedWidth(EXPANDED_WIDTH)
            self._chevron.setText("›")
            self._chevron.setToolTip("Collapse todos")
            self._title.setVisible(True)
            self._count.setVisible(True)
            self._clear_btn.setVisible(True)
            self._input.parentWidget().setVisible(True)
            self._voice_hint.setVisible(True)
            self._scroll.setVisible(True)
            self._sync_empty_state()

    # ── Data refresh ──────────────────────────────────────────

    @Slot()
    def refresh(self) -> None:
        # Drop existing _TodoRow widgets; keep empty label + trailing stretch.
        i = 0
        while i < self._list_layout.count():
            w = self._list_layout.itemAt(i).widget()
            if isinstance(w, _TodoRow):
                self._list_layout.takeAt(i)
                w.setParent(None)
                w.deleteLater()
            else:
                i += 1

        todos = qt_list(include_done=True, done_limit=20)
        open_count = sum(1 for t in todos if not t["done"])
        self._count.setText(str(open_count))

        # Insert rows just before the empty label so order stays correct.
        empty_idx = self._list_layout.indexOf(self._empty_label)
        if empty_idx < 0:
            empty_idx = 0
        for t in todos:
            row = _TodoRow(t, self._list_host)
            row.toggle_requested.connect(self._on_toggle)
            row.delete_requested.connect(self._on_delete)
            self._list_layout.insertWidget(empty_idx, row)
            empty_idx += 1

        self._sync_empty_state(todos_count=len(todos))

    def _sync_empty_state(self, todos_count: int | None = None) -> None:
        if self._collapsed:
            self._empty_label.setVisible(False)
            return
        if todos_count is None:
            todos_count = sum(
                1 for i in range(self._list_layout.count())
                if isinstance(self._list_layout.itemAt(i).widget(), _TodoRow)
            )
        self._empty_label.setVisible(todos_count == 0)

    # ── Actions ───────────────────────────────────────────────

    @Slot()
    def _on_add(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        try:
            qt_create(text, source="typed")
        except ValueError:
            return
        self._input.clear()
        self.refresh()
        self._signals.quick_todos_changed.emit()

    @Slot(int)
    def _on_toggle(self, todo_id: int) -> None:
        qt_toggle(todo_id)
        self.refresh()
        self._signals.quick_todos_changed.emit()

    @Slot(int)
    def _on_delete(self, todo_id: int) -> None:
        qt_delete(todo_id)
        self.refresh()
        self._signals.quick_todos_changed.emit()

    @Slot()
    def _on_clear_done(self) -> None:
        qt_clear_done()
        self.refresh()
        self._signals.quick_todos_changed.emit()
