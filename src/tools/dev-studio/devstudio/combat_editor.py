"""Combat Simulator tab: edit a character build, pick a monster, see how the fight goes.

Left: the build (character, stats, equipment with refine and gem per slot, passives,
rotation, party buffs, potions). Right: the monster, the run controls and the result
of a Monte Carlo run of ``combatsim`` -- the server's formulas ported to Python. The
simulation runs in a separate worker process (``SimService``), so the window never
waits on it; with auto-run on, an edit made while a run is in flight queues one more
run and the stale answer is dropped.
"""
import json
import os
import sys

from PyQt6.QtCore import QObject, QProcess, QStringListModel, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox,
                             QCompleter, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
                             QLabel, QLineEdit, QPlainTextEdit, QPushButton, QScrollArea,
                             QSizePolicy, QSpinBox, QSplitter, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)

from combatsim import ASSUMPTIONS, GameData
from combatsim import catalog as C
from combatsim.autobuild import PROFILES, con_floor, make_build
from combatsim.data import JOBS, SHOT_BY_WEAPON
from combatsim.player import BASE_STATS, STAT_KEYS, auto_stats, total_bonus_points

from . import theme, widgets
from .documents import REPO_ROOT
from .editor_base import EditorBase

BUILDS_DIR = REPO_ROOT / "scripts" / "combatsim" / "builds"
SLOT_ORDER = [("weapon", "Weapon"), ("subwpn", "Off-hand"), ("cap", "Head"),
              ("body", "Body"), ("arms", "Gloves"), ("foot", "Boots"), ("back", "Back"),
              ("face", "Face"), ("necklace", "Necklace"), ("ring", "Ring"),
              ("earring", "Earring")]
STAT_LABELS = dict(STR="STR", DEX="DEX", INT="INT", CON="CON", CHARM="CHA", SENSE="SEN")

_GD = {}
_CAT = {}


def game_data(root):
    """One GameData (and its pick lists) per data folder, shared by every tab."""
    stb = os.path.join(root or "", "3DDATA", "STB") if root else ""
    key = root if stb and os.path.isdir(stb) else None
    if key not in _GD:
        _GD[key] = GameData(key)
    return _GD[key]


def catalog(gd, name, *args):
    k = (id(gd), name, args)
    if k not in _CAT:
        _CAT[k] = getattr(C, name)(gd, *args)
    return _CAT[k]


# ====================================================================== pickers
class Picker(QLineEdit):
    """Type to search a pick list (name + detail); Enter or a click picks a row.

    Holds a row id; an empty field means "none" (row 0) when ``allow_none``.
    """
    picked = pyqtSignal(int)

    def __init__(self, placeholder="", allow_none=True, parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.allow_none = allow_none
        self._entries, self._by_text, self._names = [], {}, {}
        self._row = 0
        self._model = QStringListModel(self)
        comp = QCompleter(self._model, self)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        comp.setMaxVisibleItems(16)
        comp.activated[str].connect(self._activated)
        comp.popup().setMinimumWidth(460)
        self.setCompleter(comp)
        self.editingFinished.connect(self._finished)

    def set_entries(self, entries):
        self._entries = entries
        texts = []
        self._by_text, self._names = {}, {}
        for row, name, detail, _lv in entries:
            t = f"{name}  —  {detail}  #{row}" if detail else f"{name}  #{row}"
            texts.append(t)
            self._by_text[t] = row
            self._names[row] = (name, detail)
        self._model.setStringList(texts)
        self.set_row(self._row)

    def row(self):
        return self._row

    def set_row(self, row):
        self._row = int(row or 0)
        name, detail = self._names.get(self._row, (f"#{self._row}" if self._row else "", ""))
        self.blockSignals(True)
        self.setText(name)
        self.blockSignals(False)
        self.setToolTip(f"{name}\n{detail}\nrow {self._row}" if self._row else "")
        self.setCursorPosition(0)

    def _activated(self, text):
        row = self._by_text.get(text)
        if row is not None:
            self._row = row
            QTimer.singleShot(0, lambda: (self.set_row(row), self.picked.emit(row)))

    def _finished(self):
        t = self.text().strip()
        if not t and self.allow_none and self._row:
            self._row = 0
            self.picked.emit(0)
            return
        if t.startswith("#") and t[1:].isdigit():
            self._row = int(t[1:])
            self.set_row(self._row)
            self.picked.emit(self._row)
            return
        self.set_row(self._row)       # typed text that matched nothing: restore


def section(title, parent_layout):
    lab = widgets.caps_label(title)
    lab.setContentsMargins(0, 14, 0, 2)
    parent_layout.addWidget(lab)


def spin(lo, hi, value=0, prefix="", suffix="", width=None):
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setValue(value)
    s.setPrefix(prefix)
    s.setSuffix(suffix)
    s.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
    s.setAlignment(Qt.AlignmentFlag.AlignRight)
    s.setKeyboardTracking(False)
    if width:
        s.setFixedWidth(width)
    return s


def combo(min_chars=10):
    """A combo whose width does not follow its longest entry (those run to 100+ chars);
    the popup is wide enough to read them."""
    c = QComboBox()
    c.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    c.setMinimumContentsLength(min_chars)
    c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    c.view().setMinimumWidth(460)
    return c


def dim(text="", obj="Dim"):
    lab = QLabel(text)
    lab.setObjectName(obj)
    if obj == "Hint":
        lab.setWordWrap(True)
    return lab


class RankCombo(QComboBox):
    """The ranks of one skill ("—" = not learned / not used)."""

    def __init__(self, gd, any_row, allow_none=True):
        super().__init__()
        self.ranks = C.skill_ranks(gd, any_row) or [any_row]
        if allow_none:
            self.addItem("—", 0)
        for r in self.ranks:
            self.addItem(f"Rank {gd.sk(r, 2)}", r)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)

    def set_row(self, row):
        i = self.findData(row)
        self.setCurrentIndex(i if i >= 0 else 0)

    def row(self):
        return self.currentData() or 0


