"""STL string-table editor: entries in a grid, one language slot at a time."""
import os

from PyQt6.QtCore import (QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt,
                          QTimer)
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QFormLayout,
                             QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox,
                             QPushButton, QScrollArea, QSplitter, QVBoxLayout, QWidget)

from . import icons, theme, widgets, workspace as ws
from .documents import ENCODING_NAMES
from .editor_base import EditorBase
from .grid import (ROLE_MODIFIED, ROLE_MULTILINE, ROLE_NAME, ROLE_NUMERIC, ROLE_SORT,
                   GridView)

FIRST_FIELD = 2     # grid columns: key, id, then the entry's fields


class StlModel(QAbstractTableModel):
    def __init__(self, doc, editor):
        super().__init__()
        self.doc, self.editor = doc, editor
        self.slot = 0
        doc.entriesChanged.connect(self._changed)
        doc.entriesAboutToBeInserted.connect(lambda a, b: self.beginInsertRows(QModelIndex(), a, b))
        doc.entriesInserted.connect(self.endInsertRows)
        doc.entriesAboutToBeRemoved.connect(lambda a, b: self.beginRemoveRows(QModelIndex(), a, b))
        doc.entriesRemoved.connect(self.endRemoveRows)
        doc.saved.connect(self._all)

    def set_slot(self, slot):
        self.slot = slot
        self._all()
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, self.columnCount() - 1)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else self.doc.count

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else FIRST_FIELD + self.doc.nfields

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        e, c = index.row(), index.column()
        d = self.doc
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if c == 0:
                return d.key(e)
            if c == 1:
                return str(d.ident(e))
            return d.field(e, c - FIRST_FIELD, self.slot)
        if role == ROLE_MODIFIED:
            if c == 0:
                return d.key_modified(e)
            if c == 1:
                return d.id_modified(e)
            return d.is_modified(e, c - FIRST_FIELD, self.slot)
        if role == ROLE_NUMERIC:
            return c == 1
        if role == ROLE_MULTILINE:
            return c > FIRST_FIELD
        if role == ROLE_SORT:
            if c == 1:
                return (0, d.ident(e), "")
            v = self.data(index).lower()
            return (0 if v else 1, 0, v)
        if role == Qt.ItemDataRole.ToolTipRole and c >= FIRST_FIELD:
            v = d.field(e, c - FIRST_FIELD, self.slot)
            return v if len(v) > 40 or "\n" in v else None
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole:
            return False
        e, c = index.row(), index.column()
        try:
            if c == 0:
                self.doc.set_key(e, value.strip())
            elif c == 1:
                self.doc.set_ident(e, value)
            else:
                self.doc.set_field(e, c - FIRST_FIELD, self.slot, value)
        except ValueError as err:
            self.editor.toast("Edit refused", "error", str(err))
            return False
        return True

    def flags(self, index):
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        d = self.doc
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                if section < FIRST_FIELD:
                    return ("string key", "id")[section]
                if d.nslots == 1:
                    return "text"
                return "%s%s" % (d.slot_names[self.slot],
                                 "  ·  in game" if self.slot == d.display_slot() else "  ·  not read by the game")
            if role == ROLE_NAME:
                return ("Key", "ID")[section] if section < FIRST_FIELD else d.field_names[section - FIRST_FIELD]
            if role == Qt.ItemDataRole.ToolTipRole:
                if section == 0:
                    return "The key the STB rows name (LWEA001 …). Renaming it breaks every row that uses it."
                if section == 1:
                    return "Numeric id stored beside the key"
                if section > FIRST_FIELD:
                    return "Multi-line: edit it in the inspector (Enter or double-click)"
        else:
            if section >= d.count:
                return None
            if role == Qt.ItemDataRole.DisplayRole:
                return str(section)
            if role == ROLE_MODIFIED:
                return d.entry_modified(section)
        return None

    def _changed(self, a, b):
        self.dataChanged.emit(self.index(a, 0), self.index(b, self.columnCount() - 1))
        self.headerDataChanged.emit(Qt.Orientation.Vertical, a, b)

    def _all(self):
        if self.doc.count:
            self._changed(0, self.doc.count - 1)


