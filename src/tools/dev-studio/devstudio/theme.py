"""Colours, fonts and the one stylesheet.

Every colour the studio paints comes from a ``Theme``: the stylesheet is
generated from it, and custom-painted widgets (table cells, headers, the
explorer) read the same tokens through ``current()``. Nothing else in the
package names a colour, so a third theme is one more ``Theme(...)`` below.
"""
from dataclasses import dataclass, fields
from string import Template

from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PyQt6.QtWidgets import QApplication


@dataclass(frozen=True)
class Theme:
    name: str
    dark: bool
    bg_app: str        # menu bar, activity bar, status bar
    bg_side: str       # explorer, inspector
    bg_editor: str     # the grid
    bg_alt: str        # alternate grid rows
    bg_raised: str     # headers, popups, buttons
    bg_input: str
    bg_hover: str
    border: str
    border_strong: str
    grid: str
    text: str
    text_dim: str
    text_faint: str
    accent: str
    accent_text: str
    modified: str
    danger: str
    success: str
    match: str
    scroll: str
    scroll_hover: str


DARK = Theme(
    name="dark", dark=True,
    bg_app="#121419", bg_side="#171a20", bg_editor="#1b1e25", bg_alt="#1e2129",
    bg_raised="#23272f", bg_input="#14161b", bg_hover="#2b303a",
    border="#272b34", border_strong="#3a404c", grid="#252932",
    text="#dfe2e8", text_dim="#9aa2b1", text_faint="#606878",
    accent="#e8577e", accent_text="#ffffff",
    modified="#e5b45a", danger="#ef6461", success="#4cc38a", match="#5aa9e6",
    scroll="#363c47", scroll_hover="#4a5160",
)

LIGHT = Theme(
    name="light", dark=False,
    bg_app="#e9ebef", bg_side="#f3f4f6", bg_editor="#ffffff", bg_alt="#f8f9fb",
    bg_raised="#f5f6f8", bg_input="#ffffff", bg_hover="#e4e7ec",
    border="#dfe2e8", border_strong="#c9ced6", grid="#eceef2",
    text="#1d2128", text_dim="#566070", text_faint="#9aa1ad",
    accent="#d43d68", accent_text="#ffffff",
    modified="#c98a14", danger="#d64545", success="#2f9e6a", match="#2f7fc4",
    scroll="#c9ced6", scroll_hover="#aab1bc",
)

THEMES = {t.name: t for t in (DARK, LIGHT)}
_current = DARK


def current():
    return _current


def color(hex_, alpha=255):
    c = QColor(hex_)
    c.setAlpha(alpha)
    return c


def rgba(hex_, alpha):
    c = QColor(hex_)
    return "rgba(%d,%d,%d,%d)" % (c.red(), c.green(), c.blue(), alpha)


# ------------------------------------------------------------------ fonts
UI_FAMILY = "Segoe UI"
MONO_FAMILY = "Cascadia Mono"


def ui_font(pt=9.5, weight=QFont.Weight.Normal):
    f = QFont(UI_FAMILY)
    f.setPointSizeF(pt)
    f.setWeight(weight)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return f


def mono_font(pt=9.0):
    f = QFont(MONO_FAMILY)
    f.setStyleHint(QFont.StyleHint.Monospace)
    f.setPointSizeF(pt)
    return f


def caps_font(pt=7.8):
    """Small spaced capitals for section titles (EXPLORER, FIELDS ...)."""
    f = ui_font(pt, QFont.Weight.DemiBold)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.9)
    return f


def init_fonts():
    global MONO_FAMILY, UI_FAMILY
    fams = set(QFontDatabase.families())
    for cand in ("Segoe UI Variable Text", "Segoe UI", "Inter"):
        if cand in fams:
            UI_FAMILY = cand
            break
    for cand in ("Cascadia Mono", "JetBrains Mono", "Consolas"):
        if cand in fams:
            MONO_FAMILY = cand
            break


