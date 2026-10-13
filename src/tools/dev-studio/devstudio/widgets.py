"""Small shared widgets: search field, chips, toasts, banners, segmented control."""
from PyQt6.QtCore import (QEasingCurve, QPoint, QPropertyAnimation, QSize, Qt, QTimer,
                          pyqtSignal)
from PyQt6.QtGui import QAction, QColor, QFont, QPainter
from PyQt6.QtWidgets import (QButtonGroup, QFrame, QGraphicsDropShadowEffect,
                             QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLineEdit,
                             QPlainTextEdit, QPushButton, QSizePolicy, QToolButton,
                             QVBoxLayout, QWidget)

from . import icons, theme


def tool_button(icon_name, tip, slot=None, checkable=False, size=16, shortcut_text=""):
    b = QToolButton()
    b.setIcon(icons.icon(icon_name, size=size))
    b.setIconSize(QSize(size, size))
    b.setToolTip(tip + ("  <span style='opacity:.6'>%s</span>" % shortcut_text if shortcut_text else ""))
    b.setCheckable(checkable)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setAutoRaise(True)
    b._icon_name = icon_name
    if slot:
        (b.toggled if checkable else b.clicked).connect(slot)
    return b


def text_button(icon_name, text, slot=None):
    b = QToolButton()
    b.setObjectName("TextButton")
    b.setText(text)
    if icon_name:
        b.setIcon(icons.icon(icon_name))
        b.setIconSize(QSize(15, 15))
        b._icon_name = icon_name
    b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if slot:
        b.clicked.connect(slot)
    return b


def retint(root):
    """Re-render every themed icon under ``root`` after a theme switch."""
    for b in root.findChildren(QToolButton):
        name = getattr(b, "_icon_name", None)
        if name:
            b.setIcon(icons.icon(name, size=b.iconSize().width()))
    for a in root.findChildren(QAction):
        name = getattr(a, "_icon_name", None)
        if name:
            a.setIcon(icons.icon(name))


def caps_label(text):
    lab = QLabel(text.upper())
    lab.setFont(theme.caps_font())
    lab.setObjectName("Faint")
    return lab


def chip(text="", modified=False):
    lab = QLabel(text)
    lab.setObjectName("ChipModified" if modified else "Chip")
    f = theme.ui_font(8.2)
    lab.setFont(f)
    return lab


class ElidedLabel(QLabel):
    """A one-line label that shortens itself with an ellipsis instead of
    widening its parent (TileLookup column names run to 80 characters)."""

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(20)
        self.setText(text)

    def setText(self, text):
        self._full = text
        self.setToolTip(text if len(text) > 30 else self.toolTip())
        self._elide()

    def full_text(self):
        return self._full

    def _elide(self):
        w = max(10, self.width())
        super().setText(self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideRight, w))

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._elide()


