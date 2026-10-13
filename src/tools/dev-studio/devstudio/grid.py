"""The data grid shared by the STB and STL editors.

Cells, column headers and row headers are painted by hand rather than styled:
a stylesheet cannot show a column's game index above its name, tint a cell that
differs from disk, or mark search hits, and those three things are most of what
makes a 4,000 x 87 table readable.
"""
from PyQt6.QtCore import QModelIndex, QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QKeySequence, QPainter, QPen, QPolygon
from PyQt6.QtWidgets import (QAbstractItemDelegate, QAbstractItemView, QHeaderView,
                             QLineEdit, QStyle, QStyledItemDelegate, QTableView)

from . import icons, theme

ROLE_MODIFIED = Qt.ItemDataRole.UserRole + 1
ROLE_NUMERIC = Qt.ItemDataRole.UserRole + 2
ROLE_NAME = Qt.ItemDataRole.UserRole + 3
ROLE_SORT = Qt.ItemDataRole.UserRole + 4
ROLE_MULTILINE = Qt.ItemDataRole.UserRole + 5

ROW_HEIGHT = 26


class CellDelegate(QStyledItemDelegate):
    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.query = ""

    def paint(self, p, opt, index):
        t = theme.current()
        r = opt.rect
        p.save()
        if opt.features & opt.ViewItemFeature.Alternate:
            p.fillRect(r, QColor(t.bg_alt))
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        modified = index.data(ROLE_MODIFIED)
        if modified:
            p.fillRect(r, theme.color(t.modified, 30 if t.dark else 40))
        if self.query and text and self.query in text.lower():
            p.fillRect(r, theme.color(t.match, 46 if t.dark else 40))
        if opt.state & QStyle.StateFlag.State_Selected:
            p.fillRect(r, theme.color(t.accent, 48 if t.dark else 34))
        if modified:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(t.modified))
            p.drawPolygon(QPolygon([r.topLeft(), r.topLeft() + QPoint(6, 0), r.topLeft() + QPoint(0, 6)]))
        if text:
            if "\n" in text or "\r" in text:
                text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "  ↵  ")
            numeric = index.data(ROLE_NUMERIC)
            p.setFont(opt.font)
            p.setPen(QColor(t.text))
            fm = opt.fontMetrics
            body = r.adjusted(8, 0, -8, 0)
            shown = fm.elidedText(text, Qt.TextElideMode.ElideRight, body.width())
            align = (Qt.AlignmentFlag.AlignRight if numeric else Qt.AlignmentFlag.AlignLeft) | Qt.AlignmentFlag.AlignVCenter
            p.drawText(body, int(align), shown)
        if index == self.view.currentIndex() and self.view.hasFocus():
            pen = QPen(QColor(t.accent))
            pen.setWidthF(1.6)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r.adjusted(0, 0, -1, -1))
        p.restore()

    def createEditor(self, parent, opt, index):
        e = QLineEdit(parent)
        e.setFrame(False)
        e.setFont(opt.font)
        return e

    def setEditorData(self, editor, index):
        editor.setText(index.data(Qt.ItemDataRole.EditRole) or "")
        editor.selectAll()

    def sizeHint(self, opt, index):
        return QSize(80, ROW_HEIGHT)