# ------------------------------------------------------------------ stylesheet
QSS = Template(r"""
QWidget { color: $text; }
QMainWindow, #Shell { background: $bg_app; }
QAbstractScrollArea { background: transparent; }

/* ---------- scrollbars: thin, rounded, no arrows ---------- */
QScrollBar:vertical { background: transparent; width: 12px; margin: 0; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 0; }
QScrollBar::handle:vertical { background: $scroll; min-height: 36px; border-radius: 3px; margin: 3px 3px 3px 3px; }
QScrollBar::handle:horizontal { background: $scroll; min-width: 36px; border-radius: 3px; margin: 3px 3px 3px 3px; }
QScrollBar::handle:hover { background: $scroll_hover; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* ---------- menus ---------- */
QMenuBar { background: $bg_app; border-bottom: 1px solid $border; padding: 2px 6px; }
QMenuBar::item { background: transparent; padding: 4px 10px; border-radius: 5px; color: $text_dim; }
QMenuBar::item:selected, QMenuBar::item:pressed { background: $bg_hover; color: $text; }
QMenu { background: $bg_raised; border: 1px solid $border_strong; padding: 6px; }
QMenu::item { padding: 6px 30px 6px 10px; border-radius: 5px; background: transparent; }
QMenu::item:selected { background: $accent_soft; }
QMenu::item:disabled { color: $text_faint; }
QMenu::separator { height: 1px; background: $border; margin: 5px 6px; }
QMenu::icon { padding-left: 6px; }

/* ---------- tooltips ---------- */
QToolTip { background: $bg_raised; color: $text; border: 1px solid $border_strong; padding: 6px 8px; }

/* ---------- inputs ---------- */
QLineEdit, QPlainTextEdit, QSpinBox {
    background: $bg_input; border: 1px solid $border; border-radius: 6px;
    padding: 4px 8px; selection-background-color: $accent; selection-color: $accent_text;
}
QLineEdit:hover, QPlainTextEdit:hover { border-color: $border_strong; }
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus { border-color: $accent; }
QLineEdit[modified="true"] { border-left: 3px solid $modified; }
QPlainTextEdit[modified="true"] { border-left: 3px solid $modified; }
QLineEdit:read-only { color: $text_dim; background: transparent; }

QComboBox { background: $bg_input; border: 1px solid $border; border-radius: 6px; padding: 4px 26px 4px 8px; }
QComboBox:hover { border-color: $border_strong; }
QComboBox:focus { border-color: $accent; }
QComboBox::drop-down { border: none; width: 22px; subcontrol-origin: padding; subcontrol-position: center right; }
QComboBox::down-arrow { image: url("$chevron_down"); width: 14px; height: 14px; }
QComboBox QAbstractItemView {
    background: $bg_raised; border: 1px solid $border_strong; outline: 0; padding: 4px;
    selection-background-color: $accent_soft; selection-color: $text;
}

/* ---------- buttons ---------- */
QPushButton {
    background: $bg_raised; border: 1px solid $border_strong; border-radius: 6px;
    padding: 5px 14px; min-height: 18px;
}
QPushButton:hover { background: $bg_hover; }
QPushButton:pressed { background: $border; }
QPushButton:disabled { color: $text_faint; border-color: $border; }
QPushButton#Primary { background: $accent; border-color: $accent; color: $accent_text; font-weight: 600; }
QPushButton#Primary:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton#Danger { color: $danger; }
QPushButton#Link { background: transparent; border: none; color: $accent; padding: 2px 4px; text-align: left; }
QPushButton#Link:hover { text-decoration: underline; }

QToolButton { background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 4px; }
QToolButton:hover { background: $bg_hover; }
QToolButton:pressed { background: $border; }
QToolButton:checked { background: $accent_soft; border-color: $accent_line; }
QToolButton#TextButton { padding: 4px 10px; color: $text_dim; }
QToolButton#TextButton:hover { color: $text; }
QToolButton::menu-indicator { image: none; width: 0; }

QCheckBox { spacing: 8px; color: $text_dim; }
QCheckBox:hover { color: $text; }

/* ---------- splitters ---------- */
QSplitter::handle { background: $border; }
QSplitter::handle:horizontal { width: 1px; }
QSplitter::handle:vertical { height: 1px; }

/* ---------- tabs ---------- */
QTabWidget::pane { border: none; background: $bg_editor; }
QTabBar { background: $bg_app; qproperty-drawBase: 0; }
QTabBar::tab {
    background: transparent; color: $text_dim; border: none; border-right: 1px solid $border;
    border-top: 2px solid transparent; padding: 0 6px 0 12px; height: 33px; min-width: 60px;
}
QTabBar::tab:hover:!selected { background: $bg_hover; color: $text; }
QTabBar::tab:selected { background: $bg_editor; color: $text; border-top: 2px solid $accent; }
QTabBar::scroller { width: 28px; }
QTabBar QToolButton { background: $bg_app; border: none; border-radius: 0; }

/* ---------- tables ---------- */
QTableView {
    background: $bg_editor; alternate-background-color: $bg_alt; border: none;
    gridline-color: $grid; outline: 0;
    selection-background-color: $accent_soft; selection-color: $text;
}
QTableView QLineEdit { border-radius: 0; border: 1px solid $accent; padding: 0 6px; background: $bg_input; }
QTableCornerButton::section { background: $bg_raised; border: none; border-right: 1px solid $border; border-bottom: 1px solid $border; }

QListView, QTreeView { background: transparent; border: none; outline: 0; }

/* ---------- named surfaces ---------- */
#ActivityBar { background: $bg_app; border-right: 1px solid $border; }
#ActivityBar QToolButton { border: none; border-radius: 0; border-left: 2px solid transparent; padding: 11px; }
#ActivityBar QToolButton:checked { background: transparent; border-left: 2px solid $accent; }
#ActivityBar QToolButton:hover { background: transparent; }
#Sidebar { background: $bg_side; }
#Inspector { background: $bg_side; }
#Inspector QScrollArea, #Inspector #InspectorBody { background: $bg_side; }
#EditorToolbar { background: $bg_editor; border-bottom: 1px solid $border; }
#Editor { background: $bg_editor; }
#Welcome { background: $bg_editor; }
#Welcome QPushButton#RecentItem {
    background: transparent; border: none; border-radius: 6px; padding: 6px 10px; text-align: left; color: $text;
}
#Welcome QPushButton#RecentItem:hover { background: $bg_hover; }
QStatusBar { background: $bg_app; border-top: 1px solid $border; min-height: 24px; }
QStatusBar::item { border: none; }
QStatusBar QLabel { color: $text_dim; padding: 0 6px; }

#Banner { background: $banner_bg; border-bottom: 1px solid $border; }
#Popup { background: $bg_raised; border: 1px solid $border_strong; border-radius: 10px; }
#Popup QLineEdit { background: transparent; border: none; border-bottom: 1px solid $border; border-radius: 0; padding: 10px 12px; }
#Toast { background: $bg_raised; border: 1px solid $border_strong; border-radius: 8px; }
#Segmented { background: $bg_input; border: 1px solid $border; border-radius: 7px; }
#Segmented QToolButton { padding: 3px 10px; border-radius: 5px; color: $text_dim; border: 1px solid transparent; }
#Segmented QToolButton:hover { color: $text; background: transparent; }
#Segmented QToolButton:checked { background: $bg_raised; color: $text; border: 1px solid $border_strong; }
#Chip { background: $bg_raised; border: 1px solid $border; border-radius: 9px; padding: 1px 8px; color: $text_dim; }
#ChipModified { background: $modified_soft; border: 1px solid $modified_line; border-radius: 9px; padding: 1px 8px; color: $modified; }
#Divider { background: $border_strong; }
#Dim { color: $text_dim; }
#Error { color: $danger; }
QPushButton#ListItem {
    background: transparent; border: none; border-radius: 6px; padding: 5px 8px; text-align: left; color: $text_dim;
}
QPushButton#ListItem:hover { background: $bg_hover; color: $text; }
#Faint { color: $text_faint; }
#Hint { color: $text_faint; padding: 2px 0; }
#Card { background: $bg_raised; border: 1px solid $border; border-radius: 8px; }
QDialog { background: $bg_side; }
QMessageBox { background: $bg_side; }
""")


