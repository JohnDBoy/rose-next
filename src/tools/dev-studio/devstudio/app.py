"""The studio window: activity bar, explorer, tabs, status bar, palette."""
import ctypes
import json
import os
import sys
import traceback

from PyQt6.QtCore import QFileSystemWatcher, QSettings, QSize, Qt, QTimer
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QUndoGroup
from PyQt6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel,
                             QMainWindow, QMessageBox, QSplitter, QStackedWidget, QTabBar,
                             QTabWidget, QVBoxLayout, QWidget)

from . import icons, theme, widgets
from .documents import BACKUP_ROOT, ENCODINGS, REPO_ROOT, StbDocument, StlDocument
from .explorer import Explorer
from .palette import CommandPalette
from .stb_editor import StbEditor
from .stl_editor import StlEditor
from .welcome import Welcome
from .workspace import Workspace

APP_NAME = "Rose Dev Studio"

# extension -> (Document class, editor class). A new format is a Document over
# its rosefmt codec, an EditorBase subclass, a line here and one in
# workspace.KINDS (which puts it in the explorer).
EDITORS = {
    ".stb": (StbDocument, StbEditor),
    ".stl": (StlDocument, StlEditor),
}


def norm(p):
    return os.path.normcase(os.path.normpath(os.path.abspath(p)))