class StlProxy(QSortFilterProxyModel):
    def __init__(self, doc):
        super().__init__()
        self.doc = doc
        self.query, self.slot = "", 0
        self.setSortRole(ROLE_SORT)
        self.setDynamicSortFilter(False)

    def set_filter(self, query, slot):
        self.query, self.slot = query.lower(), slot
        self.invalidateFilter()

    def filterAcceptsRow(self, e, parent):
        return not self.query or self.query in self.doc.search_text(e, self.slot)

    def lessThan(self, a, b):
        return a.data(ROLE_SORT) < b.data(ROLE_SORT)


class AddEntryDialog(QDialog):
    def __init__(self, doc, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle("Add string entry")
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(12)
        title = QLabel("New entry in %s" % doc.name)
        title.setFont(theme.ui_font(12, QFont.Weight.DemiBold))
        lay.addWidget(title)
        hint = QLabel("Entries are added at the end: the client reads them in file order. "
                      "The name is written to every language slot.")
        hint.setObjectName("Dim")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        form = QFormLayout()
        form.setSpacing(8)
        self.key = QLineEdit(doc.suggest_key())
        self.ident = QLineEdit(str(doc.suggest_id()))
        self.name = QLineEdit()
        self.name.setPlaceholderText("Display name")
        form.addRow("Key", self.key)
        form.addRow("ID", self.ident)
        form.addRow(doc.field_names[0], self.name)
        lay.addLayout(form)
        self.error = QLabel("")
        self.error.setObjectName("Error")
        lay.addWidget(self.error)
        buttons = QDialogButtonBox()
        self.ok = buttons.addButton("Add entry", QDialogButtonBox.ButtonRole.AcceptRole)
        self.ok.setObjectName("Primary")
        buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.key.textChanged.connect(self._validate)
        self.ident.textChanged.connect(self._validate)
        self.name.setFocus()
        self._validate()

    def _validate(self):
        err = self.doc.validate_key(self.key.text().strip())
        if not err:
            try:
                v = int(self.ident.text().strip())
                if not 0 <= v <= 0xFFFFFFFF:
                    err = "The id is an unsigned 32-bit number"
            except ValueError:
                err = "The id is a whole number"
        self.error.setText(err or "")
        self.ok.setEnabled(not err)
        return not err

    def _accept(self):
        if self._validate():
            self.accept()


class StlInspector(QFrame):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.doc = editor.doc
        self.setObjectName("Inspector")
        self.setMinimumWidth(300)
        self.entry = -1

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body.setObjectName("InspectorBody")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(6)
        self.scroll.setWidget(body)
        outer.addWidget(self.scroll, 1)

        lay.addWidget(widgets.caps_label("Entry"))
        self.title = QLabel("No entry selected")
        self.title.setFont(theme.ui_font(13, QFont.Weight.DemiBold))
        self.title.setWordWrap(True)
        lay.addWidget(self.title)
        meta = QHBoxLayout()
        self.sub = QLabel("")
        self.sub.setObjectName("Dim")
        meta.addWidget(self.sub)
        self.chip = widgets.chip("modified", modified=True)
        self.chip.hide()
        meta.addWidget(self.chip)
        meta.addStretch(1)
        lay.addLayout(meta)
        lay.addSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(8)
        kbox, self.key = self._field("Key", widgets.CommitLineEdit())
        ibox, self.ident = self._field("ID", widgets.CommitLineEdit())
        self.ident.setMaximumWidth(110)
        self.key.committed.connect(lambda v: self._commit_key(v))
        self.ident.committed.connect(lambda v: self._commit_id(v))
        row.addLayout(kbox, 1)
        row.addLayout(ibox)
        lay.addLayout(row)

        lay.addSpacing(10)
        self.slot_title = widgets.caps_label("Text")
        lay.addWidget(self.slot_title)
        self.shared = QLabel("")
        self.shared.setObjectName("Hint")
        self.shared.setWordWrap(True)
        lay.addWidget(self.shared)
        self.fields = []
        for f, fname in enumerate(self.doc.field_names):
            ed = widgets.CommitLineEdit() if f == 0 else widgets.CommitTextEdit()
            if f:
                ed.setMinimumHeight(96)
            box, _ = self._field(fname, ed)
            ed.committed.connect(lambda v, f=f: self._commit_field(f, v))
            lay.addLayout(box)
            self.fields.append(ed)

        self.others_title = widgets.caps_label("Other language slots")
        lay.addSpacing(10)
        lay.addWidget(self.others_title)
        self.others = QVBoxLayout()
        self.others.setSpacing(2)
        lay.addLayout(self.others)

        self.used_title = widgets.caps_label("Used by")
        lay.addSpacing(10)
        lay.addWidget(self.used_title)
        self.used = QVBoxLayout()
        self.used.setSpacing(0)
        lay.addLayout(self.used)
        lay.addStretch(1)

        foot = QWidget()
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(12, 8, 12, 10)
        fl.addStretch(1)
        rm = widgets.text_button("trash", "Remove entry", editor.remove_entries)
        rm.setToolTip("Remove the selected entries (every language slot)")
        fl.addWidget(rm)
        outer.addWidget(foot)
        self.set_entry(-1)

    @staticmethod
    def _field(label, editor):
        box = QVBoxLayout()
        box.setSpacing(3)
        lab = QLabel(label)
        lab.setObjectName("Dim")
        box.addWidget(lab)
        box.addWidget(editor)
        return box, editor

    def _clear(self, layout):
        widgets.clear_layout(layout)

    def set_entry(self, e):
        self.entry = e
        valid = 0 <= e < self.doc.count
        for w in [self.key, self.ident] + self.fields:
            w.setEnabled(valid)
        if not valid:
            self.title.setText("No entry selected")
            self.sub.setText("Select a row to edit its text here.")
            self.chip.hide()
            self.key.set_value("")
            self.ident.set_value("")
            for ed in self.fields:
                ed.set_value("")
            self._clear(self.others)
            self._clear(self.used)
            self.others_title.hide()
            self.used_title.hide()
            return
        self.refresh(full=True)

    def refresh(self, full=False):
        e = self.entry
        d = self.doc
        if not 0 <= e < d.count:
            return
        slot = self.editor.slot
        name = d.field(e, 0, slot)
        self.title.setText(name or d.key(e))
        self.sub.setText("Entry %d" % e)
        self.chip.setVisible(d.entry_modified(e))
        if not self.key.hasFocus():
            self.key.set_value(d.key(e), d.key_modified(e))
        if not self.ident.hasFocus():
            self.ident.set_value(str(d.ident(e)), d.id_modified(e))
        all_langs = getattr(self.editor, "all_langs", False)
        self.slot_title.setText(("Text · " + d.slot_names[slot]).upper() if all_langs else "TEXT")
        shared = d.shared_slots(slot)
        if len(shared) > 1 and all_langs:
            self.shared.setText("Slots %s share one block on disk; an edit here applies to all of them "
                                "while their text is the same." % ", ".join(map(str, shared)))
            self.shared.show()
        else:
            self.shared.hide()
        for f, ed in enumerate(self.fields):
            if not ed.hasFocus():
                ed.set_value(d.field(e, f, slot), d.is_modified(e, f, slot))
        # other slots
        self._clear(self.others)
        others = [s for s in range(d.nslots) if s != slot] if all_langs else []
        self.others_title.setVisible(bool(others))
        for s in others:
            b = QPushButton()
            b.setObjectName("ListItem")
            text = d.field(e, 0, s) or "—"
            b.setText("%s    %s" % (d.slot_names[s], text if len(text) < 60 else text[:57] + "…"))
            b.setToolTip("Show slot %d" % s)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, s=s: self.editor.set_slot(s))
            self.others.addWidget(b)
        if full:
            self._fill_used()

    def _fill_used(self):
        self._clear(self.used)
        e, d = self.entry, self.doc
        stb = ws.companion_stb(d.path)
        rows = []
        if stb:
            rows = self.editor.workspace.stb_rows_with_key(stb, d.key(e), self.editor.open_doc_for(stb))
        self.used_title.setVisible(bool(stb))
        if not stb:
            return
        if not rows:
            lab = QLabel("No row of %s names this key." % os.path.basename(stb))
            lab.setObjectName("Hint")
            lab.setWordWrap(True)
            self.used.addWidget(lab)
            return
        for r in rows[:12]:
            b = QPushButton("%s  ·  row %d" % (os.path.basename(stb), r))
            b.setObjectName("Link")
            b.setIcon(icons.icon("external", theme.current().accent))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, r=r: self.editor.openRequested.emit(stb, ("row", r)))
            self.used.addWidget(b)
        if len(rows) > 12:
            more = QLabel("… and %d more" % (len(rows) - 12))
            more.setObjectName("Hint")
            self.used.addWidget(more)

    def focus_field(self, f):
        if 0 <= f < len(self.fields):
            self.fields[f].setFocus()
            self.scroll.ensureWidgetVisible(self.fields[f], 0, 60)

    def _commit_key(self, v):
        try:
            self.doc.set_key(self.entry, v.strip())
        except ValueError as e:
            self.editor.toast("Key not changed", "error", str(e))
            self.key.set_value(self.doc.key(self.entry))

    def _commit_id(self, v):
        try:
            self.doc.set_ident(self.entry, v)
        except ValueError as e:
            self.editor.toast("ID not changed", "error", str(e))
            self.ident.set_value(str(self.doc.ident(self.entry)))

    def _commit_field(self, f, v):
        if not 0 <= self.entry < self.doc.count:
            return
        try:
            self.doc.set_field(self.entry, f, self.editor.slot, v)
        except ValueError as e:
            self.editor.toast("Text not changed", "error", str(e))


