"""The sidebar: every STB and STL under the data folder, filterable."""
import os

from PyQt6.QtCore import QModelIndex, QRect, QSize, QSortFilterProxyModel, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QLabel, QStyle,
                             QStyledItemDelegate, QTreeView, QVBoxLayout)

from . import icons, theme, widgets, workspace as ws

R_PATH = Qt.ItemDataRole.UserRole + 1
R_META = Qt.ItemDataRole.UserRole + 2
R_HINT = Qt.ItemDataRole.UserRole + 3
R_KIND = Qt.ItemDataRole.UserRole + 4

GROUPS = (("stb", "Tables"), ("stl", "String tables"))
HOME = os.path.join("3DDATA", "STB").lower()


class ExplorerDelegate(QStyledItemDelegate):
    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.open_paths = set()
        self.dirty_paths = set()
        self._name = theme.ui_font(9.2)
        self._bold = theme.ui_font(9.2, QFont.Weight.DemiBold)
        self._meta = theme.ui_font(8.0)
        self._caps = theme.caps_font(7.6)

    def sizeHint(self, opt, index):
        return QSize(100, 30 if index.data(R_KIND) == "group" else 27)

    def paint(self, p, opt, index):
        t = theme.current()
        r = opt.rect
        kind = index.data(R_KIND)
        p.save()
        p.setRenderHint(p.RenderHint.Antialiasing)
        hover = opt.state & QStyle.StateFlag.State_MouseOver
        if kind == "group":
            exp = self.view.isExpanded(index)
            p.drawPixmap(r.left() + 10, r.top() + (r.height() - 12) // 2,
                         icons.pixmap("chevron-down" if exp else "chevron-right", t.text_faint, 12, stroke=2.2))
            p.setFont(self._caps)
            p.setPen(QColor(t.text if hover else t.text_dim))
            p.drawText(r.adjusted(28, 0, -12, 0), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                       index.data().upper())
            p.setFont(self._meta)
            p.setPen(QColor(t.text_faint))
            p.drawText(r.adjusted(0, 0, -14, 0), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
                       str(index.data(R_META)))
            p.restore()
            return
        box = r.adjusted(6, 1, -6, -1)
        path = index.data(R_PATH)
        if opt.state & QStyle.StateFlag.State_Selected:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(theme.color(t.accent, 46 if t.dark else 32))
            p.drawRoundedRect(box, 5, 5)
        elif hover:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(t.bg_hover))
            p.drawRoundedRect(box, 5, 5)
        tint = t.match if kind == "stb" else t.success
        p.drawPixmap(box.left() + 14, box.top() + (box.height() - 14) // 2,
                     icons.pixmap("table" if kind == "stb" else "text", tint, 14))
        meta = index.data(R_META) or ""
        p.setFont(self._meta)
        mfm = p.fontMetrics()
        mw = mfm.horizontalAdvance(meta)
        right = box.right() - 8
        if path in self.dirty_paths:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(t.modified))
            p.drawEllipse(right - 6, box.center().y() - 3, 7, 7)
            right -= 14
        p.setPen(QColor(t.text_faint))
        p.drawText(QRect(right - mw, box.top(), mw, box.height()),
                   int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight), meta)
        nf = self._bold if path in self.open_paths else self._name
        p.setFont(nf)
        fm = p.fontMetrics()
        name_box = QRect(box.left() + 36, box.top(), right - mw - box.left() - 46, box.height())
        name = index.data()
        hint = index.data(R_HINT) or ""
        name_w = fm.horizontalAdvance(name)
        p.setPen(QColor(t.text))
        p.drawText(name_box, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                   fm.elidedText(name, Qt.TextElideMode.ElideMiddle, name_box.width()))
        if hint and name_w + 30 < name_box.width():
            hb = name_box.adjusted(name_w + 8, 0, 0, 0)
            p.setFont(self._meta)
            p.setPen(QColor(t.text_faint))
            p.drawText(hb, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                       mfm.elidedText(hint, Qt.TextElideMode.ElideLeft, hb.width()))
        p.restore()


class ExplorerProxy(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.setRecursiveFilteringEnabled(True)
        self.query = ""

    def set_query(self, q):
        self.query = q.lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, row, parent):
        idx = self.sourceModel().index(row, 0, parent)
        if idx.data(R_KIND) == "group":
            return False      # recursive filtering keeps a group whose children match
        q = self.query
        if not q:
            return True
        hay = ((idx.data() or "") + " " + (idx.data(R_HINT) or "")).lower()
        return all(part in hay for part in q.split())