def dark_title_bar(window, dark):
    """Windows 10 1809+ / 11: match the native title bar to the theme."""
    if sys.platform != "win32":
        return
    try:
        hwnd = int(window.winId())
        val = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):          # DWMWA_USE_IMMERSIVE_DARK_MODE (new, pre-20H1)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), 4) == 0:
                break
    except Exception:
        pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("RoseNext", "DevStudio")
        self.workspace = None
        self.editors = {}           # norm path -> editor
        self.undo_group = QUndoGroup(self)
        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self._file_changed)
        self.toasts = widgets.ToastHost(self)
        self.setWindowTitle(APP_NAME)
        self.resize(1440, 900)
        self._build()
        self._build_menus()
        self.palette = CommandPalette(self)
        self._apply_theme(self.settings.value("theme", "dark"), save=False)
        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        QTimer.singleShot(0, self._startup)

    # ================================================================ layout
    def _build(self):
        shell = QWidget()
        shell.setObjectName("Shell")
        h = QHBoxLayout(shell)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        act = QFrame()
        act.setObjectName("ActivityBar")
        act.setFixedWidth(48)
        al = QVBoxLayout(act)
        al.setContentsMargins(0, 4, 0, 8)
        al.setSpacing(0)
        self.act_explorer = widgets.tool_button("files", "Explorer", None, checkable=True,
                                                size=22, shortcut_text="Ctrl+B")
        self.act_explorer.setChecked(True)
        al.addWidget(self.act_explorer)
        self.act_search = widgets.tool_button("search", "Go to file", lambda: self.open_palette(""), size=22,
                                              shortcut_text="Ctrl+P")
        al.addWidget(self.act_search)
        al.addStretch(1)
        self.act_palette = widgets.tool_button("command", "Command palette", lambda: self.open_palette(">"),
                                               size=20, shortcut_text="Ctrl+Shift+P")
        al.addWidget(self.act_palette)
        self.act_theme = widgets.tool_button("sun", "Switch theme", self._toggle_theme, size=20)
        al.addWidget(self.act_theme)
        h.addWidget(act)

        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.setChildrenCollapsible(False)
        self.explorer = Explorer()
        self.explorer.openRequested.connect(lambda p: self.open_path(p))
        self.explorer.chooseRootRequested.connect(self.choose_root)
        self.explorer.refreshRequested.connect(self.rescan)
        self.split.addWidget(self.explorer)
        self.act_explorer.toggled.connect(self._toggle_sidebar)

        self.stack = QStackedWidget()
        self.welcome = Welcome()
        self.welcome.openRequested.connect(lambda p: self.open_path(p))
        self.welcome.chooseRootRequested.connect(self.choose_root)
        self.welcome.paletteRequested.connect(self.open_palette)
        self.stack.addWidget(self.welcome)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideMiddle)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setIconSize(QSize(14, 14))
        self.tabs.currentChanged.connect(self._tab_changed)
        self.tabs.tabBar().installEventFilter(self)
        self.stack.addWidget(self.tabs)
        self.split.addWidget(self.stack)
        self.split.setStretchFactor(1, 1)
        self.split.setSizes([280, 1160])
        h.addWidget(self.split, 1)
        self.setCentralWidget(shell)

        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        self.st_left = QLabel("")
        self.st_pos = QLabel("")
        self.st_dirty = QLabel("")
        self.st_root = QLabel("")
        sb.addWidget(self.st_left)
        sb.addWidget(self.st_pos, 1)
        sb.addPermanentWidget(self.st_dirty)
        sb.addPermanentWidget(self.st_root)

        sizes = self.settings.value("split")
        if sizes:
            try:
                self.split.setSizes([int(x) for x in sizes])
            except (TypeError, ValueError):
                pass
        if not self.settings.value("sidebar", True, type=bool):
            self.act_explorer.setChecked(False)
            self.explorer.hide()

    def _action(self, menu, text, slot, shortcut=None, icon=None):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut) if isinstance(shortcut, str) else shortcut)
        if icon:
            a.setIcon(icons.icon(icon))
            a._icon_name = icon
        a.triggered.connect(slot)
        menu.addAction(a)
        self.addAction(a)
        self._commands.append((text.replace("&", "").rstrip("…").strip(), a, icon or "command"))
        return a

    def _build_menus(self):
        self._commands = []
        mb = self.menuBar()
        f = mb.addMenu("&File")
        self._action(f, "Go to File…", lambda: self.open_palette(""), "Ctrl+P", "search")
        self._action(f, "Open Data Folder…", self.choose_root, None, "folder")
        self.recent_menu = f.addMenu("Open Recent")
        self.recent_menu.aboutToShow.connect(self._fill_recent)
        f.addSeparator()
        self.a_save = self._action(f, "&Save", self.save_current, QKeySequence.StandardKey.Save, "save")
        self._action(f, "Save All", self.save_all, "Ctrl+Shift+S")
        self._action(f, "Reload From Disk", lambda: self.reload_current(), None, "refresh")
        enc = f.addMenu("Reopen With Encoding")
        for e, name, why in ENCODINGS:
            a = enc.addAction("%s   —  %s" % (name, why))
            a.triggered.connect(lambda _c=False, e=e: self.reload_current(e))
            self._commands.append(("Reopen with encoding: %s" % name, a, "globe"))
        f.addSeparator()
        self._action(f, "Close Tab", self.close_current, "Ctrl+W", "x")
        self._action(f, "Show Backups Folder", self.show_backups, None, "folder")
        f.addSeparator()
        self._action(f, "Exit", self.close, "Alt+F4")

        e = mb.addMenu("&Edit")
        self.a_undo = self.undo_group.createUndoAction(self, "Undo")
        self.a_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.a_undo.setIcon(icons.icon("undo"))
        self.a_undo._icon_name = "undo"
        self.a_redo = self.undo_group.createRedoAction(self, "Redo")
        self.a_redo.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        self.a_redo.setIcon(icons.icon("redo"))
        self.a_redo._icon_name = "redo"
        e.addAction(self.a_undo)
        e.addAction(self.a_redo)
        self._commands += [("Undo", self.a_undo, "undo"), ("Redo", self.a_redo, "redo")]
        e.addSeparator()
        self._action(e, "Filter Rows", lambda: self._with_editor(lambda ed: ed.focus_search()), "Ctrl+F", "filter")
        self._action(e, "Go to Row…", lambda: self._with_editor(lambda ed: ed.focus_search("#")), "Ctrl+G", "hash")

        v = mb.addMenu("&View")
        self._action(v, "Command Palette…", lambda: self.open_palette(">"), "Ctrl+Shift+P", "command")
        self._action(v, "Toggle Sidebar", lambda: self.act_explorer.toggle(), "Ctrl+B", "files")
        self._action(v, "Toggle Inspector", lambda: self._with_editor(lambda ed: ed.toggle_inspector()), "Ctrl+I",
                     "panel-right")
        self._action(v, "Filter Files in Explorer", self._focus_explorer, "Ctrl+Shift+E", "files")
        v.addSeparator()
        th = v.addMenu("Theme")
        self._action(th, "Dark Theme", lambda: self._apply_theme("dark"), None, "moon")
        self._action(th, "Light Theme", lambda: self._apply_theme("light"), None, "sun")
        v.addSeparator()
        self._action(v, "Next Tab", lambda: self._cycle_tab(1), "Ctrl+PgDown")
        self._action(v, "Previous Tab", lambda: self._cycle_tab(-1), "Ctrl+PgUp")

        hm = mb.addMenu("&Help")
        self._action(hm, "About Rose Dev Studio", self.about, None, "info")

    # ================================================================ startup
    def _startup(self):
        root = self.settings.value("root", "")
        if not root or not os.path.isdir(root):
            cand = REPO_ROOT / "data"
            root = str(cand) if cand.is_dir() else ""
        if root:
            self.set_root(root, restore=True)
        else:
            self._refresh_welcome()
        self._refresh_status()

    def set_root(self, root, restore=False):
        self.workspace = Workspace(root)
        self.workspace.scan()
        self.settings.setValue("root", self.workspace.root)
        self.explorer.set_workspace(self.workspace)
        self.st_root.setText("  %s  " % self.workspace.root)
        self._refresh_welcome()
        if restore:
            self._restore_session()
        self._mark_explorer()

    def rescan(self):
        if self.workspace:
            self.workspace.scan()
            self.explorer.set_workspace(self.workspace)
            self._mark_explorer()
            self._refresh_welcome()
            self.toast("Rescanned the data folder", "info",
                       "%d files" % len(self.workspace.files))

    def choose_root(self):
        start = self.workspace.root if self.workspace else str(REPO_ROOT)
        d = QFileDialog.getExistingDirectory(self, "Choose a data folder (the one holding 3DDATA)", start)
        if not d:
            return
        if any(ed.doc.dirty for ed in self.editors.values()):
            if not self._confirm_discard_all("Switching data folders closes every open file."):
                return
        while self.tabs.count():
            self._close_index(0, force=True)
        self.set_root(d)

    def _refresh_welcome(self):
        root = self.workspace.root if self.workspace else ""
        nstb = sum(1 for f in self.workspace.files if f[0] == "stb") if self.workspace else 0
        nstl = sum(1 for f in self.workspace.files if f[0] == "stl") if self.workspace else 0
        self.welcome.set_root(root, nstb, nstl)
        self.welcome.set_recent(self._recent(), root)

    # ================================================================ files
    def _recent(self):
        v = self.settings.value("recent", [])
        return [p for p in (v if isinstance(v, list) else [v]) if p]

    def _push_recent(self, path):
        r = [p for p in self._recent() if norm(p) != norm(path)]
        self.settings.setValue("recent", [path] + r[:15])

    def _fill_recent(self):
        self.recent_menu.clear()
        for p in self._recent()[:12]:
            if os.path.exists(p):
                a = self.recent_menu.addAction(os.path.basename(p))
                a.setToolTip(p)
                a.triggered.connect(lambda _c=False, p=p: self.open_path(p))
        if self.recent_menu.isEmpty():
            self.recent_menu.addAction("No recent files").setEnabled(False)

    def open_doc_for(self, path):
        ed = self.editors.get(norm(path))
        return ed.doc if ed else None

    def open_path(self, path, target=None, encoding=None, activate=True, state=None):
        key = norm(path)
        ed = self.editors.get(key)
        if ed is None:
            ext = os.path.splitext(path)[1].lower()
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                if ext not in EDITORS:
                    raise ValueError("No editor for %s files yet" % ext)
                doc_cls, ed_cls = EDITORS[ext]
                ed = ed_cls(doc_cls(path, encoding or "latin-1"), self.workspace, self.open_doc_for)
                doc = ed.doc
            except Exception as e:
                QApplication.restoreOverrideCursor()
                traceback.print_exc()
                self.toast("Could not open %s" % os.path.basename(path), "error", str(e))
                return None
            QApplication.restoreOverrideCursor()
            self._add_editor(key, ed)
            self._push_recent(doc.path)
            if state:
                ed.restore_view_state(state)
        if activate:
            self.tabs.setCurrentWidget(ed)
            self.stack.setCurrentWidget(self.tabs)
        if target:
            ed.reveal(target)
        return ed

    def _add_editor(self, key, ed, index=None):
        doc = ed.doc
        self.editors[key] = ed
        self.undo_group.addStack(doc.undo)
        t = theme.current()
        ic = icons.icon("table", t.match, active=t.match) if doc.kind == "stb" else icons.icon("text", t.success, active=t.success)
        if index is None:
            i = self.tabs.addTab(ed, ic, doc.name)
        else:
            i = self.tabs.insertTab(index, ed, ic, doc.name)
        self.tabs.setTabToolTip(i, doc.path)
        btn = widgets.TabCloseButton()
        btn.clicked.connect(lambda _c=False, ed=ed: self._close_editor(ed))
        self.tabs.tabBar().setTabButton(i, QTabBar.ButtonPosition.RightSide, btn)
        ed._close_btn = btn
        doc.dirtyChanged.connect(lambda d, ed=ed: self._dirty_changed(ed, d))
        ed.statusChanged.connect(self._refresh_status)
        ed.openRequested.connect(lambda p, tgt: self.open_path(p, tgt))
        ed.toastRequested.connect(self.toast)
        self.watcher.addPath(doc.path)
        self.stack.setCurrentWidget(self.tabs)
        self._mark_explorer()

    def _dirty_changed(self, ed, dirty):
        ed._close_btn.set_dirty(dirty)
        self._mark_explorer()
        self._refresh_status()

    def _mark_explorer(self):
        self.explorer.mark([ed.doc.path for ed in self.editors.values()],
                           [ed.doc.path for ed in self.editors.values() if ed.doc.dirty])

    def current_editor(self):
        w = self.tabs.currentWidget()
        return w if self.stack.currentWidget() is self.tabs else None

    def _with_editor(self, fn):
        ed = self.current_editor()
        if ed:
            fn(ed)

    def _tab_changed(self, i):
        ed = self.tabs.widget(i)
        if ed is None:
            self.undo_group.setActiveStack(None)
            self.stack.setCurrentWidget(self.welcome)
            self._refresh_welcome()
        else:
            self.undo_group.setActiveStack(ed.doc.undo)
            ed.activated()
            self.explorer.select_path(ed.doc.path)
            if ed.doc.changed_on_disk():
                self._disk_change(ed)
        self._refresh_status()

    def _cycle_tab(self, step):
        n = self.tabs.count()
        if n:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + step) % n)

    # ================================================================ save / close
    def save_editor(self, ed):
        try:
            backup = ed.doc.save()
        except Exception as e:
            traceback.print_exc()
            self.toast("%s was not saved" % ed.doc.name, "error", str(e))
            return False
        self.watcher.addPath(ed.doc.path)
        detail = "Original kept in build/dev-studio/backups" if backup else ""
        self.toast("Saved %s" % ed.doc.name, "success", detail)
        self.workspace and self.workspace._names.pop(ed.doc.path, None)
        return True

    def save_current(self):
        ed = self.current_editor()
        if ed:
            self.save_editor(ed)

    def save_all(self):
        n = 0
        for ed in list(self.editors.values()):
            if ed.doc.dirty:
                if not self.save_editor(ed):
                    return
                n += 1
        if not n:
            self.toast("Nothing to save", "info")

    def _ask_save(self, eds):
        names = "\n".join("  •  " + ed.doc.name for ed in eds)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(APP_NAME)
        box.setText("Save changes before closing?" if len(eds) == 1 else "%d files have unsaved changes." % len(eds))
        box.setInformativeText(names)
        save = box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton("Don't save", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        box.exec()
        c = box.clickedButton()
        if c is save:
            return all(self.save_editor(ed) for ed in eds)
        return c is discard

    def _confirm_discard_all(self, why):
        dirty = [ed for ed in self.editors.values() if ed.doc.dirty]
        if not dirty:
            return True
        return self._ask_save(dirty)

    def _close_editor(self, ed):
        i = self.tabs.indexOf(ed)
        if i >= 0:
            self._close_index(i)

    def close_current(self):
        if self.tabs.count() and self.stack.currentWidget() is self.tabs:
            self._close_index(self.tabs.currentIndex())

    def _close_index(self, i, force=False):
        ed = self.tabs.widget(i)
        if ed is None:
            return True
        if ed.doc.dirty and not force and not self._ask_save([ed]):
            return False
        self._discard_editor(ed)
        return True

    def _discard_editor(self, ed):
        i = self.tabs.indexOf(ed)
        self.tabs.removeTab(i)
        self.editors.pop(norm(ed.doc.path), None)
        self.undo_group.removeStack(ed.doc.undo)
        if ed.doc.path in self.watcher.files():
            self.watcher.removePath(ed.doc.path)
        ed.deleteLater()
        self._mark_explorer()
        if not self.tabs.count():
            self.stack.setCurrentWidget(self.welcome)
            self._refresh_welcome()
        self._refresh_status()

    # ================================================================ reload / disk changes
    def reload_current(self, encoding=None):
        ed = self.current_editor()
        if not ed:
            return
        if ed.doc.dirty:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle(APP_NAME)
            box.setText("Discard your changes to %s?" % ed.doc.name)
            box.setInformativeText("Reloading reads the file from disk again.")
            ok = box.addButton("Discard and reload", QMessageBox.ButtonRole.DestructiveRole)
            box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() is not ok:
                return
        self._reload(ed, encoding)

    def _reload(self, ed, encoding=None):
        path, i, state = ed.doc.path, self.tabs.indexOf(ed), ed.view_state()
        enc = encoding or ed.doc.encoding
        self._discard_editor(ed)
        new = self.open_path(path, encoding=enc, activate=False)
        if new is None:
            return
        j = self.tabs.indexOf(new)
        if j != i and i >= 0:
            self.tabs.tabBar().moveTab(j, min(i, self.tabs.count() - 1))
        self.tabs.setCurrentWidget(new)
        new.restore_view_state(state)
        self.toast("Reloaded %s" % new.doc.name, "info",
                   "Encoding: %s" % enc if encoding else "")

    def _file_changed(self, path):
        QTimer.singleShot(250, lambda: self._file_changed_late(path))

    def _file_changed_late(self, path):
        ed = self.editors.get(norm(path))
        if not ed:
            return
        if os.path.exists(path) and path not in self.watcher.files():
            self.watcher.addPath(path)
        if ed.doc.changed_on_disk():
            self._disk_change(ed)

    def _disk_change(self, ed):
        if not os.path.exists(ed.doc.path):
            ed.banner.show_message("%s was deleted or moved on disk. Saving will write it again." % ed.doc.name,
                                   [("Dismiss", ed.banner.hide, False)])
            return
        if not ed.doc.dirty:
            self._reload(ed)
            return
        ed.banner.show_message(
            "%s changed on disk (a script or another tool wrote it). You have unsaved changes here." % ed.doc.name,
            [("Reload from disk", lambda: self._reload(ed), True),
             ("Keep mine", lambda: (ed.doc._stat(), ed.banner.hide()), False)])

    # ================================================================ palette
    def open_palette(self, text=""):
        files = []
        if self.workspace:
            t = theme.current()
            for kind, path, rel in self.workspace.files:
                files.append({
                    "title": os.path.basename(path), "detail": os.path.dirname(rel).replace("\\", "/"),
                    "icon": "table" if kind == "stb" else "text", "tint": t.match if kind == "stb" else t.success,
                    "run": (lambda p=path: self.open_path(p)),
                })
        commands = []
        for title, action, icon in self._commands:
            if not action.isEnabled():
                continue
            sc = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
            commands.append({"title": title, "icon": icon, "shortcut": sc, "run": action.trigger})
        self.palette.open(files, commands, text)

    def _focus_explorer(self):
        if not self.explorer.isVisible():
            self.act_explorer.setChecked(True)
        self.explorer.focus_filter()

    # ================================================================ misc UI
    def toast(self, text, kind="info", detail=""):
        self.toasts.show(text, kind, detail)

    def _toggle_sidebar(self, on):
        self.explorer.setVisible(on)
        self.settings.setValue("sidebar", on)

    def _toggle_theme(self):
        self._apply_theme("light" if theme.current().dark else "dark")

    def _apply_theme(self, name, save=True):
        t = theme.apply(name)
        widgets.retint(self)
        self.act_theme._icon_name = "sun" if t.dark else "moon"
        self.act_theme.setIcon(icons.icon(self.act_theme._icon_name, size=20))
        self.act_theme.setToolTip("Switch to the %s theme" % ("light" if t.dark else "dark"))
        self.setWindowIcon(QIcon(icons.pixmap("logo", t.accent, 64)))
        for ed in self.editors.values():
            widgets.retint(ed)
        for i in range(self.tabs.count()):
            ed = self.tabs.widget(i)
            kind = ed.doc.kind
            self.tabs.setTabIcon(i, icons.icon("table", t.match, active=t.match) if kind == "stb"
                                 else icons.icon("text", t.success, active=t.success))
        self.welcome.retint()
        self.explorer.filter.retint()
        dark_title_bar(self, t.dark)
        if save:
            self.settings.setValue("theme", t.name)
        self.update()

    def _refresh_status(self):
        ed = self.current_editor()
        if ed:
            self.st_left.setText(ed.status_left())
            self.st_pos.setText(ed.status_position())
            self.setWindowTitle("%s%s — %s" % ("● " if ed.doc.dirty else "", ed.doc.name, APP_NAME))
        else:
            self.st_left.setText("Ready")
            self.st_pos.setText("")
            self.setWindowTitle(APP_NAME)
        n = sum(1 for e in self.editors.values() if e.doc.dirty)
        self.st_dirty.setText("%d unsaved" % n if n else "")
        self.a_save.setEnabled(bool(ed and ed.doc.dirty))

    def show_backups(self):
        path = BACKUP_ROOT if BACKUP_ROOT.exists() else BACKUP_ROOT.parent
        if not path.exists():
            self.toast("No backups yet", "info", "The first save of each file this session makes one.")
            return
        os.startfile(str(path))

    def about(self):
        QMessageBox.about(self, APP_NAME,
                          "<h3>%s</h3><p>STB and STL editing for Rose Next, built on "
                          "<code>scripts/rosefmt</code>: the same reader and writer the data scripts use.</p>"
                          "<p>Python %s · Qt %s</p>" % (APP_NAME, sys.version.split()[0],
                                                       __import__("PyQt6.QtCore", fromlist=["QT_VERSION_STR"]).QT_VERSION_STR))

    # ================================================================ events
    def eventFilter(self, obj, ev):
        if obj is self.tabs.tabBar() and ev.type() == ev.Type.MouseButtonRelease \
                and ev.button() == Qt.MouseButton.MiddleButton:
            i = self.tabs.tabBar().tabAt(ev.position().toPoint())
            if i >= 0:
                self._close_index(i)
            return True
        return super().eventFilter(obj, ev)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.toasts.layout()

    def showEvent(self, ev):
        super().showEvent(ev)
        dark_title_bar(self, theme.current().dark)

    def _restore_session(self):
        raw = self.settings.value("session", "")
        try:
            sess = json.loads(raw) if raw else {}
        except ValueError:
            sess = {}
        for item in sess.get("files", []):
            p = item.get("path")
            if p and os.path.exists(p) and self.workspace and norm(p).startswith(norm(self.workspace.root)):
                self.open_path(p, encoding=item.get("encoding"), activate=False, state=item.get("state"))
        cur = sess.get("current")
        if cur and norm(cur) in self.editors:
            self.tabs.setCurrentWidget(self.editors[norm(cur)])
        if self.tabs.count():
            self.stack.setCurrentWidget(self.tabs)

    def _save_session(self):
        files = []
        for i in range(self.tabs.count()):
            ed = self.tabs.widget(i)
            files.append({"path": ed.doc.path, "encoding": ed.doc.encoding, "state": ed.view_state()})
        cur = self.current_editor()
        self.settings.setValue("session", json.dumps({"files": files, "current": cur.doc.path if cur else None}))

    def closeEvent(self, ev):
        dirty = [ed for ed in self.editors.values() if ed.doc.dirty]
        if dirty and not self._ask_save(dirty):
            ev.ignore()
            return
        self._save_session()
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("split", self.split.sizes())
        ev.accept()


def main(argv=None):
    argv = argv if argv is not None else sys.argv
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("RoseNext.DevStudio")
        except Exception:
            pass
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    theme.init_fonts()
    app.setFont(theme.ui_font(9.5))
    w = MainWindow()

    def excepthook(kind, value, tb):
        # PyQt aborts the process on an exception escaping a slot unless a hook is
        # installed; an editor must never lose unsaved work to a UI bug.
        traceback.print_exception(kind, value, tb)
        try:
            w.toast("Something went wrong", "error", "%s: %s" % (kind.__name__, value))
        except Exception:
            pass

    sys.excepthook = excepthook
    w.show()
    for p in argv[1:]:
        if os.path.isfile(p):
            QTimer.singleShot(50, lambda p=p: w.open_path(p))
    return app.exec()
