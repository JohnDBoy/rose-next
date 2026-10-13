"""What the shell needs from any editor tab."""
from PyQt6.QtCore import QSettings, pyqtSignal
from PyQt6.QtWidgets import QApplication, QInputDialog, QWidget


class EditorBase(QWidget):
    statusChanged = pyqtSignal()
    openRequested = pyqtSignal(str, object)      # path, reveal target
    toastRequested = pyqtSignal(str, str, str)   # text, kind, detail

    def __init__(self, doc, workspace, open_doc_for=None, parent=None):
        super().__init__(parent)
        self.setObjectName("Editor")
        self.doc = doc
        self.workspace = workspace
        # path -> the open Document for it, so links read live (unsaved) data
        self.open_doc_for = open_doc_for or (lambda path: None)
        doc.contentChanged.connect(self.statusChanged.emit)

    # --- shell hooks; editors override what applies
    def status_left(self):
        return ""

    def status_position(self):
        return ""

    def reveal(self, target):
        pass

    def focus_search(self, prefix=""):
        pass

    def activated(self):
        pass

    def toggle_inspector(self):
        pass

    def view_state(self):
        return None

    def restore_view_state(self, state):
        pass

    def toast(self, text, kind="info", detail=""):
        self.toastRequested.emit(text, kind, detail)

    def ask_text(self, title, label, value=""):
        text, ok = QInputDialog.getText(self, title, label, text=value)
        return text if ok else None

    def ask_int(self, title, label, value, lo, hi):
        v, ok = QInputDialog.getInt(self, title, label, value, lo, hi)
        return v if ok else None

    @staticmethod
    def settings():
        return QSettings("RoseNext", "DevStudio")

    @staticmethod
    def clipboard_text():
        return QApplication.clipboard().text()

    @staticmethod
    def set_clipboard(text):
        QApplication.clipboard().setText(text)