class Explorer(QFrame):
    openRequested = pyqtSignal(str)
    chooseRootRequested = pyqtSignal()
    refreshRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setMinimumWidth(220)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        head = QHBoxLayout()
        head.setContentsMargins(16, 10, 8, 4)
        head.addWidget(widgets.caps_label("Explorer"))
        head.addStretch(1)
        head.addWidget(widgets.tool_button("refresh", "Rescan the data folder", self.refreshRequested.emit, size=15))
        head.addWidget(widgets.tool_button("folder", "Open another data folder…", self.chooseRootRequested.emit, size=15))
        lay.addLayout(head)

        self.root_label = QLabel("No data folder")
        self.root_label.setObjectName("Dim")
        self.root_label.setContentsMargins(16, 0, 12, 8)
        lay.addWidget(self.root_label)

        self.filter = widgets.SearchField("Filter files")
        sl = QHBoxLayout()
        sl.setContentsMargins(10, 0, 10, 8)
        sl.addWidget(self.filter)
        lay.addLayout(sl)

        self.model = QStandardItemModel()
        self.proxy = ExplorerProxy()
        self.proxy.setSourceModel(self.model)
        self.tree = QTreeView()
        self.tree.setModel(self.proxy)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(0)
        self.tree.setUniformRowHeights(False)
        self.tree.setMouseTracking(True)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.delegate = ExplorerDelegate(self.tree)
        self.tree.setItemDelegate(self.delegate)
        self.tree.clicked.connect(self._clicked)
        self.tree.activated.connect(self._activated)
        lay.addWidget(self.tree, 1)
        self.filter.textChanged.connect(self._filter)
        self.filter.returnPressed.connect(self._open_first)

    def set_workspace(self, wsp):
        self.model.clear()
        if wsp is None:
            self.root_label.setText("No data folder")
            return
        self.root_label.setText(os.path.basename(wsp.root) or wsp.root)
        self.root_label.setToolTip(wsp.root)
        for kind, title in GROUPS:
            files = [f for f in wsp.files if f[0] == kind]
            g = QStandardItem(title)
            g.setData("group", R_KIND)
            g.setData(len(files), R_META)
            g.setFlags(Qt.ItemFlag.ItemIsEnabled)
            for _, path, rel in files:
                it = QStandardItem(os.path.basename(path))
                folder = os.path.dirname(rel)
                it.setData(os.path.normpath(path), R_PATH)
                it.setData(kind, R_KIND)
                it.setData(ws.peek(path), R_META)
                it.setData("" if folder.lower() == HOME else folder.replace("\\", "/"), R_HINT)
                it.setToolTip(rel)
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                g.appendRow(it)
            self.model.appendRow(g)
        self.tree.expandAll()

    def mark(self, open_paths, dirty_paths):
        self.delegate.open_paths = set(open_paths)
        self.delegate.dirty_paths = set(dirty_paths)
        self.tree.viewport().update()

    def select_path(self, path):
        path = os.path.normpath(path)
        for g in range(self.proxy.rowCount()):
            gi = self.proxy.index(g, 0)
            for r in range(self.proxy.rowCount(gi)):
                idx = self.proxy.index(r, 0, gi)
                if idx.data(R_PATH) == path:
                    self.tree.setCurrentIndex(idx)
                    self.tree.scrollTo(idx)
                    return

    def _filter(self, text):
        self.proxy.set_query(text.strip())
        self.tree.expandAll()

    def _clicked(self, idx):
        if idx.data(R_KIND) == "group":
            self.tree.setExpanded(idx, not self.tree.isExpanded(idx))
        elif idx.data(R_PATH):
            self.openRequested.emit(idx.data(R_PATH))

    def _activated(self, idx):
        if idx.data(R_PATH):
            self.openRequested.emit(idx.data(R_PATH))

    def _open_first(self):
        for g in range(self.proxy.rowCount()):
            gi = self.proxy.index(g, 0)
            if self.proxy.rowCount(gi):
                self._activated(self.proxy.index(0, 0, gi))
                return

    def focus_filter(self):
        self.filter.setFocus()
        self.filter.selectAll()