class StlEditor(EditorBase):
    def __init__(self, doc, workspace, open_doc_for=None, parent=None):
        super().__init__(doc, workspace, open_doc_for, parent)
        self.slot = doc.display_slot()
        self.model = StlModel(doc, self)
        self.model.slot = self.slot
        self.proxy = StlProxy(doc)
        self.proxy.slot = self.slot
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
        bl.setSpacing(8)
        self.search = widgets.SearchField("Filter by key, id or text")
        self.search.setFixedWidth(280)
        self.search.textChanged.connect(lambda _t: self._debounce.start())
        self.search.escaped.connect(lambda: self.view.setFocus())
        self.search.returnPressed.connect(lambda: self.view.setFocus())
        bl.addWidget(self.search)
        # The game reads one slot (English); the other four are kept but hidden
        # behind a toggle, so nobody edits a language the client never shows.
        self.slots = widgets.Segmented()
        self.lang_btn = None
        if doc.nslots > 1:
            tips = ["Slot %d · %s · %s%s" % (s, doc.slot_names[s], ENCODING_NAMES.get(doc.slot_enc[s], doc.slot_enc[s]),
                                            "  ·  read by the game" if s == doc.display_slot() else "")
                    for s in range(doc.nslots)]
            self.slots.set_items([doc.slot_names[s] for s in range(doc.nslots)], tips, self.slot)
            self.slots.changed.connect(self.set_slot)
            bl.addWidget(self.slots)
            self.lang_btn = widgets.tool_button("globe", "Show the other language slots (the game reads only %s)"
                                                % doc.slot_names[doc.display_slot()], self._langs_toggled,
                                                checkable=True)
            bl.addWidget(self.lang_btn)
        self.count = widgets.chip("")
        bl.addWidget(self.count)
        bl.addStretch(1)
        bl.addWidget(widgets.text_button("plus", "Add entry", self.add_entry))
        bl.addWidget(widgets.vline())
        self.insp_btn = widgets.tool_button("panel-right", "Toggle entry inspector", self._inspector_toggled,
                                            checkable=True, shortcut_text="Ctrl+I")
        bl.addWidget(self.insp_btn)
        lay.addWidget(bar)

        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.setChildrenCollapsible(False)
        self.view = GridView()
        self.view.setModel(self.proxy)
        self.view.verticalHeader().set_label_width(0)
        self.split.addWidget(self.view)
        self.inspector = StlInspector(self)
        self.split.addWidget(self.inspector)
        self.split.setStretchFactor(0, 1)
        self.split.setSizes([860, 380])
        lay.addWidget(self.split, 1)

        hh = self.view.horizontalHeader()
        hh.resizeSection(0, 150)
        hh.resizeSection(1, 80)
        for f in range(doc.nfields):
            hh.resizeSection(FIRST_FIELD + f, 300 if f == 0 else 460)
        hh.setStretchLastSection(True)

        self._debounce = QTimer(self, singleShot=True, interval=140)
        self._debounce.timeout.connect(self._apply_filter)
        self.view.selectionModel().currentChanged.connect(self._current_changed)
        self.view.activatedMultiline.connect(self._edit_multiline)
        self.view.copyRequested.connect(self.copy_cells)
        self.view.pasteRequested.connect(self.paste_cells)
        self.view.clearRequested.connect(self.clear_cells)
        self.view.customContextMenuRequested.connect(self._cell_menu)
        doc.entriesChanged.connect(lambda *a: self.inspector.refresh())
        doc.entriesInserted.connect(self._update_count)
        doc.entriesRemoved.connect(self._update_count)
        doc.saved.connect(self.inspector.refresh)

        self.all_langs = False
        if self.lang_btn is not None:
            on = self.settings().value("stl/all_languages", False, type=bool)
            self.lang_btn.setChecked(on)
            self._langs_toggled(on, save=False)

        on = self.settings().value("stl/inspector", True, type=bool)
        self.insp_btn.setChecked(on)
        self.inspector.setVisible(on)
        self._update_count()

    # ------------------------------------------------------------ slots
    def _langs_toggled(self, on, save=True):
        self.all_langs = on
        self.slots.setVisible(on)
        if not on:
            self.set_slot(self.doc.display_slot())
        if save:
            self.settings().setValue("stl/all_languages", on)
        self.inspector.refresh()
        self.model.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, self.model.columnCount() - 1)

    def set_slot(self, s):
        if s == self.slot:
            return
        self.slot = s
        self.model.set_slot(s)
        self.proxy.slot = s
        self.slots.set_current(s)
        self._apply_filter()
        self.inspector.refresh()
        self.statusChanged.emit()

    # ------------------------------------------------------------ filter
    def _apply_filter(self):
        q = self.search.text().strip()
        self.proxy.set_filter(q, self.slot)
        self.view.cells.query = q.lower()
        self.view.viewport().update()
        self._update_count()

    def _update_count(self):
        shown, total = self.proxy.rowCount(), self.doc.count
        self.count.setText("%s entries" % format(total, ",") if shown == total
                           else "%s of %s entries" % (format(shown, ","), format(total, ",")))
        self.statusChanged.emit()

    def focus_search(self, prefix=""):
        self.search.setFocus()
        self.search.selectAll()

    # ------------------------------------------------------------ navigation
    def reveal(self, target):
        if not target:
            return
        e = None
        if target[0] == "key":
            e = self.doc.index_of(target[1])
            if e is None:
                self.toast("%s is not in %s" % (target[1], self.doc.name), "warning",
                           "Add it with “Add entry” if the table needs it.")
                return
        elif target[0] == "entry":
            e = target[1]
        if e is None or not 0 <= e < self.doc.count:
            return
        pidx = self.proxy.mapFromSource(self.model.index(e, 0))
        if not pidx.isValid():
            self.search.blockSignals(True)
            self.search.clear()
            self.search.blockSignals(False)
            self._apply_filter()
            pidx = self.proxy.mapFromSource(self.model.index(e, 0))
        pidx = pidx.siblingAtColumn(FIRST_FIELD)
        self.view.setCurrentIndex(pidx)
        self.view.center_on(pidx)
        self.view.setFocus()

    def _current_changed(self, cur, prev):
        src = self.proxy.mapToSource(cur)
        if cur.row() != prev.row() or not prev.isValid():
            self.inspector.set_entry(src.row() if src.isValid() else -1)
        self.statusChanged.emit()

    def _edit_multiline(self, idx):
        if not self.inspector.isVisible():
            self.insp_btn.setChecked(True)
        self.inspector.focus_field(idx.column() - FIRST_FIELD)

    def current_source(self):
        return self.proxy.mapToSource(self.view.currentIndex())

    # ------------------------------------------------------------ editing
    def add_entry(self):
        dlg = AddEntryDialog(self.doc, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            e = self.doc.add_entry(dlg.key.text().strip(), int(dlg.ident.text().strip()), dlg.name.text())
        except ValueError as err:
            self.toast("Entry not added", "error", str(err))
            return
        self.reveal(("entry", e))
        self.toast("Added %s" % dlg.key.text().strip(), "success", "Entry %d" % e)

    def _selected_entries(self):
        rows = sorted({self.proxy.mapToSource(i).row() for i in self.view.selectionModel().selectedIndexes()})
        if not rows and self.current_source().isValid():
            rows = [self.current_source().row()]
        return rows

    def remove_entries(self):
        rows = self._selected_entries()
        if not rows:
            return
        what = self.doc.key(rows[0]) if len(rows) == 1 else "%d entries" % len(rows)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Remove entries")
        box.setText("Remove %s from %s?" % (what, self.doc.name))
        box.setInformativeText("Every language slot loses it. Any STB row that still names the key "
                               "will show a blank name in game. Ctrl+Z undoes this.")
        rm = box.addButton("Remove", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is rm:
            self.doc.remove_entries(rows)
            self.toast("Removed %s" % what, "info", "Ctrl+Z puts it back.")

    def _selected_cells(self):
        out = []
        for idx in self.view.selectionModel().selectedIndexes():
            s = self.proxy.mapToSource(idx)
            out.append((idx.row(), idx.column(), s.row(), s.column()))
        return out

    def copy_cells(self):
        sel = self._selected_cells()
        if not sel:
            return
        prow = sorted({p for p, _, _, _ in sel})
        pcol = sorted({c for _, c, _, _ in sel})
        cells = {(p, c): self.model.index(sr, sc).data() for p, c, sr, sc in sel}
        self.set_clipboard("\n".join("\t".join(cells.get((p, c), "") or "" for c in pcol) for p in prow))
        self.toast("Copied %d cell%s" % (len(sel), "s" if len(sel) != 1 else ""), "info")

    def paste_cells(self):
        text = self.clipboard_text()
        cur = self.view.currentIndex()
        if not text or not cur.isValid():
            return
        lines = text.replace("\r\n", "\n").split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        n = 0
        self.doc.undo.beginMacro("Paste")
        try:
            for i, ln in enumerate(lines):
                for j, v in enumerate(ln.split("\t")):
                    idx = self.proxy.index(cur.row() + i, cur.column() + j)
                    if idx.isValid() and self.proxy.setData(idx, v):
                        n += 1
        finally:
            self.doc.undo.endMacro()
        if n:
            self.toast("Pasted %d cell%s" % (n, "s" if n != 1 else ""), "success")

    def clear_cells(self):
        sel = [(sr, sc) for _, _, sr, sc in self._selected_cells() if sc >= FIRST_FIELD]
        if not sel:
            return
        self.doc.undo.beginMacro("Clear text")
        try:
            for e, c in sel:
                self.doc.set_field(e, c - FIRST_FIELD, self.slot, "")
        finally:
            self.doc.undo.endMacro()

    def _cell_menu(self, pos):
        m = QMenu(self)
        for icon, text, slot, sc in (("copy", "Copy", self.copy_cells, "Ctrl+C"),
                                     ("clipboard", "Paste", self.paste_cells, "Ctrl+V"),
                                     ("eraser", "Clear text", self.clear_cells, "Del")):
            a = m.addAction(icons.icon(icon), text)
            a.triggered.connect(slot)
            a.setShortcut(sc)
            a.setShortcutVisibleInContextMenu(True)
        m.addSeparator()
        m.addAction(icons.icon("plus"), "Add entry…").triggered.connect(self.add_entry)
        m.addAction(icons.icon("trash"), "Remove entries…").triggered.connect(self.remove_entries)
        m.exec(self.view.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------ inspector
    def toggle_inspector(self):
        self.insp_btn.toggle()

    def _inspector_toggled(self, on):
        self.inspector.setVisible(on)
        self.settings().setValue("stl/inspector", on)
        if on:
            self.inspector.refresh(full=True)

    def activated(self):
        if self.inspector.isVisible() and self.inspector.entry >= 0:
            self.inspector._fill_used()

    # ------------------------------------------------------------ status
    def status_left(self):
        d = self.doc
        lang = ("%s  ·  " % d.slot_names[self.slot]) if d.nslots > 1 else ""
        return "STL %s  ·  %s entries  ·  %s%s" % (
            d.format_tag + (" (legacy)" if d.stl.legacy else ""), format(d.count, ","), lang,
            ENCODING_NAMES.get(d.slot_enc[self.slot], d.slot_enc[self.slot]))

    def status_position(self):
        s = self.current_source()
        if not s.isValid():
            return ""
        return "Entry %d  ·  %s" % (s.row(), self.doc.key(s.row()))

    def view_state(self):
        s = self.current_source()
        return {"entry": s.row(), "slot": self.slot} if s.isValid() else {"slot": self.slot}

    def restore_view_state(self, st):
        if not st:
            return
        if "slot" in st and 0 <= st["slot"] < self.doc.nslots:
            self.set_slot(st["slot"])
        if st.get("entry", -1) >= 0:
            self.reveal(("entry", st["entry"]))
