"""The page shown when no file is open."""
import os

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
                             QScrollArea, QVBoxLayout, QWidget)

from . import icons, theme, widgets

SHORTCUTS = [
    ("Ctrl+P", "Go to file"),
    ("Ctrl+Shift+P", "Command palette"),
    ("Ctrl+S", "Save"),
    ("Ctrl+F", "Filter rows"),
    ("Ctrl+G", "Go to row"),
    ("Ctrl+I", "Toggle inspector"),
    ("Ctrl+B", "Toggle sidebar"),
    ("Ctrl+Z / Ctrl+Y", "Undo / redo"),
]

TIPS = [
    "STB rows are ids that every other table points at: rows are appended or cleared, never deleted.",
    "A cell that differs from the file on disk is tinted, with a marker in its corner.",
    "Saving re-reads the written bytes and refuses if they do not match; the original goes to build/dev-studio/backups.",
    "Copy and paste use tab-separated text, so rows move to and from a spreadsheet.",
]


class Welcome(QScrollArea):
    openRequested = pyqtSignal(str)
    chooseRootRequested = pyqtSignal()
    paletteRequested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Welcome")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        page = QWidget()
        page.setObjectName("Welcome")
        self.setWidget(page)
        outer = QHBoxLayout(page)
        outer.addStretch(1)
        col = QVBoxLayout()
        col.setContentsMargins(24, 64, 24, 40)
        col.setSpacing(0)
        w = QWidget()
        w.setLayout(col)
        w.setMaximumWidth(780)
        w.setMinimumWidth(520)
        outer.addWidget(w, 10)
        outer.addStretch(1)

        head = QHBoxLayout()
        head.setSpacing(16)
        self.logo = QLabel()
        head.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignTop)
        tbox = QVBoxLayout()
        tbox.setSpacing(2)
        title = QLabel("Rose Dev Studio")
        title.setFont(theme.ui_font(22, QFont.Weight.DemiBold))
        tbox.addWidget(title)
        sub = QLabel("Edit ROSE Online data tables and string files, through the same codecs the scripts use.")
        sub.setObjectName("Dim")
        sub.setWordWrap(True)
        tbox.addWidget(sub)
        head.addLayout(tbox, 1)
        col.addLayout(head)
        col.addSpacing(34)

        grid = QGridLayout()
        grid.setHorizontalSpacing(40)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        start = QVBoxLayout()
        start.setSpacing(2)
        start.addWidget(widgets.caps_label("Start"))
        start.addSpacing(6)
        self._start_buttons = []
        for icon, text, slot in (
                ("search", "Open a file…", lambda: self.paletteRequested.emit("")),
                ("command", "Run a command…", lambda: self.paletteRequested.emit(">")),
                ("folder", "Open another data folder…", self.chooseRootRequested.emit)):
            b = QPushButton(text)
            b.setObjectName("ListItem")
            b.setIconSize(QSize(16, 16))
            b._icon_name = icon
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            start.addWidget(b)
            self._start_buttons.append(b)
        start.addSpacing(18)
        start.addWidget(widgets.caps_label("Data folder"))
        start.addSpacing(6)
        self.root = QLabel("—")
        self.root.setWordWrap(True)
        self.root.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        start.addWidget(self.root)
        self.root_stats = QLabel("")
        self.root_stats.setObjectName("Faint")
        start.addWidget(self.root_stats)
        start.addStretch(1)
        grid.addLayout(start, 0, 0)

        recent = QVBoxLayout()
        recent.setSpacing(2)
        recent.addWidget(widgets.caps_label("Recent"))
        recent.addSpacing(6)
        self.recent_box = QVBoxLayout()
        self.recent_box.setSpacing(1)
        recent.addLayout(self.recent_box)
        recent.addStretch(1)
        grid.addLayout(recent, 0, 1)
        col.addLayout(grid)
        col.addSpacing(36)

        bottom = QGridLayout()
        bottom.setHorizontalSpacing(40)
        bottom.setColumnStretch(0, 1)
        bottom.setColumnStretch(1, 1)
        keys = QVBoxLayout()
        keys.setSpacing(6)
        keys.addWidget(widgets.caps_label("Keyboard"))
        keys.addSpacing(4)
        for k, what in SHORTCUTS:
            row = QHBoxLayout()
            a = QLabel(what)
            a.setObjectName("Dim")
            b = QLabel(k)
            b.setFont(theme.mono_font(8.4))
            b.setObjectName("Faint")
            row.addWidget(a)
            row.addStretch(1)
            row.addWidget(b)
            keys.addLayout(row)
        bottom.addLayout(keys, 0, 0, Qt.AlignmentFlag.AlignTop)
        tips = QVBoxLayout()
        tips.setSpacing(8)
        tips.addWidget(widgets.caps_label("Good to know"))
        tips.addSpacing(2)
        for tip in TIPS:
            lab = QLabel(tip)
            lab.setWordWrap(True)
            lab.setObjectName("Dim")
            tips.addWidget(lab)
        bottom.addLayout(tips, 0, 1, Qt.AlignmentFlag.AlignTop)
        col.addLayout(bottom)
        col.addStretch(1)
        self.retint()

    def retint(self):
        t = theme.current()
        self.logo.setPixmap(icons.pixmap("logo", t.accent, 52, stroke=1.8))
        for b in self._start_buttons:
            b.setIcon(icons.icon(b._icon_name, t.accent))

    def set_root(self, root, n_stb=0, n_stl=0):
        self.root.setText(root or "No data folder chosen")
        self.root_stats.setText("%d tables  ·  %d string tables" % (n_stb, n_stl) if root else "")

    def set_recent(self, paths, root):
        widgets.clear_layout(self.recent_box)
        shown = [p for p in paths if os.path.exists(p)][:8]
        if not shown:
            lab = QLabel("Files you open show up here.")
            lab.setObjectName("Faint")
            self.recent_box.addWidget(lab)
            return
        t = theme.current()
        for p in shown:
            kind = os.path.splitext(p)[1].lower()
            b = QPushButton()
            b.setObjectName("ListItem")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setIcon(icons.icon("table" if kind == ".stb" else "text", t.match if kind == ".stb" else t.success))
            try:
                rel = os.path.relpath(os.path.dirname(p), root) if root else os.path.dirname(p)
            except ValueError:
                rel = os.path.dirname(p)
            b.setText("%s     %s" % (os.path.basename(p), rel.replace("\\", "/")))
            b.setToolTip(p)
            b.clicked.connect(lambda _c=False, p=p: self.openRequested.emit(p))
            self.recent_box.addWidget(b)
