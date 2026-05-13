"""QSS template + render() — single source of visual truth for v3.

Uses string.Template ($token) so QSS curly braces don't need escaping.

Key design choices vs CSS:
- Qt QSS has no `box-shadow` — focus rings are border-color swaps with a 1px
  reserve to avoid reflowing neighbours.
- Property selectors `[active="true"]`, `[state="recording"]` need the widget
  to be re-polished after a property change. See ui.helpers.restyle().
- rgba() is supported in Qt 6 for backgrounds, borders, and colors.
"""

from __future__ import annotations

from string import Template

_QSS_TEMPLATE = Template(r"""
/* ============================================================
   AgeniusDesk for PySide6  ·  Voice Notes v3
   ============================================================ */

QWidget {
    background: $bg_void;
    color: $text_primary;
    font-family: "Inter", "Segoe UI", -apple-system, sans-serif;
    font-size: 13px;
    selection-background-color: $accent_glow;
    selection-color: $text_primary;
}

QMainWindow, QDialog {
    background: $bg_void;
}

/* ───────── Sidebar ─────────────────────────────────────────── */

QFrame#sidebar {
    background: $bg_sidebar;
    border: none;
    border-right: 1px solid $border_dim;
}

QLabel#sidebarLogo {
    color: $text_primary;
    font-size: 18px;
    font-weight: 700;
    letter-spacing: -0.5px;
    padding: 18px 16px 4px 16px;
    background: transparent;
}
QLabel#sidebarLogoAccent {
    color: $accent;
    font-size: 18px;
    font-weight: 700;
    letter-spacing: -0.5px;
    background: transparent;
}
QLabel#sidebarVersion {
    color: $text_dim;
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 11px;
    padding: 0 16px 12px 16px;
    background: transparent;
}

QLabel.sectionLabel {
    color: $text_dim;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.2px;
    padding: 14px 18px 4px 18px;
    background: transparent;
}

QFrame.divider {
    background: $border_dim;
    max-height: 1px;
    min-height: 1px;
    margin: 8px 12px;
    border: none;
}

QPushButton#navBtn {
    background: transparent;
    border: none;
    border-left: 2px solid transparent;
    color: $text_secondary;
    font-size: 13px;
    font-weight: 500;
    padding: 9px 12px 9px 16px;
    text-align: left;
    border-radius: 0;
}
QPushButton#navBtn:hover {
    background: $bg_hover;
    color: $text_primary;
}
QPushButton#navBtn:pressed {
    background: $bg_hover;
}
QPushButton#navBtn[active="true"] {
    background: $accent_glow;
    color: $accent;
    border-left: 2px solid $accent;
    font-weight: 600;
}

/* Sidebar footer */

QFrame#sidebarFooter {
    background: $bg_sidebar;
    border-top: 1px solid $border_dim;
}
QLabel#sidebarFooterText {
    color: $text_dim;
    font-size: 11px;
    background: transparent;
}
QPushButton#gearBtn {
    background: transparent;
    border: none;
    color: $text_secondary;
    font-size: 16px;
    padding: 6px;
    border-radius: ${radius}px;
}
QPushButton#gearBtn:hover {
    background: $bg_hover;
    color: $text_primary;
}

/* ───────── Status dot ──────────────────────────────────────── */

QFrame#statusDot {
    border-radius: 4px;
    background: $text_dim;
    min-width: 8px;
    max-width: 8px;
    min-height: 8px;
    max-height: 8px;
    border: none;
}
QFrame#statusDot[state="online"]    { background: $success; }
QFrame#statusDot[state="offline"]   { background: $error;   }
QFrame#statusDot[state="checking"]  { background: $warning; }
QFrame#statusDot[state="idle"]      { background: $text_dim; }
QFrame#statusDot[state="active"]    { background: $accent;  }

/* ───────── Active Listening status bar ─────────────────────── */

QFrame#alStatusBar {
    background: $bg_panel_solid;
    border: none;
    border-bottom: 1px solid $border_dim;
    min-height: 36px;
    max-height: 36px;
}
QFrame#alStatusBar[state="loading"]        { background: $info_glow; }
QFrame#alStatusBar[state="listening"]      { background: $info_glow; }
QFrame#alStatusBar[state="wake-detected"]  { background: $accent_glow; }
QFrame#alStatusBar[state="recording"]      { background: $error_glow; }
QFrame#alStatusBar[state="transcribing"]   { background: $warning_glow; }
QFrame#alStatusBar[state="parsing"]        { background: $accent_glow; }

QLabel#alStatusText {
    color: $text_primary;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.3px;
    background: transparent;
}
QFrame#alStatusBar[state="listening"] QLabel#alStatusText      { color: $info; }
QFrame#alStatusBar[state="wake-detected"] QLabel#alStatusText  { color: $accent; }
QFrame#alStatusBar[state="recording"] QLabel#alStatusText      { color: $error; }
QFrame#alStatusBar[state="transcribing"] QLabel#alStatusText   { color: $warning; }
QFrame#alStatusBar[state="parsing"] QLabel#alStatusText        { color: $accent; }

/* ───────── Main content area ───────────────────────────────── */

QWidget#mainArea {
    background: $bg_void;
}

QLabel.h1 {
    color: $text_primary;
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.3px;
    background: transparent;
}
QLabel.h2 {
    color: $text_primary;
    font-size: 16px;
    font-weight: 600;
    background: transparent;
}
QLabel.muted {
    color: $text_secondary;
    background: transparent;
}
QLabel.dim {
    color: $text_dim;
    background: transparent;
}
QLabel.mono {
    font-family: "JetBrains Mono", "Consolas", monospace;
}

/* ───────── Inputs ──────────────────────────────────────────── */

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: $bg_input_solid;
    border: 1px solid $border_mid;
    border-radius: ${radius}px;
    padding: 8px 12px;
    color: $text_primary;
    font-size: 13px;
    selection-background-color: $accent_glow;
}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover,
QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {
    border: 1px solid $border_bright;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid $accent;
}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
    color: $text_dim;
    background: $bg_panel_solid;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox::down-arrow {
    image: none;
    width: 8px;
    height: 8px;
    border-left: 1px solid $text_secondary;
    border-bottom: 1px solid $text_secondary;
}
QComboBox QAbstractItemView {
    background: $bg_panel_solid;
    border: 1px solid $border_mid;
    border-radius: ${radius}px;
    color: $text_primary;
    padding: 4px;
    selection-background-color: $accent_glow;
    selection-color: $accent;
    outline: 0;
}

/* ───────── Buttons ─────────────────────────────────────────── */

QPushButton {
    background: $bg_input_solid;
    border: 1px solid $border_mid;
    border-radius: ${radius}px;
    color: $text_primary;
    font-size: 13px;
    font-weight: 500;
    padding: 8px 16px;
}
QPushButton:hover {
    background: $bg_hover_solid;
    border: 1px solid $border_bright;
}
QPushButton:pressed {
    background: $bg_input_solid;
}
QPushButton:disabled {
    color: $text_dim;
    border: 1px solid $border_dim;
}

QPushButton#primary {
    background: $accent;
    border: 1px solid $accent;
    color: white;
    font-weight: 600;
}
QPushButton#primary:hover {
    background: $accent_hover;
    border: 1px solid $accent_hover;
}
QPushButton#primary:pressed {
    background: $accent_pressed;
    border: 1px solid $accent_pressed;
}

QPushButton#ghost {
    background: transparent;
    border: 1px solid transparent;
}
QPushButton#ghost:hover {
    background: $bg_hover;
    border: 1px solid $border_dim;
}

QPushButton#danger {
    color: $error;
    border: 1px solid $error_glow;
}
QPushButton#danger:hover {
    background: $error_glow;
    border: 1px solid $error;
}

QPushButton#success {
    color: $success;
    border: 1px solid $success_glow;
}
QPushButton#success:hover {
    background: $success_glow;
    border: 1px solid $success;
}

/* Big mic button — face is the QIcon (mic_button.png / mic_button_recording.png),
   so the button itself stays transparent. */
QPushButton#micBtn {
    background: transparent;
    border: none;
    border-radius: 0;
    color: transparent;
    min-width: 56px;
    max-width: 56px;
    min-height: 56px;
    max-height: 56px;
    padding: 0;
}
QPushButton#micBtn:hover {
    background: $bg_hover_solid;
    border-radius: 12px;
}
QPushButton#micBtn:pressed {
    background: transparent;
}

/* ───────── Cards ───────────────────────────────────────────── */

QFrame.card {
    background: $bg_card;
    border: 1px solid $border_dim;
    border-radius: ${radius_lg}px;
    padding: 0px;
}
QFrame.card:hover {
    border: 1px solid $border_bright;
}
QFrame.card[done="true"] {
    background: $bg_card_done;
}

QFrame#cardAccent {
    background: $accent;
    border: none;
    border-top-left-radius: ${radius_lg}px;
    border-bottom-left-radius: ${radius_lg}px;
    min-width: 3px;
    max-width: 3px;
}
QFrame#cardAccent[kind="task"]      { background: $accent; }
QFrame#cardAccent[kind="note"]      { background: $info;   }
QFrame#cardAccent[kind="task-done"] { background: $success; }
QFrame#cardAccent[kind="note-done"] { background: $border_mid; }

QLabel#cardTitle {
    color: $text_primary;
    font-size: 14px;
    font-weight: 600;
    background: transparent;
}
QLabel#cardBody {
    color: $text_secondary;
    font-size: 12px;
    background: transparent;
}
QLabel#cardMeta {
    color: $text_dim;
    font-size: 11px;
    font-family: "JetBrains Mono", "Consolas", monospace;
    background: transparent;
}

/* ───────── Pills + chips ───────────────────────────────────── */

QLabel.pill {
    padding: 2px 10px;
    border-radius: 9px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    background: $border_mid;
    color: $text_dim;
}
QLabel.pill[level="high"]   { background: $error_glow;   color: $error;   }
QLabel.pill[level="normal"] { background: $info_glow;    color: $info;    }
QLabel.pill[level="low"]    { background: $success_glow; color: $success; }

QLabel.tagChip {
    padding: 2px 8px;
    border-radius: 9px;
    background: $bg_input_solid;
    color: $text_secondary;
    font-size: 11px;
    border: 1px solid $border_dim;
}

/* ───────── ScrollArea + ScrollBar ──────────────────────────── */

QScrollArea {
    background: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}

QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: $border_mid;
    border-radius: 3px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: $border_bright; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: $border_mid;
    border-radius: 3px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover { background: $border_bright; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

/* ───────── Dialog (Settings) ───────────────────────────────── */

QDialog {
    background: $bg_panel_solid;
}
QFrame#dialogHeader {
    background: $bg_panel_solid;
    border-bottom: 1px solid $border_dim;
}
QFrame#dialogFooter {
    background: $bg_panel_solid;
    border-top: 1px solid $border_dim;
}
QFrame.settingsSection {
    background: transparent;
    border: 1px solid $border_dim;
    border-radius: ${radius_lg}px;
}
QLabel.settingsSectionLabel {
    color: $text_primary;
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}
QLabel.fieldLabel {
    color: $text_secondary;
    font-size: 12px;
    font-weight: 500;
    background: transparent;
}
QLabel.fieldHint {
    color: $text_dim;
    font-size: 11px;
    background: transparent;
}

/* Theme selector segmented control */
QPushButton#themeSeg {
    border-radius: 0;
    background: $bg_input_solid;
    border: 1px solid $border_mid;
}
QPushButton#themeSeg:hover {
    background: $bg_hover_solid;
}
QPushButton#themeSeg[active="true"] {
    background: $accent_glow;
    color: $accent;
    border: 1px solid $accent;
    font-weight: 600;
}

/* ───────── Quick todos right pane ──────────────────────────── */

QFrame#quickTodosPanel {
    background: $bg_sidebar;
    border-left: 1px solid $border_dim;
}
QFrame#qtHeader { background: transparent; }
QLabel#qtTitle {
    font-weight: 600;
    font-size: 14px;
    color: $text_primary;
}
QLabel#qtCount {
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 11px;
    color: $text_secondary;
    background: $bg_input_solid;
    border-radius: 8px;
    padding: 1px 7px;
}
QPushButton#qtChevron {
    background: transparent;
    border: none;
    color: $text_secondary;
    font-size: 16px;
    font-weight: 600;
    padding: 0;
}
QPushButton#qtChevron:hover { color: $accent; }
QPushButton#qtClearBtn {
    background: transparent;
    border: none;
    color: $text_dim;
    font-size: 11px;
    padding: 2px 6px;
}
QPushButton#qtClearBtn:hover { color: $accent; }

QFrame#qtAddRow { background: transparent; }
QLineEdit#qtInput {
    background: $bg_input_solid;
    border: 1px solid $border_mid;
    border-radius: ${radius}px;
    padding: 6px 10px;
    font-size: 13px;
}
QLineEdit#qtInput:focus { border: 1px solid $accent; }
QPushButton#qtAddBtn {
    background: transparent;
    border: none;
    color: $accent;
    font-size: 26px;
    font-weight: 700;
    padding: 0 0 4px 0;
    min-width: 30px;
    max-width: 30px;
    min-height: 30px;
    max-height: 30px;
}
QPushButton#qtAddBtn:hover { color: $accent_hover; }
QPushButton#qtAddBtn:pressed { color: $accent; }

QLabel#qtVoiceHint {
    color: $text_dim;
    font-size: 11px;
    padding: 0 12px 8px 12px;
    background: transparent;
}

QScrollArea#qtScroll { background: transparent; border: none; }
QWidget#qtListHost { background: transparent; }

QFrame#qtRow { background: transparent; border-radius: 4px; }
QFrame#qtRow:hover { background: $bg_hover_solid; }
QLabel#qtRowText { color: $text_primary; font-size: 13px; }
QLabel#qtRowText[done="true"] { color: $text_dim; }
QPushButton#qtRowDelete {
    background: transparent;
    border: none;
    color: $text_dim;
    font-size: 14px;
    font-weight: 600;
    padding: 0;
}
QPushButton#qtRowDelete:hover { color: $accent; }

QLabel#qtEmpty {
    color: $text_dim;
    font-size: 12px;
    padding: 20px 12px;
}

QCheckBox#qtCheck {
    spacing: 0;
    background: transparent;
}
QCheckBox#qtCheck::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid $border_mid;
    border-radius: 4px;
    background: $bg_input_solid;
}
QCheckBox#qtCheck::indicator:hover {
    border: 1px solid $accent;
}
QCheckBox#qtCheck::indicator:checked {
    background: $accent;
    border: 1px solid $accent;
}

/* ───────── Misc ────────────────────────────────────────────── */

QToolTip {
    background: $bg_panel_solid;
    color: $text_primary;
    border: 1px solid $border_mid;
    border-radius: ${radius}px;
    padding: 4px 8px;
}

QSplitter::handle {
    background: $border_dim;
}
QSplitter::handle:horizontal { width: 1px; }
QSplitter::handle:vertical   { height: 1px; }
""")


def render(tokens: dict[str, str]) -> str:
    """Substitute every token in the QSS template."""
    return _QSS_TEMPLATE.substitute(tokens)
