"""A combat-simulator build (``scripts/combatsim/builds/*.json``) as a studio document.

The file is the ``combatsim.Build`` JSON record; the document keeps it as a plain
dict and every edit replaces the whole dict through one undo command, which is
cheap at this size and makes undo exact. Saving goes through ``Document.save``
(re-read check, one backup per session, hidden ``.tmp`` + rename).
"""
import json

from PyQt6.QtGui import QUndoCommand

from combatsim import Build

from .documents import Document


def is_build(d):
    return isinstance(d, dict) and "job" in d and "level" in d and "stats" in d


class _SetBuild(QUndoCommand):
    MERGE_ID = 0x6275    # consecutive edits with the same label merge (spin boxes)

    def __init__(self, doc, old, new, label, merge):
        super().__init__(label)
        self.doc, self.old, self.new, self.label, self.merge = doc, old, new, label, merge

    def id(self):
        return self.MERGE_ID

    def mergeWith(self, other):
        if not (self.merge and other.merge) or other.label != self.label:
            return False
        self.new = other.new
        return True

    def redo(self):
        self.doc.data = self.new

    def undo(self):
        self.doc.data = self.old


class BuildDocument(Document):
    kind = "build"
    DEFAULT_ENCODING = "utf-8"

    def __init__(self, path, encoding="utf-8"):
        with open(path, "rb") as fh:
            raw = json.loads(fh.read().decode("utf-8"))
        if not is_build(raw):
            raise ValueError("not a combat simulator build (no job/level/stats)")
        self.data = Build(raw).to_json()      # normalised: every field present
        # A build made by Tools > New Combat Build is written to disk so it can be opened
        # like any file, but it is not the user's until they save it: it counts as unsaved,
        # and "Don't save" deletes it (MainWindow.discard_provisional).
        self.provisional = False
        super().__init__(path, encoding)

    def mark_provisional(self):
        self.provisional = True
        self.dirtyChanged.emit(True)

    @property
    def dirty(self):
        return self.provisional or not self.undo.isClean()

    def _clean_changed(self, clean):
        self.dirtyChanged.emit(self.provisional or not clean)

    def build(self):
        return Build(self.data)

    def set_data(self, new, label="Edit build", merge=True):
        if new == self.data:
            return
        self.undo.push(_SetBuild(self, self.data, new, label, merge))

    def to_bytes(self):
        return (json.dumps(self.data, indent=2) + "\n").encode("utf-8")

    def verify(self, blob):
        if json.loads(blob.decode("utf-8")) != self.data:
            raise ValueError("build JSON does not round-trip")

    def _mark_saved(self):
        if self.provisional:
            self.provisional = False
            self.dirtyChanged.emit(not self.undo.isClean())