class ColumnHeader(QHeaderView):
    """Two lines per column: the game index (small) over the column's name."""
    HEIGHT = 44

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setSectionsClickable(True)
        self.setHighlightSections(True)
        self.setMinimumSectionSize(34)
        self.setDefaultSectionSize(110)
        self.setFixedHeight(self.HEIGHT)
        self.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.setStretchLastSection(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._small = theme.ui_font(7.6)
        self._name = theme.ui_font(8.8, QFont.Weight.DemiBold)

    def paintSection(self, p, rect, logical):
        if not rect.isValid():
            return
        t = theme.current()
        m = self.model()
        view = self.parent()
        cur = view.currentIndex().column() == logical if view else False
        p.save()
        p.fillRect(rect, QColor(t.bg_hover if cur else t.bg_raised))
        p.setPen(QColor(t.border))
        p.drawLine(rect.topRight(), rect.bottomRight())
        p.drawLine(rect.bottomLeft(), rect.bottomRight())
        if cur:
            p.fillRect(QRect(rect.left(), rect.bottom() - 1, rect.width(), 2), QColor(t.accent))
        idx = str(m.headerData(logical, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) or "")
        name = m.headerData(logical, Qt.Orientation.Horizontal, ROLE_NAME) or ""
        body = rect.adjusted(9, 6, -9, -6)
        right = 0
        if self.isSortIndicatorShown() and self.sortIndicatorSection() == logical:
            down = self.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
            pm = icons.pixmap("chevron-down" if down else "chevron-up", t.accent, 12, stroke=2.4)
            p.drawPixmap(rect.right() - 20, rect.top() + 6, pm)
            right = 14
        p.setFont(self._small)
        p.setPen(QColor(t.accent if cur else t.text_faint))
        p.drawText(body.adjusted(0, 0, -right, 0), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), idx)
        p.setFont(self._name)
        p.setPen(QColor(t.text if cur else t.text_dim))
        fm = p.fontMetrics()
        p.drawText(body, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom),
                   fm.elidedText(name or "—", Qt.TextElideMode.ElideRight, body.width()))
        p.restore()

    def sizeHint(self):
        s = super().sizeHint()
        return QSize(s.width(), self.HEIGHT)


class RowHeader(QHeaderView):
    """Row number in a fixed gutter, then the row's display name."""
    GUTTER = 56

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Vertical, parent)
        self.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.setDefaultSectionSize(ROW_HEIGHT)
        self.setMinimumSectionSize(ROW_HEIGHT)
        self.setSectionsClickable(True)
        self.setHighlightSections(True)
        self.label_width = 200
        self._num = theme.mono_font(8.4)
        self._label = theme.ui_font(9.0)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def set_label_width(self, w):
        self.label_width = w
        self.updateGeometry()
        self.viewport().update()

    def sizeHint(self):
        return QSize(self.GUTTER + (self.label_width + 14 if self.label_width else 8), ROW_HEIGHT)

    def paintSection(self, p, rect, logical):
        if not rect.isValid():
            return
        t = theme.current()
        m = self.model()
        view = self.parent()
        cur = view.currentIndex().row() == logical if view else False
        sel = view.selectionModel().isRowSelected(logical, QModelIndex()) if view and view.selectionModel() else False
        p.save()
        p.fillRect(rect, QColor(t.bg_raised))
        if sel:
            p.fillRect(rect, theme.color(t.accent, 48 if t.dark else 34))
        elif cur:
            p.fillRect(rect, QColor(t.bg_hover))
        p.setPen(QColor(t.border))
        p.drawLine(rect.topRight(), rect.bottomRight())
        p.setPen(QColor(t.grid))
        p.drawLine(rect.bottomLeft(), rect.bottomRight())
        if m.headerData(logical, Qt.Orientation.Vertical, ROLE_MODIFIED):
            p.fillRect(QRect(rect.left(), rect.top() + 3, 3, rect.height() - 6), QColor(t.modified))
        num = str(m.headerData(logical, Qt.Orientation.Vertical, Qt.ItemDataRole.DisplayRole) or "")
        p.setFont(self._num)
        p.setPen(QColor(t.accent if cur else t.text_faint))
        p.drawText(QRect(rect.left(), rect.top(), self.GUTTER - 8, rect.height()),
                   int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), num)
        if self.label_width:
            name = m.headerData(logical, Qt.Orientation.Vertical, ROLE_NAME) or ""
            if name:
                box = QRect(rect.left() + self.GUTTER + 4, rect.top(), rect.width() - self.GUTTER - 12, rect.height())
                p.setFont(self._label)
                p.setPen(QColor(t.text if cur or sel else t.text_dim))
                fm = p.fontMetrics()
                p.drawText(box, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                           fm.elidedText(name, Qt.TextElideMode.ElideRight, box.width()))
        p.restore()