# ====================================================================== worker
WORKER = REPO_ROOT / "scripts" / "combatsim" / "worker.py"


class SimService(QObject):
    """One simulation worker *process* per data folder, shared by every tab.

    The engine is pure Python: run on a thread it holds the GIL and the window stutters
    with every edit. A process costs nothing to the UI; requests queue in its stdin and
    results come back on stdout (scripts/combatsim/worker.py has the protocol).
    """
    result = pyqtSignal(int, object, str)      # request id, summary dict, error

    _services = {}

    @classmethod
    def get(cls, root):
        if root not in cls._services:
            cls._services[root] = cls(root)
        return cls._services[root]

    def __init__(self, root):
        super().__init__(QApplication.instance())
        self.root = root
        self.proc = None
        self._buf = b""
        self._next = 0
        self._pending = {}        # id -> request line, until answered
        self._ready = False

    def _start(self):
        p = QProcess(self)
        p.setProgram(sys.executable)
        args = [str(WORKER)]
        if self.root:
            args += ["--data", self.root]
        p.setArguments(args)
        p.readyReadStandardOutput.connect(self._read)
        p.readyReadStandardError.connect(
            lambda: sys.stderr.write(bytes(p.readAllStandardError()).decode("utf-8", "replace")))
        p.finished.connect(self._died)
        p.start()
        self.proc, self._ready, self._buf = p, False, b""
        QApplication.instance().aboutToQuit.connect(p.kill)

    def request(self, payload):
        if self.proc is None or self.proc.state() == QProcess.ProcessState.NotRunning:
            self._start()
        self._next += 1
        line = (json.dumps(dict(payload, id=self._next)) + "\n").encode("utf-8")
        self._pending[self._next] = line
        self.proc.write(line)
        return self._next

    def _read(self):
        self._buf += bytes(self.proc.readAllStandardOutput())
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            try:
                msg = json.loads(line.decode("utf-8"))
            except ValueError:
                continue
            if msg.get("ready"):
                self._ready = True
            elif "fatal" in msg:
                for rid in list(self._pending):
                    self.result.emit(rid, None, msg["fatal"])
                self._pending.clear()
            else:
                rid = msg.get("id")
                self._pending.pop(rid, None)
                self.result.emit(rid or 0, msg.get("summary"), msg.get("error", ""))

    def _died(self, *_a):
        lost = list(self._pending)
        self._pending.clear()
        self.proc = None
        for rid in lost:
            self.result.emit(rid, None, "the simulation worker stopped (see the console)")