class SearchField(QLineEdit):
    """A line edit with a search glyph, a clear button and Escape-to-clear."""
    escaped = pyqtSignal()

    def __init__(self, placeholder, parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self._lead = self.addAction(icons.icon("search"), QLineEdit.ActionPosition.LeadingPosition)
        self._lead._icon_name = "search"
        self.setMinimumHeight(30)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Escape:
            if self.text():
                self.clear()
            else:
                self.escaped.emit()
            return
        super().keyPressEvent(ev)

    def retint(self):
        self._lead.setIcon(icons.icon("search"))


class CommitLineEdit(QLineEdit):
    """Emits ``committed(text)`` on Enter or focus-out, only if the text changed;
    Escape puts the stored value back."""
    committed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = ""
        self.editingFinished.connect(self._finish)

    def set_value(self, v, modified=False):
        self._value = v
        self.blockSignals(True)
        self.setText(v)
        self.setCursorPosition(0)
        self.blockSignals(False)
        if self.property("modified") != modified:
            self.setProperty("modified", modified)
            self.style().unpolish(self)
            self.style().polish(self)

    def _finish(self):
        if self.text() != self._value:
            self.committed.emit(self.text())

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Escape:
            self.setText(self._value)
            self.clearFocus()
            return
        super().keyPressEvent(ev)


class CommitTextEdit(QPlainTextEdit):
    """Multi-line twin of CommitLineEdit: commits on focus-out or Ctrl+Enter."""
    committed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = ""
        self.setTabChangesFocus(True)

    def set_value(self, v, modified=False):
        self._value = v
        self.blockSignals(True)
        self.setPlainText(v)
        self.blockSignals(False)
        if self.property("modified") != modified:
            self.setProperty("modified", modified)
            self.style().unpolish(self)
            self.style().polish(self)

    def _finish(self):
        if self.toPlainText() != self._value:
            self.committed.emit(self.toPlainText())

    def focusOutEvent(self, ev):
        self._finish()
        super().focusOutEvent(ev)

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._finish()
            return
        if ev.key() == Qt.Key.Key_Escape:
            self.setPlainText(self._value)
            self.clearFocus()
            return
        super().keyPressEvent(ev)


class Segmented(QFrame):
    """A row of mutually exclusive pill buttons (language slots ...)."""
    changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Segmented")
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(2, 2, 2, 2)
        self._lay.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.idClicked.connect(self.changed.emit)

    def set_items(self, labels, tips=None, current=0):
        for b in self._group.buttons():
            self._group.removeButton(b)
        clear_layout(self._lay)
        for i, lab in enumerate(labels):
            b = QToolButton()
            b.setText(lab)
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            if tips:
                b.setToolTip(tips[i])
            self._group.addButton(b, i)
            self._lay.addWidget(b)
        if labels:
            self._group.button(current).setChecked(True)

    def set_current(self, i):
        b = self._group.button(i)
        if b and not b.isChecked():
            b.setChecked(True)


class Banner(QFrame):
    """A strip across the top of an editor: a message and a few actions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Banner")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 8, 6)
        lay.setSpacing(8)
        self._icon = QLabel()
        self._text = QLabel()
        self._text.setWordWrap(True)
        lay.addWidget(self._icon)
        lay.addWidget(self._text, 1)
        self._buttons = QHBoxLayout()
        self._buttons.setSpacing(6)
        lay.addLayout(self._buttons)
        self.hide()

    def show_message(self, text, actions, icon="alert"):
        t = theme.current()
        self._icon.setPixmap(icons.pixmap(icon, t.modified, 16))
        self._text.setText(text)
        clear_layout(self._buttons)
        for label, slot, primary in actions:
            b = QPushButton(label)
            if primary:
                b.setObjectName("Primary")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            self._buttons.addWidget(b)
        self.show()


class Toast(QFrame):
    """A transient notice in the bottom-right corner of the window."""

    def __init__(self, host, text, kind="info", detail=""):
        super().__init__(host)
        self.setObjectName("Toast")
        t = theme.current()
        col = {"success": t.success, "error": t.danger, "warning": t.modified}.get(kind, t.accent)
        ic = {"success": "check", "error": "alert", "warning": "alert"}.get(kind, "info")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 14, 10)
        lay.setSpacing(10)
        i = QLabel()
        i.setPixmap(icons.pixmap(ic, col, 18, stroke=2))
        i.setAlignment(Qt.AlignmentFlag.AlignTop)
        lay.addWidget(i)
        col_lay = QVBoxLayout()
        col_lay.setSpacing(2)
        main = QLabel(text)
        main.setFont(theme.ui_font(9.5, QFont.Weight.DemiBold))
        col_lay.addWidget(main)
        if detail:
            d = QLabel(detail)
            d.setObjectName("Dim")
            d.setWordWrap(True)
            d.setMaximumWidth(380)
            col_lay.addWidget(d)
        lay.addLayout(col_lay)
        self.setMaximumWidth(460)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 110 if t.dark else 45))
        self.setGraphicsEffect(shadow)
        self.adjustSize()
        self._timer = QTimer(self, singleShot=True, interval=4200 if kind != "error" else 7000)
        self._timer.timeout.connect(self._fade)
        self._timer.start()

    def _fade(self):
        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(260)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(self.deleteLater)
        anim.start()

    def mousePressEvent(self, ev):
        self._fade()


class ToastHost:
    """Stacks toasts above the status bar of ``window``."""

    def __init__(self, window):
        self.window = window
        self.items = []

    def show(self, text, kind="info", detail=""):
        t = Toast(self.window, text, kind, detail)
        t.destroyed.connect(lambda *_: self._forget(t))
        self.items.append(t)
        t.show()
        t.raise_()
        self.layout()

    def _forget(self, t):
        if t in self.items:
            self.items.remove(t)
        self.layout()

    def layout(self):
        w = self.window
        try:
            y = w.height() - 40
        except RuntimeError:          # window already torn down
            return
        for t in reversed(self.items):
            try:
                t.adjustSize()
                y -= t.height()
                t.move(w.width() - t.width() - 18, y)
                y -= 10
            except RuntimeError:
                pass


class TabCloseButton(QToolButton):
    """Close button that shows a dot while the document has unsaved changes and
    turns into a cross under the pointer (the convention editors settled on)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dirty = False
        self.setFixedSize(20, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRaise(True)
        self._hover = False

    def set_dirty(self, d):
        self.dirty = d
        self.update()

    def enterEvent(self, ev):
        self._hover = True
        self.update()

    def leaveEvent(self, ev):
        self._hover = False
        self.update()

    def paintEvent(self, ev):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._hover:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(t.bg_hover))
            p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 4, 4)
            p.drawPixmap(QPoint(3, 3), icons.pixmap("x", t.text, 14, stroke=2))
        elif self.dirty:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(t.text_dim))
            p.drawEllipse(self.rect().center(), 4, 4)
        else:
            p.drawPixmap(QPoint(3, 3), icons.pixmap("x", t.text_faint, 14, stroke=2))
        p.end()


def clear_layout(layout):
    """Empty a layout *now*: deleteLater alone leaves the widgets drawn (and
    parented) until the event loop runs, which shows as stale text."""
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def hspacer():
    w = QWidget()
    w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return w


def vline():
    f = QFrame()
    f.setFixedWidth(1)
    f.setFixedHeight(18)
    f.setObjectName("Divider")
    return f