class GridView(QTableView):
    """QTableView with spreadsheet keys: Enter edits and moves down, Delete
    clears, Ctrl+C / Ctrl+V copy and paste tab-separated text."""
    clearRequested = pyqtSignal()
    copyRequested = pyqtSignal()
    pasteRequested = pyqtSignal()
    activatedMultiline = pyqtSignal(QModelIndex)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cells = CellDelegate(self)
        self.setItemDelegate(self.cells)
        self.setHorizontalHeader(ColumnHeader(self))
        self.setVerticalHeader(RowHeader(self))
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked |
                             QAbstractItemView.EditTrigger.EditKeyPressed |
                             QAbstractItemView.EditTrigger.AnyKeyPressed)
        self.setWordWrap(False)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setShowGrid(True)
        self.setCornerButtonEnabled(False)
        self.setFont(theme.ui_font(9.2))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.verticalScrollBar().setSingleStep(ROW_HEIGHT)

    def center_on(self, idx):
        """Bring ``idx`` to the vertical middle; horizontally, only scroll as far
        as needed (PositionAtCenter would also centre the column)."""
        if not idx.isValid():
            return
        self.scrollTo(idx, QAbstractItemView.ScrollHint.EnsureVisible)
        y = self.rowViewportPosition(idx.row())
        sb = self.verticalScrollBar()
        sb.setValue(sb.value() + y - (self.viewport().height() - self.rowHeight(idx.row())) // 2)

    def currentChanged(self, cur, prev):
        super().currentChanged(cur, prev)
        self.horizontalHeader().viewport().update()
        self.verticalHeader().viewport().update()

    def selectionChanged(self, sel, desel):
        super().selectionChanged(sel, desel)
        self.verticalHeader().viewport().update()

    def keyPressEvent(self, ev):
        if self.state() != QAbstractItemView.State.EditingState:
            if ev.matches(QKeySequence.StandardKey.Copy):
                self.copyRequested.emit()
                return
            if ev.matches(QKeySequence.StandardKey.Paste):
                self.pasteRequested.emit()
                return
            if ev.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                self.clearRequested.emit()
                return
            if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.currentIndex().isValid():
                idx = self.currentIndex()
                if idx.data(ROLE_MULTILINE):
                    self.activatedMultiline.emit(idx)
                else:
                    self.edit(idx)
                return
        super().keyPressEvent(ev)

    def edit(self, index, trigger=None, event=None):
        if trigger is None:
            return super().edit(index)
        if index.isValid() and index.data(ROLE_MULTILINE) and trigger in (
                QAbstractItemView.EditTrigger.DoubleClicked, QAbstractItemView.EditTrigger.AnyKeyPressed,
                QAbstractItemView.EditTrigger.EditKeyPressed):
            self.activatedMultiline.emit(index)
            return False
        return super().edit(index, trigger, event)

    def closeEditor(self, editor, hint):
        super().closeEditor(editor, hint)
        if hint == QAbstractItemDelegate.EndEditHint.SubmitModelCache:
            cur = self.currentIndex()
            nxt = cur.siblingAtRow(cur.row() + 1)
            if nxt.isValid():
                self.setCurrentIndex(nxt)

    def focusInEvent(self, ev):
        super().focusInEvent(ev)
        self.viewport().update()

    def focusOutEvent(self, ev):
        super().focusOutEvent(ev)
        self.viewport().update()


def fit_columns(view, ncols, sample_rows, text_at, header_name, max_w=340):
    """Size columns from a sample of rows; resizeColumnsToContents on a 7,000-row
    table walks every cell and stalls for seconds."""
    fm = QFontMetrics(view.font())
    hf = QFontMetrics(theme.ui_font(8.8, QFont.Weight.DemiBold))
    hh = view.horizontalHeader()
    for c in range(ncols):
        w = hf.horizontalAdvance(header_name(c) or "—") + 24
        for r in sample_rows:
            s = text_at(r, c)
            if s:
                w = max(w, fm.horizontalAdvance(s[:60]) + 22)
                if w >= max_w:
                    break
        hh.resizeSection(c, max(48, min(max_w, w)))