# ====================================================================== editor
class CombatEditor(EditorBase):
    def __init__(self, doc, workspace, open_doc_for=None, parent=None):
        super().__init__(doc, workspace, open_doc_for, parent)
        root = workspace.root if workspace else None
        self.gd = game_data(root)
        self._loading = True         # widgets fire signals while they are built
        self._sig = {}
        self._req = None             # id of the request in flight
        self._again = False          # the build changed while it ran
        self._report = None          # last summary dict
        self.svc = SimService.get(self.gd.data_dir)
        self.svc.result.connect(self._sim_done)
        self._status = "ready"
        self._run_timer = QTimer(self, singleShot=True, interval=500)
        self._run_timer.timeout.connect(self.run_sim)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.addWidget(self._build_form())
        split.addWidget(self._build_results())
        split.setSizes([500, 900])
        split.setStretchFactor(1, 1)
        lay.addWidget(split)

        doc.contentChanged.connect(self._doc_changed)
        self._load_from_doc()
        self._restore_mob()
        self.queue_run(immediate=True)

    # ------------------------------------------------------------------ form
    def _build_form(self):
        outer = QFrame()
        outer.setObjectName("Inspector")
        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("InspectorBody")
        v = QVBoxLayout(body)
        v.setContentsMargins(16, 4, 16, 16)
        v.setSpacing(6)
        gd = self.gd

        # character
        section("Character", v)
        g = QGridLayout()
        g.setHorizontalSpacing(8)
        g.setVerticalSpacing(6)
        self.e_name = QLineEdit()
        self.e_name.editingFinished.connect(lambda: self._commit("Rename build"))
        self.e_job = combo(14)
        for j, n in C.jobs():
            self.e_job.addItem(f"{n}  ({j})", j)
        self.e_job.currentIndexChanged.connect(self._job_changed)
        self.e_level = spin(1, 240, 100, width=70)
        self.e_level.valueChanged.connect(lambda: self._commit("Level"))
        self.e_female = QCheckBox("Female")
        self.e_female.toggled.connect(lambda: self._commit("Gender"))
        g.addWidget(dim("Name"), 0, 0)
        g.addWidget(self.e_name, 0, 1, 1, 3)
        g.addWidget(dim("Class"), 1, 0)
        g.addWidget(self.e_job, 1, 1)
        g.addWidget(dim("Level"), 1, 2)
        g.addWidget(self.e_level, 1, 3)
        g.addWidget(self.e_female, 2, 1)
        g.setColumnStretch(1, 1)
        v.addLayout(g)
        row = QHBoxLayout()
        row.addWidget(dim("Auto-build"))
        for gear, text, tip in (
                ("average", "Average gear",
                 "What a typical player runs: older-tier median armour, current weapon (and "
                 "body/back at higher levels), low refines"),
                ("best", "Best in slot",
                 "The best item per slot at this level, well refined")):
            btn = QPushButton(text)
            btn.setToolTip(tip + ". Replaces stats, gear and passives; keeps rotation, "
                           "buffs and potions.")
            btn.clicked.connect(lambda _c=False, g=gear: self._auto_build(g))
            row.addWidget(btn, 1)
        v.addLayout(row)

        # stats
        section("Stats", v)
        g = QGridLayout()
        g.setHorizontalSpacing(8)
        self.e_stats = {}
        for i, k in enumerate(STAT_KEYS):
            s = spin(1, 300, BASE_STATS[k], width=64)
            s.valueChanged.connect(lambda _v, k=k: self._commit(f"{k}"))
            self.e_stats[k] = s
            lab = dim(STAT_LABELS[k])
            lab.setMinimumWidth(30)
            g.addWidget(lab, i // 3, (i % 3) * 2)
            g.addWidget(s, i // 3, (i % 3) * 2 + 1)
        g.setColumnStretch(6, 1)
        v.addLayout(g)
        row = QHBoxLayout()
        self.l_points = widgets.chip("")
        row.addWidget(self.l_points)
        row.addStretch(1)
        b = QPushButton("Spend by class weights")
        b.clicked.connect(self._auto_stats)
        row.addWidget(b)
        v.addLayout(row)

        # equipment
        section("Equipment", v)
        g = QGridLayout()
        g.setHorizontalSpacing(6)
        g.setVerticalSpacing(5)
        self.e_items = {}
        for i, (slot, label) in enumerate(SLOT_ORDER):
            p = Picker("none")
            p.set_entries(catalog(gd, "items", slot))
            p.picked.connect(lambda _r, s=slot: self._commit(f"{s.title()}"))
            gr = spin(0, 9, 0, prefix="+", width=40)
            gr.setToolTip("Refine grade (LIST_GRADE)")
            gr.valueChanged.connect(lambda _v, s=slot: self._commit(f"{s.title()} refine"))
            gem = Picker("gem / option")
            gem.set_entries(catalog(gd, "gems"))
            gem.setFixedWidth(104)
            p.setMinimumWidth(80)
            gem.picked.connect(lambda _r, s=slot: self._commit(f"{s.title()} gem"))
            self.e_items[slot] = (p, gr, gem)
            g.addWidget(dim(label), i, 0)
            g.addWidget(p, i, 1)
            g.addWidget(gr, i, 2)
            g.addWidget(gem, i, 3)
        g.setColumnStretch(1, 1)
        v.addLayout(g)
        row = QHBoxLayout()
        self.l_ammo = dim("Ammo")
        self.e_ammo = Picker("needed by bows, guns and launchers")
        self.e_ammo.picked.connect(lambda _r: self._commit("Ammo"))
        row.addWidget(self.l_ammo)
        row.addWidget(self.e_ammo, 1)
        v.addLayout(row)

        # passives
        section("Passive skills", v)
        self.passive_box = QGridLayout()
        self.passive_box.setHorizontalSpacing(8)
        self.passive_box.setVerticalSpacing(4)
        v.addLayout(self.passive_box)
        self.passive_rows = {}

        # rotation
        section("Rotation (priority order)", v)
        v.addWidget(dim("Damage skills and debuffs, cast whenever off cooldown and affordable; "
                        "a debuff is recast when it drops.", "Hint"))
        self.rot_box = QVBoxLayout()
        self.rot_box.setSpacing(4)
        v.addLayout(self.rot_box)
        self.rot_add = combo()
        self.rot_add.activated.connect(self._rot_add)
        v.addWidget(self.rot_add)

        # buffs
        section("Buffs kept up", v)
        v.addWidget(dim("Self and party buffs (Cleric buffs left out). Caster INT 0 = "
                        "this character's INT.", "Hint"))
        self.buff_box = QVBoxLayout()
        self.buff_box.setSpacing(4)
        v.addLayout(self.buff_box)
        self.buff_add = combo()
        self.buff_add.addItem("Add a buff…", 0)
        for r, name, detail, _ in catalog(gd, "buff_skills"):
            self.buff_add.addItem(f"{name}  —  {detail}", r)
        self.buff_add.activated.connect(self._buff_add)
        v.addWidget(self.buff_add)

        # potions
        section("Potions", v)
        self.e_pot_on = QCheckBox("Drink potions (off by default: vials skew balance)")
        self.e_pot_on.toggled.connect(lambda: self._commit("Potions"))
        v.addWidget(self.e_pot_on)
        g = QGridLayout()
        g.setHorizontalSpacing(6)
        self.e_pot = {}
        for i, kind in enumerate(("hp", "mp")):
            cb = combo()
            cb.addItem("none", 0)
            for r, name, how, _ in catalog(gd, "potions", kind):
                cb.addItem(f"{name}  —  {how}", r)
            cb.currentIndexChanged.connect(lambda _i: self._commit("Potion"))
            th = spin(1, 99, 50, prefix="below ", suffix=" %", width=96)
            th.valueChanged.connect(lambda _v: self._commit("Potion threshold"))
            self.e_pot[kind] = (cb, th)
            g.addWidget(dim(kind.upper()), i, 0)
            g.addWidget(cb, i, 1)
            g.addWidget(th, i, 2)
        g.setColumnStretch(1, 1)
        v.addLayout(g)

        section("Notes", v)
        self.e_notes = QPlainTextEdit()
        self.e_notes.setFixedHeight(70)
        self.e_notes.textChanged.connect(lambda: self._commit("Notes"))
        v.addWidget(self.e_notes)
        v.addStretch(1)

        scroll.setWidget(body)
        ol.addWidget(scroll)
        outer.setMinimumWidth(430)
        return outer

    # ------------------------------------------------------------------ results
    def _build_results(self):
        w = QWidget()
        w.setObjectName("Editor")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        bar = QFrame()
        bar.setObjectName("EditorToolbar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(12, 6, 12, 6)
        bl.setSpacing(8)
        bl.addWidget(dim("Monster"))
        self.e_mob = Picker("search a monster by name or #row", allow_none=False)
        self.e_mob.set_entries(catalog(self.gd, "monsters"))
        self.e_mob.picked.connect(self._mob_changed)
        bl.addWidget(self.e_mob, 1)
        bl.addWidget(dim("Fights"))
        self.e_n = spin(20, 5000, 300, width=60)
        self.e_n.setToolTip("Monte Carlo fights per run (a survival run of a third as many "
                            "is added: fresh copies of the monster back to back)")
        self.e_n.valueChanged.connect(lambda: self.queue_run())
        bl.addWidget(self.e_n)
        self.e_fix = QCheckBox("Fix passive bugs")
        self.e_fix.setToolTip("Show what the passives were meant to give: the server loses "
                              "% STR..SEN passives at login (no skill uses one today)")
        self.e_fix.toggled.connect(lambda: self.queue_run(immediate=True))
        bl.addWidget(self.e_fix)
        self.e_auto = QCheckBox("Auto-run")
        self.e_auto.setToolTip("Re-run after every edit (off: press Run)")
        self.e_auto.setChecked(False)
        self.e_auto.toggled.connect(lambda on: on and self.queue_run(immediate=True))
        bl.addWidget(self.e_auto)
        self.b_run = QPushButton("Run")
        self.b_run.setObjectName("Primary")
        self.b_run.clicked.connect(lambda: self.queue_run(immediate=True, force=True))
        bl.addWidget(self.b_run)
        b = widgets.tool_button("copy", "Copy the report as text", self._copy_report)
        bl.addWidget(b)
        lay.addWidget(bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body.setObjectName("Editor")
        self.res = QVBoxLayout(body)
        self.res.setContentsMargins(18, 14, 18, 18)
        self.res.setSpacing(10)

        self.l_title = QLabel()
        self.l_title.setFont(theme.ui_font(12, QFont.Weight.DemiBold))
        self.res.addWidget(self.l_title)
        self.l_state = dim("")
        self.res.addWidget(self.l_state)

        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.cards = {}
        tips = dict(
            win="Share of fights the player wins (monster dead before the player)",
            ttk="Seconds to kill the monster, median of the fights won",
            surv="How long the player lasts fighting fresh copies of this monster back to "
                 "back (each one replaced the moment it dies), with the same rotation, regen "
                 "and potions",
            hp="HP left at the end of a won fight (median)",
            mp="MP left at the end of a won fight (median)")
        for key, title in (("win", "Wins"), ("ttk", "Time to kill"), ("surv", "Survives"),
                           ("hp", "HP left"), ("mp", "MP left")):
            c = QFrame()
            c.setObjectName("Card")
            c.setToolTip(tips[key])
            cl = QVBoxLayout(c)
            cl.setContentsMargins(14, 10, 14, 10)
            cl.setSpacing(2)
            cl.addWidget(widgets.caps_label(title))
            big = QLabel("—")
            big.setFont(theme.ui_font(17, QFont.Weight.DemiBold))
            sub = dim("")
            sub.setWordWrap(True)
            cl.addWidget(big)
            cl.addWidget(sub)
            self.cards[key] = (big, sub)
            cards.addWidget(c, 1)
        self.res.addLayout(cards)

        rates = QHBoxLayout()
        rates.setSpacing(10)
        self.rate_cards = {}
        for key, title in (("dps", "Damage dealt / s"), ("dtps", "Damage taken / s"),
                           ("mps", "MP / s")):
            c = QFrame()
            c.setObjectName("Card")
            cl = QVBoxLayout(c)
            cl.setContentsMargins(14, 10, 14, 10)
            cl.setSpacing(2)
            cl.addWidget(widgets.caps_label(title))
            big = QLabel("—")
            big.setFont(theme.ui_font(14, QFont.Weight.DemiBold))
            sub = dim("")
            sub.setWordWrap(True)
            cl.addWidget(big)
            cl.addWidget(sub)
            self.rate_cards[key] = (big, sub)
            rates.addWidget(c, 1)
        self.res.addLayout(rates)

        section("Stat blocks (what the formulas read)", self.res)
        self.t_stats = self._table(["", "HP", "MP", "ATK", "HIT", "DEF", "RES", "AVOID",
                                    "CRIT", "ASPD", "Swing"])
        self.res.addWidget(self.t_stats)
        self.l_buffs = dim("")
        self.l_buffs.setWordWrap(True)
        self.res.addWidget(self.l_buffs)

        section("Player damage", self.res)
        self.t_dmg = self._table(["Attack", "Per fight", "Lands", "Crit", "Per hit",
                                  "DPS", "MP", "Cooldown", "Debuff lands"])
        self.res.addWidget(self.t_dmg)
        self.l_debuffs = dim("")
        self.l_debuffs.setWordWrap(True)
        self.res.addWidget(self.l_debuffs)

        section("Monster damage", self.res)
        self.t_mdmg = self._table(["Attack", "Per fight", "Lands", "Crit", "Per hit", "DPS",
                                   "State lands", "Then"])
        self.res.addWidget(self.t_mdmg)
        self.l_monster = QLabel()
        self.l_monster.setWordWrap(True)
        self.res.addWidget(self.l_monster)

        self.warn_head = widgets.caps_label("Warnings")
        self.warn_head.setContentsMargins(0, 14, 0, 2)
        self.res.addWidget(self.warn_head)
        self.l_warn = QLabel()
        self.l_warn.setObjectName("Error")
        self.l_warn.setWordWrap(True)
        self.res.addWidget(self.l_warn)

        section("Assumptions", self.res)
        lab = dim("\n".join("•  " + a for a in ASSUMPTIONS), "Faint")
        lab.setWordWrap(True)
        self.res.addWidget(lab)
        self.res.addStretch(1)
        scroll.setWidget(body)
        lay.addWidget(scroll, 1)
        return w

    def _table(self, headers):
        t = QTableWidget(0, len(headers))
        t.setObjectName("SimTable")
        t.setHorizontalHeaderLabels(headers)
        t.verticalHeader().hide()
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        t.setShowGrid(False)
        t.setAlternatingRowColors(True)
        h = t.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        h.setStretchLastSection(True)
        h.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        t.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        t.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return t

    @staticmethod
    def _fill(t, rows):
        t.setRowCount(len(rows))
        for r, vals in enumerate(rows):
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                if c:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                t.setItem(r, c, it)
        t.resizeColumnsToContents()
        h = t.horizontalHeader().height() + sum(t.rowHeight(i) for i in range(len(rows)))
        t.setFixedHeight(h + 4 + (t.horizontalScrollBar().height()
                                  if t.horizontalScrollBar().isVisible() else 0))

    # ------------------------------------------------------------------ doc <-> widgets
    def _load_from_doc(self):
        self._loading = True
        try:
            b = self.doc.build()
            gd = self.gd
            self.e_name.setText(b.name)
            i = self.e_job.findData(b.job)
            self.e_job.setCurrentIndex(i if i >= 0 else 0)
            self.e_level.setValue(b.level)
            self.e_female.setChecked(b.female)
            for k, s in self.e_stats.items():
                s.setValue(b.stats[k])
            for slot, (p, gr, gem) in self.e_items.items():
                it = b.equip[slot]
                p.set_row(it.id)
                gr.setValue(it.grade)
                gem.set_row(it.gem)
            wid = b.equip["weapon"].id
            shot = SHOT_BY_WEAPON.get(gd.weapon_type(wid)) if wid else None
            self.e_ammo.set_entries(catalog(gd, "ammo", shot) if shot is not None else [])
            self.e_ammo.set_row(b.ammo)
            self.e_ammo.setEnabled(shot is not None)
            self.l_ammo.setEnabled(shot is not None)
            self._fill_passives(b)
            self._fill_rotation(b)
            self._fill_buffs(b)
            self.e_pot_on.setChecked(b.potions["enabled"])
            for kind, (cb, th) in self.e_pot.items():
                i = cb.findData(b.potions[kind])
                cb.setCurrentIndex(i if i >= 0 else 0)
                th.setValue(b.potions[kind + "_below"])
            if self.e_notes.toPlainText() != b.notes:
                self.e_notes.setPlainText(b.notes)
            self._update_points(b)
        finally:
            self._loading = False

    def _gather(self):
        b = self.doc.build()
        b.name = self.e_name.text().strip() or b.name
        b.job = self.e_job.currentData()
        b.level = self.e_level.value()
        b.female = self.e_female.isChecked()
        for k, s in self.e_stats.items():
            b.stats[k] = s.value()
        for slot, (p, gr, gem) in self.e_items.items():
            it = b.equip[slot]
            it.id, it.grade, it.gem = p.row(), gr.value(), gem.row()
        b.ammo = self.e_ammo.row() if self.e_ammo.isEnabled() else 0
        b.skills = [rc.row() for rc in self.passive_rows.values() if rc.row()]
        b.skills += [r for r in self.doc.build().skills if r not in self._class_passive_rows]
        b.rotation = [w.rank.row() for w in self._rot_widgets if w.rank.row()]
        b.buffs = [dict(skill=w.rank.row(), caster_int=w.cint.value(), caster_level=0)
                   for w in self._buff_widgets if w.rank.row()]
        b.potions["enabled"] = self.e_pot_on.isChecked()
        for kind, (cb, th) in self.e_pot.items():
            b.potions[kind] = cb.currentData() or 0
            b.potions[kind + "_below"] = th.value()
        b.notes = self.e_notes.toPlainText()
        return b

    def _commit(self, label):
        if self._loading:
            return
        b = self._gather()
        self.doc.set_data(b.to_json(), label)

    def _doc_changed(self):
        if not self._loading:
            # undo/redo or our own commit: re-sync dependent widgets, then re-run
            self._load_from_doc()
        self.queue_run()
        self.statusChanged.emit()

    def _update_points(self, b):
        spent, have = b.points_spent(), total_bonus_points(b.level)
        self.l_points.setText(f"Bonus points {spent:,} / {have:,}")
        over = spent > have
        self.l_points.setObjectName("ChipModified" if over else "Chip")
        self.l_points.setToolTip("Stats cost more points than the level grants" if over else
                                 f"{have - spent:,} unspent")
        self.l_points.style().unpolish(self.l_points)
        self.l_points.style().polish(self.l_points)

    # ------------------------------------------------------------------ passives
    def _unchanged(self, key, sig):
        """True when a list's data is what its widgets already show (no rebuild)."""
        if self._sig.get(key) == sig:
            return True
        self._sig[key] = sig
        return False

    def _fill_passives(self, b):
        if self._unchanged("passives", (b.job, tuple(b.skills))):
            return
        widgets.clear_layout(self.passive_box)
        self.passive_rows = {}
        passives, _ = catalog(self.gd, "class_skill_lists", b.job)
        self._class_passive_rows = set()
        learned = set(b.skills)
        for i, (row, name, detail, _) in enumerate(passives):
            rc = RankCombo(self.gd, row)
            self._class_passive_rows.update(rc.ranks)
            have = next((r for r in rc.ranks if r in learned), 0)
            rc.set_row(have)
            rc.currentIndexChanged.connect(lambda _i, n=name: self._commit(f"{n}"))
            lab = QLabel(name)
            lab.setToolTip(detail)
            self.passive_box.addWidget(lab, i, 0)
            self.passive_box.addWidget(rc, i, 1)
            self.passive_rows[row] = rc
        self.passive_box.setColumnStretch(0, 1)
        if not passives:
            self.passive_box.addWidget(dim("This class has no passive skills.", "Hint"), 0, 0)

    # ------------------------------------------------------------------ rotation
    def _row_widget(self, gd, row, extra=None, on_change=None, on_remove=None, on_move=None):
        w = QFrame()
        w.setObjectName("Card")
        h = QHBoxLayout(w)
        h.setContentsMargins(8, 4, 4, 4)
        h.setSpacing(6)
        lab = QLabel(gd.name("LIST_SKILL", row))
        h.addWidget(lab, 1)
        w.rank = RankCombo(gd, row, allow_none=False)
        w.rank.set_row(row)
        w.rank.currentIndexChanged.connect(on_change)
        h.addWidget(w.rank)
        if extra:
            h.addWidget(extra)
        if on_move:
            h.addWidget(widgets.tool_button("chevron-up", "Higher priority", lambda: on_move(w, -1), size=14))
            h.addWidget(widgets.tool_button("chevron-down", "Lower priority", lambda: on_move(w, 1), size=14))
        h.addWidget(widgets.tool_button("x", "Remove", lambda: on_remove(w), size=14))
        return w

    def _fill_rotation(self, b):
        if self._unchanged("rotation", (b.job, tuple(b.rotation))):
            return
        gd = self.gd
        widgets.clear_layout(self.rot_box)
        self._rot_widgets = []
        for row in b.rotation:
            w = self._row_widget(gd, row, on_change=lambda _i: self._commit("Rotation rank"),
                                 on_remove=self._rot_remove, on_move=self._rot_move)
            w.setToolTip(next((d for r, _, d, _ in catalog(gd, "class_skill_lists", b.job)[1]
                               if r in w.rank.ranks), ""))
            self.rot_box.addWidget(w)
            self._rot_widgets.append(w)
        self.rot_add.blockSignals(True)
        self.rot_add.clear()
        self.rot_add.addItem("Add a skill to the rotation…", 0)
        for r, name, detail, _ in catalog(gd, "class_skill_lists", b.job)[1]:
            self.rot_add.addItem(f"{name}  —  {detail}", r)
        self.rot_add.blockSignals(False)

    def _rot_add(self, i):
        row = self.rot_add.itemData(i)
        self.rot_add.setCurrentIndex(0)
        if not row:
            return
        b = self._gather()
        b.rotation.append(row)
        self.doc.set_data(b.to_json(), "Add to rotation", merge=False)

    def _rot_remove(self, w):
        b = self._gather()
        i = self._rot_widgets.index(w)
        del b.rotation[i]
        self.doc.set_data(b.to_json(), "Remove from rotation", merge=False)

    def _rot_move(self, w, step):
        b = self._gather()
        i = self._rot_widgets.index(w)
        j = i + step
        if 0 <= j < len(b.rotation):
            b.rotation[i], b.rotation[j] = b.rotation[j], b.rotation[i]
            self.doc.set_data(b.to_json(), "Reorder rotation", merge=False)

    # ------------------------------------------------------------------ buffs
    def _fill_buffs(self, b):
        if self._unchanged("buffs", tuple((x["skill"], x["caster_int"]) for x in b.buffs)):
            return
        gd = self.gd
        widgets.clear_layout(self.buff_box)
        self._buff_widgets = []
        for buff in b.buffs:
            cint = spin(0, 999, buff["caster_int"], prefix="INT ", width=74)
            cint.setToolTip("Caster INT (0 = this character's): flat buff values scale "
                            "by (INT + 300) / 315")
            cint.valueChanged.connect(lambda _v: self._commit("Buff caster INT"))
            w = self._row_widget(gd, buff["skill"], extra=cint,
                                 on_change=lambda _i: self._commit("Buff rank"),
                                 on_remove=self._buff_remove)
            w.cint = cint
            self.buff_box.addWidget(w)
            self._buff_widgets.append(w)

    def _buff_add(self, i):
        row = self.buff_add.itemData(i)
        self.buff_add.setCurrentIndex(0)
        if not row:
            return
        b = self._gather()
        b.buffs.append(dict(skill=row, caster_int=0, caster_level=0))
        self.doc.set_data(b.to_json(), "Add buff", merge=False)

    def _buff_remove(self, w):
        b = self._gather()
        del b.buffs[self._buff_widgets.index(w)]
        self.doc.set_data(b.to_json(), "Remove buff", merge=False)

    # ------------------------------------------------------------------ class / auto
    def _job_changed(self):
        if self._loading:
            return
        b = self._gather()
        # passives and rotation belong to the old class
        b.skills, b.rotation = [], []
        self.doc.set_data(b.to_json(), "Class", merge=False)

    def _auto_build(self, gear="average"):
        b = self._gather()
        nb = make_build(self.gd, b.job, b.level, b.female, gear)
        nb.name = b.name
        nb.buffs, nb.potions, nb.rotation = b.buffs, b.potions, b.rotation
        self.doc.set_data(nb.to_json(), f"Auto-build ({gear})", merge=False)

    def _auto_stats(self):
        b = self._gather()
        b.stats = auto_stats(b.level, PROFILES.get(b.job, PROFILES[111])["w"], con_floor(b.job))
        self.doc.set_data(b.to_json(), "Spend stat points", merge=False)

    # ------------------------------------------------------------------ monster / running
    def _restore_mob(self):
        mob = int(self.settings().value("combat/mob/" + self.doc.path, 0) or 0)
        if not mob:
            mob = int(self.settings().value("combat/last_mob", 0) or 0)
        if not mob:
            lv = self.doc.build().level
            near = [e for e in catalog(self.gd, "monsters") if abs(e[3] - lv) <= 2]
            mob = near[len(near) // 2][0] if near else 1
        self.e_mob.set_row(mob)

    def _mob_changed(self, row):
        self.settings().setValue("combat/mob/" + self.doc.path, row)
        self.settings().setValue("combat/last_mob", row)
        self.queue_run(immediate=True)

    def queue_run(self, immediate=False, force=False):
        if not force and not self.e_auto.isChecked():
            self._status = "out of date — press Run" if self._report else "press Run"
            self.l_state.setText("Results are out of date — press Run." if self._report
                                 else "Pick a monster and press Run.")
            self.statusChanged.emit()
            return
        self._run_timer.start(0 if immediate else 250)

    def run_sim(self):
        mob = self.e_mob.row()
        if not mob:
            return
        if self._req is not None:
            self._again = True               # one run in flight per tab; rerun after it
            return
        self._again = False
        self._status = "running…"
        self.l_state.setText(f"Running {self.e_n.value()} fights…")
        self.statusChanged.emit()
        self._req = self.svc.request(dict(build=self.doc.data, mob=mob, n=self.e_n.value(),
                                          fix=self.e_fix.isChecked()))

    def _sim_done(self, rid, summary, err):
        if rid != self._req:
            return                           # another tab's answer
        self._req = None
        if self._again:
            self.run_sim()                   # the build moved on: this answer is stale
            return
        if err:
            self._status = "error"
            self.l_state.setText(f"Simulation failed: {err}")
            self.statusChanged.emit()
            return
        self._report = summary
        self._status = "ready"
        self._show(summary)
        self.statusChanged.emit()

    # ------------------------------------------------------------------ results view
    def _show(self, r):
        t = theme.current()
        self.l_title.setText(f"{r['build']}  vs  {r['npc']}  (Lv {r['npc_level']})")
        srv = r["server"]
        self.l_state.setText(f"{r['n']} fights + {r['surv_n']} survival runs · {r['job']} "
                             f"{r['level']} · server.toml adds ATK +{srv['atk']}, HIT "
                             f"+{srv['hit']}, ASPD +{srv['aspd']}")

        def card(key, big, sub, color=None):
            lb, ls = self.cards[key]
            lb.setText(big)
            lb.setStyleSheet(f"color: {color};" if color else "")
            ls.setText(sub)

        win = r["win_rate"]
        win_col = t.success if win >= .95 else t.danger if win < .5 else t.modified
        card("win", f"{win:.0%}", f"{r['timeouts']} timeouts" if r["timeouts"] else
             f"of {r['n']} fights", win_col)
        ttk = r["ttk"]
        if ttk:
            card("ttk", f"{ttk['median']:.1f} s", f"p10 {ttk['p10']:.1f} · p90 {ttk['p90']:.1f} s")
            hp, mp = r["hp_left"], r["mp_left"]
            card("hp", f"{hp / max(1, r['max_hp']):.0%}",
                 f"{hp:,.0f} / {r['max_hp']:,} (median win)")
            card("mp", f"{mp / max(1, r['max_mp']):.0%}", f"{mp:,.0f} / {r['max_mp']:,}")
        else:
            card("ttk", "—", "never kills it", t.danger)
            card("hp", "—", "")
            card("mp", "—", "")
        sv = r["surv"]
        if r["surv_never"] * 2 > r["surv_n"]:
            card("surv", "never dies", "regen or potions outpace its damage", t.success)
        elif sv:
            proj = " (projected)" if r["surv_projected"] else ""
            card("surv", f"{sv['median']:.0f} s",
                 f"p10 {sv['p10']:.0f} · p90 {sv['p90']:.0f} s{proj}")

        def rate(key, big, sub):
            lb, ls = self.rate_cards[key]
            lb.setText(big)
            ls.setText(sub)

        rate("dps", f"{r['dps']:,.0f}",
             f"normal {r['dps_auto']:,.0f} · skills {r['dps_skill']:,.0f}")
        heal = r["regen_hps"] + r["potion_hps"]
        rate("dtps", f"{r['dtps']:,.0f}",
             (f"normal {r['dtps_auto']:,.0f} · skills {r['dtps_skill']:,.0f} · "
              if r["dtps_skill"] else "")
             + f"healing {heal:,.1f}/s (regen {r['regen_hps']:.1f}"
             + (f", potions {r['potion_hps']:.1f})" if r["potions_on"] else ")"))
        oom = f" · out of skill MP at {r['oom']:.0f} s" if r["oom"] else ""
        rate("mps", f"{r['mp_per_s']:,.1f}", f"regen {r['regen_mps']:.1f}/s{oom}")

        def stat_row(label, u, mp=True):
            return [label, f"{u['hp']:,}", f"{u['mp']:,}" if mp else "—", u["atk"], u["hit"],
                    u["df"], u["res"], u["avoid"], u["crit"], u["aspd"],
                    f"{u['swing_ms']} ms" if u["swing_ms"] else "—"]

        self._fill(self.t_stats, [stat_row("Player", r["player"]),
                                  stat_row("Monster", r["monster"], mp=False)])
        buffs = r["buffs"]
        self.l_buffs.setText(("Buffs: " + ", ".join(f"{n} {v:+d} ({sk})" for n, v, sk in buffs))
                             if buffs else "")
        self.l_buffs.setVisible(bool(buffs))

        nm = r["normal"]
        rows = [["Normal attack", f"{nm['per_fight']:.1f}", f"{nm['land']:.0%}",
                 f"{nm['crit']:.0%}", f"{nm['per_hit']:,.0f}", f"{nm['dps']:,.0f}", "", "", ""]]
        for sk in r["skills"]:
            dmg = sk["damage"]
            rows.append([
                f"{sk['name']} (rank {sk['rank']})", f"{sk['casts']:.1f}",
                f"{sk['land']:.0%}" if dmg and sk["casts"] else "", "",
                f"{sk['per_hit']:,.0f}" if dmg else "", f"{sk['dps']:,.0f}" if dmg else "",
                sk["mp"], f"{sk['cooldown']:.1f} s",
                f"{sk['state_land']:.0%}" if sk["state_land"] is not None else ""])
        self._fill(self.t_dmg, rows)
        up = r["debuffs"]
        self.l_debuffs.setText(("Debuff uptime on the monster: "
                                + ", ".join(f"{k} {v:.0%}" for k, v in up)) if up else "")
        self.l_debuffs.setVisible(bool(up))
        mrows = [["Normal attack", f"{r['monster_swings']:.1f}", f"{r['m_land']:.0%}",
                  f"{r['m_crit']:.0%}", f"{r['m_hit_dmg']:,.0f}", f"{r['dtps_auto']:,.0f}",
                  "", ""]]
        for sk in r["m_skills"]:
            dmg = sk["damage"]
            mrows.append([
                f"{sk['name']} (#{sk['row']})", f"{sk['casts']:.1f}",
                f"{sk['land']:.0%}" if sk["land"] is not None else "", "",
                f"{sk['per_hit']:,.0f}" if dmg else "", f"{sk['dps']:,.0f}" if dmg else "",
                f"{sk['state_land']:.0%}" if sk["state_land"] is not None else "",
                {1: "attacks", 2: "resumes"}.get(sk["mode"], "stops")])
        self._fill(self.t_mdmg, mrows)
        parts = [f"{r['dtps']:,.0f} damage per second"]
        if r["monster_disabled"]:
            parts.append(f"stunned or asleep {r['monster_disabled']:.0%} of the fight")
        if r["monster_idle"] > 0.005:
            parts.append(f"stands idle (no target) {r['monster_idle']:.0%}")
        if r["monster_buffs"]:
            parts.append("its buffs: " + ", ".join(f"{k} {v:.0%}" for k, v in r["monster_buffs"]))
        if r["player_states"]:
            parts.append("on the player: " + ", ".join(
                f"{k} {v:.0%}" for k, v in r["player_states"]))
        ai = r["ai"]
        if ai:
            parts.append(f"AI {ai['file']}: damaged pattern {ai['damaged_runs']:.1f} runs/fight "
                         f"(gate {ai['damaged_rate']}%)")
            if ai["unsimulated"]:
                parts.append("not simulated: " + ", ".join(
                    f"{k} {v:.1f}/fight" for k, v in ai["unsimulated"]))
        else:
            parts.append("no AI file")
        pots = r["potions"]
        if r["potions_on"]:
            parts.append(f"potions per fight: HP {pots['hp']:.1f}, MP {pots['mp']:.1f}")
        self.l_monster.setText(" · ".join(parts))
        notes = r["notes"]
        self.l_warn.setText("\n".join("•  " + n for n in notes))
        self.l_warn.setVisible(bool(notes))
        self.warn_head.setVisible(bool(notes))

    def _copy_report(self):
        if self._report:
            self.set_clipboard(self._report["text"])
            self.toast("Report copied", "success")

    # ------------------------------------------------------------------ shell hooks
    def status_left(self):
        return f"Combat simulator · {self._status}"

    def view_state(self):
        return {"mob": self.e_mob.row(), "n": self.e_n.value(), "fix": self.e_fix.isChecked(),
                "auto": self.e_auto.isChecked()}

    def restore_view_state(self, state):
        if not state:
            return
        if state.get("mob"):
            self.e_mob.set_row(state["mob"])
        self.e_n.setValue(state.get("n", 300))
        self.e_fix.setChecked(bool(state.get("fix")))
        self.e_auto.setChecked(state.get("auto", False))
        self.queue_run(immediate=True)

    def focus_search(self, prefix=""):
        self.e_mob.setFocus()
        self.e_mob.selectAll()


def new_build_file(gd, job, level, female=False, gear="average"):
    """Write an auto build under scripts/combatsim/builds/ and return its path."""
    BUILDS_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{JOBS.get(job, job).lower()}-{level}"
    path = BUILDS_DIR / f"{stem}.json"
    n = 2
    while path.exists():
        path = BUILDS_DIR / f"{stem}-{n}.json"
        n += 1
    b = make_build(gd, job, level, female, gear)
    b.name = f"{JOBS.get(job, job)} {level}"
    b.save(str(path))
    return str(path)


__all__ = ["CombatEditor", "BUILDS_DIR", "new_build_file", "game_data"]
