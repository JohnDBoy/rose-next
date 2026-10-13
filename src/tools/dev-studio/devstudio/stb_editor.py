"""STB table editor: the grid, a row filter and the row inspector."""
import os
import re

from PyQt6.QtCore import (QAbstractTableModel, QItemSelectionModel, QModelIndex,
                          QSortFilterProxyModel, Qt, QTimer)
from PyQt6.QtGui import QFont, QFontMetrics
from PyQt6.QtWidgets import (QAbstractItemView, QComboBox, QFrame, QHBoxLayout,
                             QLabel, QMenu, QPushButton, QScrollArea, QSplitter, QVBoxLayout,
                             QWidget)

from . import icons, theme, widgets, workspace as ws
from .documents import ENCODING_NAMES, is_number
from .editor_base import EditorBase
from .grid import (ROLE_MODIFIED, ROLE_NAME, ROLE_NUMERIC, ROLE_SORT, GridView, fit_columns)

GOTO_RE = re.compile(r"^#\s*(\d+)$")


class StbModel(QAbstractTableModel):
    def __init__(self, doc, editor):
        super().__init__()
        self.doc, self.editor = doc, editor
        doc.cellsChanged.connect(self._cells)
        doc.rowsAboutToBeAppended.connect(lambda a, b: self.beginInsertRows(QModelIndex(), a, b))
        doc.rowsAppended.connect(self.endInsertRows)
        doc.rowsAboutToBeRemoved.connect(lambda a, b: self.beginRemoveRows(QModelIndex(), a, b))
        doc.rowsRemoved.connect(self.endRemoveRows)
        doc.labelsChanged.connect(self._labels)
        doc.saved.connect(self._all)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else self.doc.rows

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else self.doc.cols

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        r, c = index.row(), index.column()
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return self.doc.text(r, c)
        if role == ROLE_MODIFIED:
            return self.doc.is_modified(r, c)
        if role == ROLE_NUMERIC:
            return is_number(self.doc.text(r, c))
        if role == ROLE_SORT:
            s = self.doc.text(r, c).strip()
            try:
                return (0, float(s), "")
            except ValueError:
                return (1 if s else 2, 0.0, s.lower())
        if role == Qt.ItemDataRole.ToolTipRole:
            s = self.doc.text(r, c)
            return s if len(s) > 32 else None
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole:
            return False
        try:
            self.doc.set_cells([(index.row(), index.column(), value)])
        except ValueError as e:
            self.editor.toast("Edit refused", "error", str(e))
            return False
        return True

    def flags(self, index):
        return (Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                return str(section)
            if role == ROLE_NAME:
                return self.doc.colname(section)
            if role == Qt.ItemDataRole.ToolTipRole:
                name = self.doc.colname(section) or "(unnamed)"
                return "<b>%s</b><br>Game column %d · editor column %d" % (name, section, section + 1)
        else:
            if section >= self.doc.rows:
                return None
            if role == Qt.ItemDataRole.DisplayRole:
                return str(section)
            if role == ROLE_NAME:
                return self.doc.row_label(section)
            if role == ROLE_MODIFIED:
                return self.doc.row_modified(section)
        return None

    def _cells(self, r0, c0, r1, c1):
        self.dataChanged.emit(self.index(r0, c0), self.index(r1, c1))
        self.headerDataChanged.emit(Qt.Orientation.Vertical, r0, r1)

    def _labels(self):
        if self.doc.rows:
            self.headerDataChanged.emit(Qt.Orientation.Vertical, 0, self.doc.rows - 1)

    def _all(self):
        if self.doc.rows and self.doc.cols:
            self.dataChanged.emit(self.index(0, 0), self.index(self.doc.rows - 1, self.doc.cols - 1))
            self.headerDataChanged.emit(Qt.Orientation.Vertical, 0, self.doc.rows - 1)


class StbProxy(QSortFilterProxyModel):
    def __init__(self, doc):
        super().__init__()
        self.doc = doc
        self.query, self.column, self.hide_empty = "", -1, False
        self.setSortRole(ROLE_SORT)
        self.setDynamicSortFilter(False)

    def set_filter(self, query, column, hide_empty):
        self.query, self.column, self.hide_empty = query.lower(), column, hide_empty
        self.invalidateFilter()

    def filterAcceptsRow(self, r, parent):
        d = self.doc
        if self.hide_empty and not d.occupied(r):
            return False
        q = self.query
        if not q:
            return True
        if self.column < 0:
            return q in d.row_text(r) or q in d.row_label(r).lower()
        return q in d.text(r, self.column).lower()

    def lessThan(self, a, b):
        return a.data(ROLE_SORT) < b.data(ROLE_SORT)


class StbInspector(QFrame):
    """The current row as a form: every column, labelled, one field each."""

    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.doc = editor.doc
        self.setObjectName("Inspector")
        self.setMinimumWidth(280)
        self.row = -1

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        head = QWidget()
        hl = QVBoxLayout(head)
        hl.setContentsMargins(16, 14, 16, 10)
        hl.setSpacing(4)
        hl.addWidget(widgets.caps_label("Row"))
        self.title = QLabel("No row selected")
        self.title.setFont(theme.ui_font(13, QFont.Weight.DemiBold))
        self.title.setWordWrap(True)
        hl.addWidget(self.title)
        meta = QHBoxLayout()
        meta.setSpacing(6)
        self.sub = QLabel("")
        self.sub.setObjectName("Dim")
        meta.addWidget(self.sub)
        self.chip = widgets.chip("modified", modified=True)
        self.chip.hide()
        meta.addWidget(self.chip)
        meta.addStretch(1)
        hl.addLayout(meta)
        self.link = QPushButton()
        self.link.setObjectName("Link")
        self.link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.link.setIcon(icons.icon("external", theme.current().accent))
        self.link.clicked.connect(self._open_strings)
        self.link.hide()
        hl.addWidget(self.link)
        self.filter = widgets.SearchField("Filter fields")
        self.filter.textChanged.connect(self._filter)
        hl.addSpacing(6)
        hl.addWidget(self.filter)
        lay.addWidget(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        # never wider than the panel: long names elide instead of scrolling sideways
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("InspectorBody")
        self.grid = QVBoxLayout(body)
        self.grid.setContentsMargins(16, 4, 14, 16)
        self.grid.setSpacing(8)
        self.scroll.setWidget(body)
        lay.addWidget(self.scroll, 1)

        foot = QWidget()
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(12, 8, 12, 10)
        fl.setSpacing(4)
        fl.addWidget(widgets.text_button("copy", "Copy row", editor.copy_rows))
        fl.addWidget(widgets.text_button("clipboard", "Paste row", editor.paste_row))
        fl.addStretch(1)
        clear = widgets.text_button("eraser", "Clear", editor.clear_rows)
        clear.setToolTip("Blank every cell of the selected rows (rows are ids: they are never deleted)")
        fl.addWidget(clear)
        lay.addWidget(foot)

        self.fields = []
        mono = theme.mono_font(8.2)
        for c in range(self.doc.cols):
            name = self.doc.colname(c) or "Column %d" % c
            lab = widgets.ElidedLabel(name)
            lab.setObjectName("Dim")
            lab.setToolTip("%s\nGame column %d · editor column %d" % (name, c, c + 1))
            num = QLabel(str(c))
            num.setFont(mono)
            num.setObjectName("Faint")
            num.setToolTip("Game column %d (editor column %d)" % (c, c + 1))
            edit = widgets.CommitLineEdit()
            edit.committed.connect(lambda text, c=c: self._commit(c, text))
            top = QHBoxLayout()
            top.setContentsMargins(2, 0, 2, 0)
            top.addWidget(lab, 1)
            top.addWidget(num)
            box = QVBoxLayout()
            box.setSpacing(3)
            box.setContentsMargins(0, 0, 0, 0)
            box.addLayout(top)
            box.addWidget(edit)
            holder = QWidget()
            holder.setLayout(box)
            self.grid.addWidget(holder)
            self.fields.append((lab, holder, edit, name.lower()))
        self.grid.addStretch(1)
        self.set_row(-1)

    def set_row(self, r):
        self.row = r
        valid = 0 <= r < self.doc.rows
        for _, _, edit, _ in self.fields:
            edit.setEnabled(valid)
        if not valid:
            self.title.setText("No row selected")
            self.sub.setText("Select a cell to edit its row here.")
            self.chip.hide()
            self.link.hide()
            for _, _, edit, _ in self.fields:
                edit.set_value("")
            return
        self.refresh()

    def refresh(self):
        r = self.row
        if not (0 <= r < self.doc.rows):
            return
        d = self.doc
        label = d.row_title(r)
        self.title.setText(label or "Row %d" % r)
        self.sub.setText("Row %d" % r + ("" if d.occupied(r) else " · empty"))
        self.chip.setVisible(d.row_modified(r))
        key = d.string_key(r)
        if key and d.strings_path:
            self.link.setText("%s  in %s" % (key, os.path.basename(d.strings_path)))
            self.link.show()
        else:
            self.link.hide()
        for c, (_, _, edit, _) in enumerate(self.fields):
            if not edit.hasFocus():
                edit.set_value(d.text(r, c), d.is_modified(r, c))

    def focus_column(self, c):
        if 0 <= c < len(self.fields):
            self.scroll.ensureWidgetVisible(self.fields[c][1], 0, 40)

    def _commit(self, c, text):
        if 0 <= self.row < self.doc.rows:
            self.editor.set_cell(self.row, c, text)

    def _filter(self, text):
        q = text.lower().strip()
        for c, (_, holder, _, name) in enumerate(self.fields):
            holder.setVisible(not q or q in name or q == str(c))

    def _open_strings(self):
        key = self.doc.string_key(self.row)
        if key and self.doc.strings_path:
            self.editor.openRequested.emit(self.doc.strings_path, ("key", key))


class StbEditor(EditorBase):
    def __init__(self, doc, workspace, open_doc_for=None, parent=None):
        super().__init__(doc, workspace, open_doc_for, parent)
        self._label_width = 0
        self._labels_decided = False
        self.model = StbModel(doc, self)
        self.proxy = StbProxy(doc)
        self.proxy.setSourceModel(self.model)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.banner = widgets.Banner()
        lay.addWidget(self.banner)

        bar = QFrame()
        bar.setObjectName("EditorToolbar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(10, 7, 10, 7)
        bl.setSpacing(6)
        self.search = widgets.SearchField("Filter rows  ·  #123 jumps to a row")
        self.search.setFixedWidth(300)
        self.search.textChanged.connect(lambda _t: self._debounce.start())
        self.search.returnPressed.connect(self._search_enter)
        self.search.escaped.connect(lambda: self.view.setFocus())
        bl.addWidget(self.search)
        self.scope = QComboBox()
        self.scope.setMinimumWidth(150)
        self.scope.setMaxVisibleItems(24)
        self.scope.addItem("All columns", -1)
        for c in range(doc.cols):
            self.scope.addItem("%d · %s" % (c, doc.colname(c) or "column %d" % c), c)
        self.scope.currentIndexChanged.connect(lambda _i: self._apply_filter())
        bl.addWidget(self.scope)
        self.hide_empty = widgets.tool_button("eye-off", "Hide empty rows", self._apply_filter, checkable=True)
        bl.addWidget(self.hide_empty)
        bl.addSpacing(4)
        self.count = widgets.chip("")
        bl.addWidget(self.count)
        bl.addStretch(1)
        bl.addWidget(widgets.text_button("rows-plus", "Append rows", self.append_rows))
        bl.addWidget(widgets.vline())
        self.labels_btn = widgets.tool_button("text", "Show row names", self._labels_clicked, checkable=True)
        bl.addWidget(self.labels_btn)
        self.insp_btn = widgets.tool_button("panel-right", "Toggle row inspector", self._inspector_toggled,
                                            checkable=True, shortcut_text="Ctrl+I")
        bl.addWidget(self.insp_btn)
        lay.addWidget(bar)

        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.setChildrenCollapsible(False)
        self.view = GridView()
        self.view.setModel(self.proxy)
        self.view.horizontalHeader().setSortIndicatorShown(False)
        self.split.addWidget(self.view)
        self.inspector = StbInspector(self)
        self.split.addWidget(self.inspector)
        self.split.setStretchFactor(0, 1)
        self.split.setStretchFactor(1, 0)
        self.split.setSizes([900, 340])
        lay.addWidget(self.split, 1)

        self._debounce = QTimer(self, singleShot=True, interval=140)
        self._debounce.timeout.connect(self._apply_filter)

        self.view.selectionModel().currentChanged.connect(self._current_changed)
        self.view.copyRequested.connect(self.copy_cells)
        self.view.pasteRequested.connect(self.paste_cells)
        self.view.clearRequested.connect(self.clear_cells)
        self.view.customContextMenuRequested.connect(self._cell_menu)
        self.view.horizontalHeader().customContextMenuRequested.connect(self._col_menu)
        self.view.verticalHeader().customContextMenuRequested.connect(self._row_menu)
        doc.cellsChanged.connect(lambda *a: self.inspector.refresh())
        doc.labelsChanged.connect(self.inspector.refresh)
        doc.rowsAppended.connect(self._update_count)
        doc.rowsRemoved.connect(self._update_count)
        doc.saved.connect(self.inspector.refresh)

        s = self.settings()
        show_insp = s.value("stb/inspector", True, type=bool)
        self.insp_btn.setChecked(show_insp)
        self.inspector.setVisible(show_insp)

        sample = [r for r in range(doc.rows) if doc.occupied(r)][:250]
        fit_columns(self.view, doc.cols, sample, doc.text, doc.colname)
        self.refresh_strings()
        self._update_count()

    # ------------------------------------------------------------ strings
    def refresh_strings(self):
        doc = self.doc
        stl = ws.companion_stl(doc.path)
        if stl:
            names = self.workspace.names_for(stl, self.open_doc_for(stl))
            key_col = doc.key_col if doc.key_col is not None else ws.sniff_key_column(doc.stb.d, set(names))
            doc.attach_strings(stl, names, key_col)
        self._size_labels()

    def _size_labels(self):
        """Row names come only from the companion STL, and are **off until the
        user turns them on** (``T``; remembered). Showing them automatically when
        "enough" differed from column 0 read as a ghost copy of column 0 in
        LIST_FOOT, where two names in three are the same."""
        doc = self.doc
        fm = QFontMetrics(theme.ui_font(9.0))
        w = 0
        for r in range(min(doc.rows, 600)):
            lab = doc.row_label(r)
            if lab:
                w = max(w, fm.horizontalAdvance(lab[:40]))
        self._label_width = min(240, max(90, w + 8)) if w else 0
        self.labels_btn.setEnabled(bool(w))
        if not w:
            self.labels_btn.setToolTip("No row names: %s has no string table"
                                       % doc.name if not doc.strings_path else
                                       "No row names: no column of %s holds %s keys"
                                       % (doc.name, os.path.basename(doc.strings_path)))
        else:
            self.labels_btn.setToolTip("Show each row's in-game name from %s" % os.path.basename(doc.strings_path))
        if not self._labels_decided:
            self._labels_decided = True
            self.labels_btn.blockSignals(True)
            self.labels_btn.setChecked(bool(w) and self.settings().value("stb/row_names", False, type=bool))
            self.labels_btn.blockSignals(False)
        self._toggle_labels(self.labels_btn.isChecked() and bool(w))

    def _toggle_labels(self, on):
        self.view.verticalHeader().set_label_width(self._label_width if on else 0)
        self.view.set_corner_text("In-game name" if on and self._label_width else "")

    def _labels_clicked(self, on):
        self.settings().setValue("stb/row_names", on)
        self._toggle_labels(on and bool(self._label_width))

    def activated(self):
        self.refresh_strings()

    # ------------------------------------------------------------ filter
    def _apply_filter(self, *_):
        q = self.search.text().strip()
        if GOTO_RE.match(q):
            q = ""
        self.proxy.set_filter(q, self.scope.currentData(), self.hide_empty.isChecked())
        self.view.cells.query = q.lower()
        self.view.viewport().update()
        self._update_count()

    def _update_count(self):
        shown, total = self.proxy.rowCount(), self.doc.rows
        self.count.setText("%s rows" % format(total, ",") if shown == total
                           else "%s of %s rows" % (format(shown, ","), format(total, ",")))
        self.statusChanged.emit()

    def _search_enter(self):
        m = GOTO_RE.match(self.search.text().strip())
        if m:
            self.reveal(("row", int(m.group(1))))
            self.search.clear()
            return
        # Enter in the filter: jump to the first matching cell
        q = self.search.text().strip().lower()
        if self.proxy.rowCount():
            start = self.view.currentIndex()
            for pr in range(start.row() + 1 if start.isValid() else 0, self.proxy.rowCount()):
                for pc in range(self.proxy.columnCount()):
                    idx = self.proxy.index(pr, pc)
                    if q and q in (idx.data() or "").lower():
                        self.view.setCurrentIndex(idx)
                        self.view.center_on(idx)
                        return
            self.view.setCurrentIndex(self.proxy.index(0, 0))
        self.view.setFocus()

    def focus_search(self, prefix=""):
        if prefix:
            self.search.setText(prefix)
        self.search.setFocus()
        self.search.selectAll() if not prefix else self.search.setCursorPosition(len(prefix))

    # ------------------------------------------------------------ navigation
    def reveal(self, target):
        if not target or target[0] != "row":
            return
        r = target[1]
        if not 0 <= r < self.doc.rows:
            self.toast("No row %d" % r, "warning", "%s has rows 0 to %d." % (self.doc.name, self.doc.rows - 1))
            return
        pidx = self.proxy.mapFromSource(self.model.index(r, max(0, self.view.currentIndex().column())))
        if not pidx.isValid():
            self.search.blockSignals(True)
            self.search.clear()
            self.search.blockSignals(False)
            self.hide_empty.setChecked(False)
            self._apply_filter()
            pidx = self.proxy.mapFromSource(self.model.index(r, 0))
        self.view.setCurrentIndex(pidx)
        self.view.center_on(pidx)
        self.view.setFocus()

    def _current_changed(self, cur, prev):
        src = self.proxy.mapToSource(cur)
        if cur.row() != prev.row() or not prev.isValid():
            self.inspector.set_row(src.row() if src.isValid() else -1)
        if src.isValid() and self.inspector.isVisible():
            self.inspector.focus_column(src.column())
        self.statusChanged.emit()

    def current_source(self):
        return self.proxy.mapToSource(self.view.currentIndex())

    # ------------------------------------------------------------ editing
    def set_cell(self, r, c, text):
        try:
            self.doc.set_cells([(r, c, text)])
        except ValueError as e:
            self.toast("Edit refused", "error", str(e))

    def _selected_source(self):
        """[(proxy_row, proxy_col, src_row, src_col)] of the selection."""
        out = []
        for idx in self.view.selectionModel().selectedIndexes():
            s = self.proxy.mapToSource(idx)
            out.append((idx.row(), idx.column(), s.row(), s.column()))
        return out

    def _selected_rows(self):
        rows = sorted({s for _, _, s, _ in self._selected_source()})
        if not rows:
            cur = self.current_source()
            if cur.isValid():
                rows = [cur.row()]
        return rows

    def copy_cells(self):
        sel = self._selected_source()
        if not sel:
            return
        prow = sorted({p for p, _, _, _ in sel})
        pcol = sorted({c for _, c, _, _ in sel})
        cells = {(p, c): (sr, sc) for p, c, sr, sc in sel}
        lines = []
        for p in prow:
            vals = []
            for c in pcol:
                sc = cells.get((p, c))
                vals.append(self.doc.text(*sc) if sc else "")
            lines.append("\t".join(vals))
        self.set_clipboard("\n".join(lines))
        n = len(sel)
        self.toast("Copied %d cell%s" % (n, "s" if n != 1 else ""), "info")

    def copy_rows(self):
        rows = self._selected_rows()
        if not rows:
            return
        self.set_clipboard("\n".join("\t".join(self.doc.text(r, c) for c in range(self.doc.cols)) for r in rows))
        self.toast("Copied %d row%s" % (len(rows), "s" if len(rows) != 1 else ""), "info",
                   "Paste on another row to clone it, or into a spreadsheet.")

    def paste_row(self):
        cur = self.view.currentIndex()
        if not cur.isValid():
            return
        self.view.setCurrentIndex(cur.siblingAtColumn(0))
        self.view.selectionModel().select(cur.siblingAtColumn(0), QItemSelectionModel.SelectionFlag.ClearAndSelect)
        self.paste_cells()

    def paste_cells(self):
        text = self.clipboard_text()
        if not text:
            return
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        grid = [ln.split("\t") for ln in lines]
        sel = self._selected_source()
        changes = []
        if len(grid) == 1 and len(grid[0]) == 1 and len(sel) > 1:
            changes = [(sr, sc, grid[0][0]) for _, _, sr, sc in sel]
        else:
            if sel:
                ar, ac = min(p for p, _, _, _ in sel), min(c for _, c, _, _ in sel)
            else:
                cur = self.view.currentIndex()
                if not cur.isValid():
                    return
                ar, ac = cur.row(), cur.column()
            lost = 0
            for i, vals in enumerate(grid):
                for j, v in enumerate(vals):
                    pr, pc = ar + i, ac + j
                    if pr >= self.proxy.rowCount() or pc >= self.proxy.columnCount():
                        lost += 1
                        continue
                    s = self.proxy.mapToSource(self.proxy.index(pr, pc))
                    changes.append((s.row(), s.column(), v))
            if lost:
                self.toast("%d value%s did not fit" % (lost, "s" if lost != 1 else ""), "warning",
                           "The pasted block runs past the last row or column.")
        try:
            n = self.doc.set_cells(changes, "Paste")
        except ValueError as e:
            self.toast("Paste refused", "error", str(e))
            return
        if n:
            self.toast("Pasted %d cell%s" % (n, "s" if n != 1 else ""), "success")

    def clear_cells(self):
        sel = self._selected_source()
        try:
            self.doc.set_cells([(sr, sc, "") for _, _, sr, sc in sel], "Clear cells")
        except ValueError:
            pass

    def clear_rows(self):
        rows = self._selected_rows()
        changes = [(r, c, "") for r in rows for c in range(self.doc.cols)]
        if self.doc.set_cells(changes, "Clear %d row%s" % (len(rows), "s" if len(rows) != 1 else "")):
            self.toast("Cleared %d row%s" % (len(rows), "s" if len(rows) != 1 else ""), "info", "Ctrl+Z puts it back.")

    def fill_selection(self):
        sel = self._selected_source()
        if not sel:
            return
        v = self.ask_text("Fill selection", "Value for %d cell%s:" % (len(sel), "s" if len(sel) != 1 else ""))
        if v is None:
            return
        try:
            self.doc.set_cells([(sr, sc, v) for _, _, sr, sc in sel], "Fill %d cells" % len(sel))
        except ValueError as e:
            self.toast("Fill refused", "error", str(e))

    def append_rows(self):
        n = self.ask_int("Append rows", "Blank rows to add after row %d:" % (self.doc.rows - 1), 1, 1, 10000)
        if not n:
            return
        first = self.doc.rows
        self.doc.append_rows(n)
        self.reveal(("row", first))
        self.toast("Added rows %d–%d" % (first, first + n - 1), "success")

    # ------------------------------------------------------------ menus
    def _menu(self):
        m = QMenu(self)
        return m

    def _act(self, menu, icon, text, slot, shortcut=None, enabled=True):
        a = menu.addAction(icons.icon(icon) if icon else icons.icon("dot", "#00000000"), text)
        a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(shortcut)
            a.setShortcutVisibleInContextMenu(True)
        a.setEnabled(enabled)
        return a

    def _cell_menu(self, pos):
        idx = self.view.indexAt(pos)
        m = self._menu()
        self._act(m, "copy", "Copy", self.copy_cells, "Ctrl+C")
        self._act(m, "clipboard", "Paste", self.paste_cells, "Ctrl+V")
        self._act(m, "eraser", "Clear cells", self.clear_cells, "Del")
        self._act(m, None, "Fill selection…", self.fill_selection)
        m.addSeparator()
        if idx.isValid():
            val = idx.data() or ""
            col = self.proxy.mapToSource(idx).column()
            self._act(m, "filter", "Filter by “%s”" % (val[:24] + ("…" if len(val) > 24 else "")),
                      lambda: self._filter_by(col, val), enabled=bool(val.strip()))
            self._act(m, "sort", "Sort by this column", lambda: self._sort(idx.column(), Qt.SortOrder.AscendingOrder))
        if self.proxy.sortColumn() >= 0:
            self._act(m, None, "Clear sort", self._clear_sort)
        key = self.doc.string_key(self.current_source().row()) if self.current_source().isValid() else ""
        if key and self.doc.strings_path:
            m.addSeparator()
            self._act(m, "external", "Open %s in %s" % (key, os.path.basename(self.doc.strings_path)),
                      self.inspector._open_strings)
        m.exec(self.view.viewport().mapToGlobal(pos))

    def _col_menu(self, pos):
        hh = self.view.horizontalHeader()
        c = hh.logicalIndexAt(pos)
        if c < 0:
            return
        m = self._menu()
        self._act(m, "chevron-up", "Sort ascending", lambda: self._sort(c, Qt.SortOrder.AscendingOrder))
        self._act(m, "chevron-down", "Sort descending", lambda: self._sort(c, Qt.SortOrder.DescendingOrder))
        self._act(m, None, "Clear sort", self._clear_sort, enabled=self.proxy.sortColumn() >= 0)
        m.addSeparator()
        self._act(m, "filter", "Filter in this column", lambda: (self.scope.setCurrentIndex(c + 1), self.focus_search()))
        self._act(m, None, "Select column", lambda: self.view.selectColumn(c))
        m.exec(hh.mapToGlobal(pos))

    def _row_menu(self, pos):
        vh = self.view.verticalHeader()
        r = vh.logicalIndexAt(pos)
        if r < 0:
            return
        if not self.view.selectionModel().isRowSelected(r, QModelIndex()):
            self.view.selectRow(r)
        m = self._menu()
        self._act(m, "copy", "Copy row", self.copy_rows)
        self._act(m, "clipboard", "Paste row", self.paste_row)
        self._act(m, "eraser", "Clear row", self.clear_rows)
        m.exec(vh.mapToGlobal(pos))

    def _filter_by(self, col, val):
        self.scope.blockSignals(True)
        self.scope.setCurrentIndex(col + 1)
        self.scope.blockSignals(False)
        self.search.setText(val.strip())
        self._apply_filter()

    def _sort(self, col, order):
        self.view.horizontalHeader().setSortIndicatorShown(True)
        self.view.horizontalHeader().setSortIndicator(col, order)
        self.proxy.sort(col, order)

    def _clear_sort(self):
        self.view.horizontalHeader().setSortIndicatorShown(False)
        self.proxy.sort(-1)

    # ------------------------------------------------------------ inspector
    def toggle_inspector(self):
        self.insp_btn.toggle()

    def _inspector_toggled(self, on):
        self.inspector.setVisible(on)
        self.settings().setValue("stb/inspector", on)
        if on:
            self.inspector.refresh()

    # ------------------------------------------------------------ status
    def status_left(self):
        d = self.doc
        return "STB  ·  %s rows × %d columns  ·  %s" % (format(d.rows, ","), d.cols,
                                                         ENCODING_NAMES.get(d.encoding, d.encoding))

    def status_position(self):
        s = self.current_source()
        if not s.isValid():
            return ""
        c = s.column()
        name = self.doc.colname(c)
        codec = self.doc.cell_codec(s.row(), c)
        return "Row %d  ·  Col %d (editor %d)%s%s" % (
            s.row(), c, c + 1, "  ·  " + name if name else "",
            "  ·  cell text is %s" % ENCODING_NAMES.get(codec, codec) if codec != self.doc.encoding else "")

    def view_state(self):
        s = self.current_source()
        return {"row": s.row(), "col": s.column()} if s.isValid() else None

    def restore_view_state(self, st):
        if st and st.get("row", -1) >= 0:
            self.reveal(("row", st["row"]))
            idx = self.proxy.mapFromSource(self.model.index(st["row"], max(0, st.get("col", 0))))
            if idx.isValid():
                self.view.setCurrentIndex(idx)
