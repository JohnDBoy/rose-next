"""Command palette: Ctrl+P finds a file, Ctrl+Shift+P (or a leading '>') runs a command."""
from PyQt6.QtCore import QEvent, QRect, QSize, Qt
from PyQt6.QtGui import QColor, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (QAbstractItemView, QFrame, QGraphicsDropShadowEffect, QLabel,
                             QLineEdit, QListView, QStyle, QStyledItemDelegate, QVBoxLayout)

from . import icons, theme

R_ITEM = Qt.ItemDataRole.UserRole + 1


def fuzzy(query, text):
    """Subsequence score: higher for consecutive runs and word starts; None if
    ``query`` is not a subsequence of ``text``."""
    if not query:
        return 0
    q, t = query.lower(), text.lower()
    if q in t:
        i = t.index(q)
        return 1000 - i * 2 - len(t) * 0.1 + (40 if i == 0 or not t[i - 1].isalnum() else 0)
    score, ti, run = 0, 0, 0
    for ch in q:
        j = t.find(ch, ti)
        if j < 0:
            return None
        run = run + 1 if j == ti else 0
        score += 10 + run * 6 + (8 if j == 0 or not t[j - 1].isalnum() else 0) - (j - ti) * 0.5
        ti = j + 1
    return score - len(t) * 0.1


class PaletteDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._title = theme.ui_font(9.6)
        self._detail = theme.ui_font(8.4)
        self._key = theme.mono_font(8.2)

    def sizeHint(self, opt, index):
        return QSize(100, 36)

    def paint(self, p, opt, index):
        t = theme.current()
        it = index.data(R_ITEM)
        r = opt.rect.adjusted(6, 1, -6, -1)
        p.save()
        p.setRenderHint(p.RenderHint.Antialiasing)
        if opt.state & QStyle.StateFlag.State_Selected:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(theme.color(t.accent, 46 if t.dark else 32))
            p.drawRoundedRect(r, 6, 6)
        tint = it.get("tint") or t.text_dim
        p.drawPixmap(r.left() + 10, r.top() + (r.height() - 16) // 2, icons.pixmap(it["icon"], tint, 16))
        x = r.left() + 36
        right = r.right() - 10
        key = it.get("shortcut", "")
        if key:
            p.setFont(self._key)
            kfm = p.fontMetrics()
            kw = kfm.horizontalAdvance(key) + 12
            kb = QRect(right - kw, r.top() + 8, kw, r.height() - 16)
            p.setPen(QColor(t.border_strong))
            p.setBrush(QColor(t.bg_input))
            p.drawRoundedRect(kb, 4, 4)
            p.setPen(QColor(t.text_dim))
            p.drawText(kb, int(Qt.AlignmentFlag.AlignCenter), key)
            right = kb.left() - 10
        p.setFont(self._title)
        fm = p.fontMetrics()
        title = it["title"]
        tw = min(fm.horizontalAdvance(title) + 2, right - x)
        p.setPen(QColor(t.text))
        p.drawText(QRect(x, r.top(), tw, r.height()), int(Qt.AlignmentFlag.AlignVCenter),
                   fm.elidedText(title, Qt.TextElideMode.ElideRight, tw))
        detail = it.get("detail", "")
        if detail and right - x - tw > 40:
            p.setFont(self._detail)
            dfm = p.fontMetrics()
            db = QRect(x + tw + 10, r.top(), right - x - tw - 10, r.height())
            p.setPen(QColor(t.text_faint))
            p.drawText(db, int(Qt.AlignmentFlag.AlignVCenter),
                       dfm.elidedText(detail, Qt.TextElideMode.ElideLeft, db.width()))
        p.restore()


class CommandPalette(QFrame):
    """An overlay child of the main window (not a separate top-level window), so
    it moves, themes and stacks with the window."""

    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.setObjectName("Popup")
        self.setFixedWidth(600)
        self.files, self.commands = [], []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.setSpacing(4)
        self.edit = QLineEdit()
        self.edit.setFont(theme.ui_font(11))
        self.edit.installEventFilter(self)
        self.edit.textChanged.connect(self._update)
        self.edit.returnPressed.connect(self._run)
        lay.addWidget(self.edit)
        self.empty = QLabel("Nothing matches")
        self.empty.setObjectName("Faint")
        self.empty.setContentsMargins(18, 8, 0, 8)
        lay.addWidget(self.empty)
        self.model = QStandardItemModel()
        self.list = QListView()
        self.list.setModel(self.model)
        self.list.setItemDelegate(PaletteDelegate(self.list))
        self.list.setUniformItemSizes(True)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.list.clicked.connect(lambda _i: self._run())
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        lay.addWidget(self.list)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 140))
        self.setGraphicsEffect(shadow)
        self.hide()
        host.installEventFilter(self)

    def open(self, files, commands, text=""):
        self.files, self.commands = files, commands
        t = theme.current()
        self.graphicsEffect().setColor(QColor(0, 0, 0, 140 if t.dark else 60))
        self.edit.setText(text)
        self._update()
        self._place()
        self.show()
        self.raise_()
        self.edit.setFocus()
        self.edit.setCursorPosition(len(text))

    def _place(self):
        w = self.host.width()
        self.move((w - self.width()) // 2, 56)

    def _update(self):
        text = self.edit.text()
        if text.startswith(">"):
            q, pool = text[1:].strip(), self.commands
            self.edit.setPlaceholderText("")
        else:
            q, pool = text.strip(), self.files
        self.edit.setPlaceholderText("Type a command" if text.startswith(">")
                                     else "Go to file  ·  type > for commands")
        scored = []
        for it in pool:
            s = fuzzy(q, it["title"])
            if s is None and it.get("detail"):
                s2 = fuzzy(q, it["detail"] + " " + it["title"])
                s = s2 - 200 if s2 is not None else None
            if s is not None:
                scored.append((s, it["title"].lower(), it))
        if q:
            scored.sort(key=lambda x: (-x[0], x[1]))
        self.model.clear()
        for _, _, it in scored[:80]:
            row = QStandardItem()
            row.setData(it, R_ITEM)
            self.model.appendRow(row)
        n = self.model.rowCount()
        self.empty.setVisible(n == 0)
        self.list.setVisible(n > 0)
        self.list.setFixedHeight(min(n, 11) * 36 + 4)
        if n:
            self.list.setCurrentIndex(self.model.index(0, 0))
        self.adjustSize()

    def _run(self):
        idx = self.list.currentIndex()
        if not idx.isValid():
            return
        it = idx.data(R_ITEM)
        self.close_palette()
        it["run"]()

    def close_palette(self):
        self.hide()

    def eventFilter(self, obj, ev):
        if obj is self.edit and ev.type() == QEvent.Type.KeyPress:
            k = ev.key()
            if k == Qt.Key.Key_Escape:
                self.close_palette()
                return True
            if k in (Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_PageDown, Qt.Key.Key_PageUp):
                n = self.model.rowCount()
                if n:
                    step = {Qt.Key.Key_Down: 1, Qt.Key.Key_Up: -1, Qt.Key.Key_PageDown: 10, Qt.Key.Key_PageUp: -10}[k]
                    cur = self.list.currentIndex().row()
                    nxt = max(0, min(n - 1, cur + step))
                    self.list.setCurrentIndex(self.model.index(nxt, 0))
                return True
        if obj is self.edit and ev.type() == QEvent.Type.FocusOut and self.isVisible():
            self.close_palette()
        if obj is self.host and ev.type() == QEvent.Type.Resize and self.isVisible():
            self._place()
        return False