def stylesheet(t, icon_path):
    tok = {f.name: getattr(t, f.name) for f in fields(t)}
    accent = QColor(t.accent)
    tok.update(
        accent_soft=rgba(t.accent, 52 if t.dark else 38),
        accent_line=rgba(t.accent, 110),
        accent_hover=accent.lighter(112).name() if t.dark else accent.darker(108).name(),
        modified_soft=rgba(t.modified, 36),
        modified_line=rgba(t.modified, 120),
        banner_bg=rgba(t.modified, 30),
        chevron_down=icon_path("chevron-down", t.text_dim).replace("\\", "/"),
    )
    return QSS.substitute(tok)


def palette(t):
    p = QPalette()
    R = QPalette.ColorRole
    p.setColor(R.Window, QColor(t.bg_side))
    p.setColor(R.WindowText, QColor(t.text))
    p.setColor(R.Base, QColor(t.bg_input))
    p.setColor(R.AlternateBase, QColor(t.bg_alt))
    p.setColor(R.Text, QColor(t.text))
    p.setColor(R.Button, QColor(t.bg_raised))
    p.setColor(R.ButtonText, QColor(t.text))
    p.setColor(R.Highlight, QColor(t.accent))
    p.setColor(R.HighlightedText, QColor(t.accent_text))
    p.setColor(R.ToolTipBase, QColor(t.bg_raised))
    p.setColor(R.ToolTipText, QColor(t.text))
    p.setColor(R.PlaceholderText, QColor(t.text_faint))
    p.setColor(R.Link, QColor(t.accent))
    p.setColor(R.Mid, QColor(t.border))
    p.setColor(R.Dark, QColor(t.border_strong))
    for role in (R.Text, R.WindowText, R.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(t.text_faint))
    return p


def apply(name):
    """Switch the whole application to theme ``name``."""
    global _current
    from . import icons
    _current = THEMES.get(name, DARK)
    app = QApplication.instance()
    app.setPalette(palette(_current))
    app.setStyleSheet(stylesheet(_current, icons.icon_file))
    icons.clear_cache()
    return _current
