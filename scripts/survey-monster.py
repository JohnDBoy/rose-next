#!/usr/bin/env python3
"""Survey one monster of a reference dump before importing it (doc/importing-monsters.md, step 1).

    python scripts/survey-monster.py C:\\Users\\Thomas\\Desktop\\Testclients\\Jrose 2290
    python scripts/survey-monster.py <dump> <row> --profile      # per-frame motion bars
    python scripts/survey-monster.py <dump> <row> --ours <data>

Read-only. Everything it prints was dug out by hand for the Shadow Soldier
(import-shadow-soldier.py, 2026-10-27), most of a session's first hour:

  * **The row**: name (decoded and glossed), model, speeds, size, hands, level, AI row,
    mark, glow, and the neighbouring rows of the source (siblings: the Shadow Soldier
    came with a Shadow Muse, Hawker and Dealer).
  * **Where it can land here**: whether our row of the same number is free (no name
    **and** no CHR entry), else the nearest free runs; and any CHR entry of ours that
    already has the same model meshes (we may own the monster under another number).
  * **The CHR entry**: skeleton, each model part's mesh and texture with whether we ship
    the file, and every anim slot: the clip, ours / new, frames, events, and **which skill
    uses that clip** -- the clip's FILE_MOTION row -> the TYPE_MOTION rows pointing at it
    -> the LIST_SKILL rows whose cast (col 52) or action (col 68) is that row, ours first,
    then the source's. That is how slots 6-9 turned out to be Impact Wave and Lightning
    Crasher. Slots from 6 up are read as cast/release pairs (a monster casts on
    `nMotion` and releases on `nMotion + 1`), with what the release clip can present:
    projectile (24/34/26), strike (25/35/10/20), the server's attack-frame count, or
    nothing at all.
  * **Motion profiles** of the skill clips: summed bone rotation per frame (degrees), which
    is how a wind-up is told from a blow when choosing where to split a clip, and the
    loop seam of a cast clip (last frame vs first: near 0 means it loops cleanly, so it
    can be repeated with rosefmt.zmo.joined). `--profile` draws them as bars.
  * **The weapon** (col 5, LIST_WEAPON + LIST_WEAPON.ZSC) and left hand (col 6,
    LIST_SUBWPN.ZSC): name, type, level requirement, mesh and texture, and our rows on the
    same mesh -- "same mesh, same texture" means we have it; "same mesh, other texture"
    is a new item on art we already ship.
  * **The source AI**, if the dump ships the file (Jrose ships ~1,200; tsuki none): every
    cast (skill, motion) with what that skill id is in the source and here -- a skill id is
    the source's numbering, and the same id here is often another skill.

Encoding: the dump's names are decoded by sniffing LIST_NPC's lead bytes (cp932 kana vs
EUC-KR Hangul, the rule gm-item-browser's src/text.rs uses); `--enc` overrides it.
"""
import argparse
import math
import os
import struct
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from rosefmt import Chr, Stb, Stl, Zsc, aip  # noqa: E402
from rosefmt import zmo as rz  # noqa: E402

NPC_STB = r"3DDATA\STB\LIST_NPC.STB"
NPC_STL = r"3DDATA\STB\LIST_NPC_S.STL"
NPC_CHR = r"3DDATA\NPC\LIST_NPC.CHR"
PART_ZSC = r"3DDATA\NPC\PART_NPC.ZSC"
WEAPON_STB = r"3DDATA\STB\LIST_WEAPON.STB"
WEAPON_STL = r"3DDATA\STB\LIST_WEAPON_S.STL"
WEAPON_ZSC = r"3DDATA\WEAPON\LIST_WEAPON.ZSC"
SUBWPN_ZSC = r"3DDATA\WEAPON\LIST_SUBWPN.ZSC"
SKILL_STB = r"3DDATA\STB\LIST_SKILL.STB"
SKILL_STL = r"3DDATA\STB\LIST_SKILL_S.STL"
FILE_MOTION = r"3DDATA\STB\FILE_MOTION.STB"
TYPE_MOTION = r"3DDATA\STB\TYPE_MOTION.STB"
FILE_AI = r"3DDATA\STB\FILE_AI.STB"

C_NAME, C_MODEL, C_WALK, C_RUN, C_SIZE, C_RWEAPON, C_LWEAPON, C_LEVEL, C_HP, C_ATK = range(10)
C_AI, C_MARK, C_GLOW, C_STRID, C_HEIGHT = 16, 27, 39, 40, 42
SK_TYPE, SK_SCOPE, SK_POWER, SK_CAST, SK_ACTION = 5, 8, 9, 52, 68

PROJECTILE, STRIKE = {24, 34, 26}, {25, 35, 10, 20}
SERVER_ATTACK = {21, 22, 23, 24, 25, 26, 27, 10, 20, 56, 66, 57, 67}   # io_motion.cpp
CASTING_FX = {44: 0, 64: 1, 74: 2, 84: 3}
AI_MONSTER_ACTS = {9, 10, 18, 20, 36, 37}   # a WORD monster id at offset 8
AI_CAST = 24                                # skill short at 10, motion short at 12


def say(*a):
    print(*a)


# ----------------------------------------------------------------- files
class Tree:
    """Case-insensitive lookup of data-relative paths under one dump root."""

    def __init__(self, root):
        self.root = root
        self.files = {}
        for dirpath, _dirs, names in os.walk(root):
            rel = os.path.relpath(dirpath, root)
            for n in names:
                key = os.path.normpath(os.path.join(rel, n)).replace("/", "\\").lower()
                self.files[key] = os.path.join(dirpath, n)

    def find(self, rel):
        if isinstance(rel, bytes):
            rel = rel.decode("latin-1")
        return self.files.get(os.path.normpath(rel.replace("/", "\\")).replace("/", "\\").lower())

    def has(self, rel):
        return self.find(rel) is not None


def text(b, enc):
    return b.decode(enc, "replace").strip() if isinstance(b, bytes) else str(b)


def sniff_encoding(stb):
    """cp932 when kana lead bytes (0x81-0x9F) dominate the names, EUC-KR on Hangul leads
    (0xB0-0xC8), else latin-1."""
    jp = kr = 0
    for r in range(stb.rows):
        name = stb.get(r, C_NAME)
        jp += sum(1 for x in name if 0x81 <= x <= 0x9F)
        kr += sum(1 for x in name if 0xB0 <= x <= 0xC8)
    if jp > kr and jp:
        return "cp932"
    if kr:
        return "euc-kr"
    return "latin-1"


def load_reader():
    import importlib.util
    spec = importlib.util.spec_from_file_location("rose_data_reader",
                                                  os.path.join(HERE, "rose-data-reader.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def num(b):
    s = b.strip()
    return int(s) if s.lstrip(b"-").isdigit() else None


# ----------------------------------------------------------------- tables of one dump
class Dump:
    def __init__(self, root, enc=None, ours=False):
        self.root, self.ours = root, ours
        self.tree = Tree(root)
        self._stbs, self._stls, self._keycols = {}, {}, {}
        # cells stay bytes and are decoded on use, so a table is read once, before the
        # encoding is known
        self.npc = self.stb(NPC_STB)
        self.enc = "latin-1" if ours else (enc or sniff_encoding(self.npc))
        self.chr = Chr(self.tree.find(NPC_CHR))
        self.part = Zsc(self.tree.find(PART_ZSC))
        self._skill_names = None

    def stb(self, rel):
        if rel not in self._stbs:
            p = self.tree.find(rel)
            self._stbs[rel] = Stb(p) if p else None
        return self._stbs[rel]

    def stl(self, rel):
        """{key: name} -- ours: the English block (1) of our UTF-8 tables; a dump: block 0."""
        if rel not in self._stls:
            p, names = self.tree.find(rel), {}
            if p:
                try:
                    t = Stl(p, "utf-8" if self.ours else self.enc)
                    names = t.by_key(1 if self.ours and len(t.langs) > 1 else 0)
                except Exception:
                    names = {}
            self._stls[rel] = {k: (v[0] if v else "") for k, v in names.items()}
        return self._stls[rel]

    def key_column(self, stb):
        """Stb.key_column, once per table: it sniffs every cell."""
        if id(stb) not in self._keycols:
            self._keycols[id(stb)] = stb.key_column()
        return self._keycols[id(stb)]

    def names(self, stb, stl, r):
        """(table name, string-file name): col 0 and the STL entry its key names. They can
        disagree -- Jrose's 2290 is "Shadow Soldier" in its table, "Master Sword" in its STL."""
        kc = self.key_column(stb)
        key = text(stb.get(r, kc), "latin-1") if kc is not None else ""
        n = stl.get(key, "")
        n = n if isinstance(n, str) else text(n, self.enc)
        return text(stb.get(r, C_NAME), self.enc), n.strip()

    def name(self, stb, stl, r):
        """The STL name when the row has a key that resolves, else the STB col 0 text."""
        col0, s = self.names(stb, stl, r)
        return s or col0

    def skill_names(self):
        if self._skill_names is None:
            self._skill_names = (self.stb(SKILL_STB), self.stl(SKILL_STL))
        return self._skill_names

    def skill_label(self, sid):
        sk, stl = self.skill_names()
        if not sk or not 0 <= sid < sk.rows or not sk.occupied(sid):
            return "(blank)"
        return "%s (type %s, power %s, scope %s)" % (
            self.name(sk, stl, sid) or "(no name)", text(sk.get(sid, SK_TYPE), "latin-1") or "-",
            text(sk.get(sid, SK_POWER), "latin-1") or "-", text(sk.get(sid, SK_SCOPE), "latin-1") or "-")

    def skills_using_clip(self, clip):
        """[(skill row, 'cast'|'action', label)] for a clip path, through FILE_MOTION ->
        TYPE_MOTION -> LIST_SKILL cols 52/68 (level-1 rows and monster rows, one per line)."""
        fm, tm = self.stb(FILE_MOTION), self.stb(TYPE_MOTION)
        sk, stl = self.skill_names()
        if not (fm and tm and sk):
            return []
        want = os.path.normpath(clip.decode("latin-1").replace("/", "\\")).lower()
        fm_rows = {r for r in range(fm.rows)
                   if os.path.normpath(text(fm.get(r, 0), "latin-1").replace("/", "\\")).lower() == want}
        if not fm_rows:
            return []
        tm_rows = {r for r in range(tm.rows) for c in range(tm.cols) if num(tm.get(r, c)) in fm_rows}
        out, seen = [], set()
        for r in range(sk.rows):
            for col, role in ((SK_ACTION, "action"), (SK_CAST, "cast")):
                if num(sk.get(r, col)) in tm_rows:
                    line = num(sk.get(r, 1))
                    if line in seen:
                        continue
                    seen.add(line)
                    out.append((r, role, self.skill_label(r)))
        return out


# ----------------------------------------------------------------- clips
def qang(a, b):
    d = abs(sum(x * y for x, y in zip(a, b)))
    return math.degrees(2 * math.acos(min(1.0, d)))


def motion_profile(blob):
    """Summed rotation change (degrees) of every bone from the previous frame, per frame
    (frame 0 = 0), and the loop seam (last frame -> first)."""
    _fps, frames, _ch = rz.read_header(blob)
    vals = [rz.frame_values(blob, f) for f in range(frames)]

    def step(p, q):
        return sum(qang(a, b) for (t, _, a), (_, _, b) in zip(p, q) if t == 4)
    prof = [0.0] + [step(vals[f - 1], vals[f]) for f in range(1, frames)]
    return prof, step(vals[-1], vals[0])


def clip_info(tree, rel):
    p = tree.find(rel)
    if not p:
        return None
    blob = open(p, "rb").read()
    h = rz.read_header(blob)
    if h is None:
        return None
    _, ev = rz.events(blob)
    events = {i: e for i, e in enumerate(ev or []) if e}
    return dict(blob=blob, fps=h[0], frames=h[1], events=events,
                attack=sum(1 for e in events.values() if e in SERVER_ATTACK))


def presents(info):
    ev = set(info["events"].values())
    kinds = []
    if ev & PROJECTILE:
        kinds.append("projectile/area " + "/".join(str(e) for e in sorted(ev & PROJECTILE)))
    if ev & STRIKE:
        kinds.append("strike " + "/".join(str(e) for e in sorted(ev & STRIKE)))
    fx = sorted(CASTING_FX[e] for e in ev if e in CASTING_FX)
    if fx:
        kinds.append("casting fx " + ",".join(map(str, fx)))
    return "; ".join(kinds) or "NO presenting event"


def print_profile(info, bars):
    prof, seam = motion_profile(info["blob"])
    ev = info["events"]
    if bars:
        for f, v in enumerate(prof):
            mark = ("ev %d" % ev[f]) if f in ev else ""
            say("        %3d %6.0f %-6s %s" % (f, v, mark, "#" * int(v / 6)))
    else:
        cells = ["%d%s" % (round(v), ("[%d]" % ev[f]) if f in ev else "") for f, v in enumerate(prof)]
        line, out = "", []
        for c in cells:
            if len(line) + len(c) + 1 > 92:
                out.append(line)
                line = ""
            line += c + " "
        out.append(line)
        for i, l in enumerate(out):
            say("        %s %s" % ("motion/frame" if i == 0 else "            ", l.rstrip()))
    peak = max(range(len(prof)), key=lambda f: prof[f]) if prof else 0
    say("        peak motion at frame %d (%.0f deg); loop seam %.1f deg%s" % (
        peak, prof[peak] if prof else 0, seam, " -- loops cleanly" if seam < 5 else ""))


# ----------------------------------------------------------------- sections
def section(title):
    say("")
    say("== " + title)


def survey_row(src, r, rd):
    npc = src.npc
    stl = src.stl(NPC_STL)
    def glossed(n):
        return n + (("  [%s]" % rd.gloss(n)) if rd and n and not n.isascii() else "")
    col0, strname = src.names(npc, stl, r)
    say("%s LIST_NPC %d: %s" % (os.path.basename(src.root.rstrip("\\/")), r, glossed(col0 or strname)))
    if strname and col0 and strname != col0:
        say("    string file calls it: %s" % glossed(strname))
    g = lambda c: text(npc.get(r, c), src.enc)  # noqa: E731
    say("    model %s  walk/run %s/%s  size %s  height %s" % (g(C_MODEL), g(C_WALK), g(C_RUN), g(C_SIZE),
                                                             g(C_HEIGHT) or "-"))
    say("    right hand %s  left hand %s  level %s  HP/level %s  ATK %s   (stats are never imported)"
        % (g(C_RWEAPON) or "-", g(C_LWEAPON) or "-", g(C_LEVEL), g(C_HP), g(C_ATK)))
    say("    AI row %s  mark %s  glow %s  key %s" % (g(C_AI) or "-", g(C_MARK) or "-", g(C_GLOW) or "-",
                                                    g(C_STRID) or "-"))
    say("    neighbours:")
    for n in range(max(0, r - 6), min(npc.rows, r + 7)):
        if n != r and npc.get(n, C_NAME).strip():
            c0, sn = src.names(npc, stl, n)
            nm = c0 or sn
            say("      %5d %-28s %-26s AI %s" % (n, nm[:28], text(npc.get(n, C_MODEL), src.enc)[:26],
                                                 text(npc.get(n, C_AI), src.enc) or "-"))


def free_here(ours, r, family):
    def free(n):
        return (not ours.npc.get(n, C_NAME).strip() if n < ours.npc.rows else True) and \
               (n >= len(ours.chr.chars) or ours.chr.chars[n] is None)
    if free(r):
        say("    our row %d is free (no name, no CHR entry): import at the source's number" % r)
    else:
        stl = ours.stl(NPC_STL)
        say("    our row %d is taken: %s" % (r, ours.name(ours.npc, stl, r) or "(no name, but a CHR entry)"))
    runs, run = [], []
    for n in range(1, max(ours.npc.rows, len(ours.chr.chars)) + family):
        if free(n):
            run.append(n)
        else:
            if len(run) >= family:
                runs.append((run[0], run[-1]))
            run = []
    if len(run) >= family:
        runs.append((run[0], run[-1]))
    near = sorted(runs, key=lambda ab: min(abs(ab[0] - r), abs(ab[1] - r)))[:4]
    say("    nearest free runs of %d+: %s" % (family, ", ".join("%d-%d" % ab for ab in sorted(near))))


def model_files(dump, entry):
    out = []
    for m in entry["models"]:
        ob = dump.part.objects[m] if m < len(dump.part.objects) else None
        for mi, ti, _ in (ob[1] if ob else []):
            out.append((dump.part.meshes[mi], dump.part.materials[ti][0]))
    return out


def survey_chr(src, ours, r, bars):
    e = src.chr.chars[r] if r < len(src.chr.chars) else None
    if e is None:
        say("    no LIST_NPC.CHR entry in the source: nothing to import a model from")
        return
    skels = src.chr.skeletons
    sk = skels[e["skel"]] if e["skel"] < len(skels) else b"?"
    say("    skeleton %s  [%s]" % (text(sk, "latin-1"), "ours" if ours.tree.has(sk) else "new"))
    parts = model_files(src, e)
    for mesh, tex in parts:
        say("    part %-58s %-4s tex %-50s %s" % (text(mesh, "latin-1"), "ours" if ours.tree.has(mesh) else "NEW",
                                                 text(tex, "latin-1"), "ours" if ours.tree.has(tex) else "NEW"))
    # same meshes in one of our entries?
    want = {os.path.normpath(text(m, "latin-1")).lower() for m, _ in parts}
    same = []
    for i, oe in enumerate(ours.chr.chars):
        if oe and want:
            have = {os.path.normpath(text(m, "latin-1")).lower() for m, _ in model_files(ours, oe)}
            if have == want:
                same.append(i)
    if same:
        stl = ours.stl(NPC_STL)
        say("    OUR CHR entries with exactly these meshes: " + ", ".join(
            "%d %s" % (i, ours.name(ours.npc, stl, i) if i < ours.npc.rows else "") for i in same[:8]))

    # who uses each of our clips (to tell a shared monster clip from a player one)
    users = defaultdict(set)
    for i, oe in enumerate(ours.chr.chars):
        for _s, a in (oe["anims"] if oe else []):
            if a < len(ours.chr.motions):
                users[os.path.normpath(text(ours.chr.motions[a], "latin-1")).lower()].add(i)

    say("    anim slots (a cast on slot N releases on N+1; the source's events; "
        "ours* = our copy differs):")
    anims = dict(e["anims"])
    infos = {}
    for slot, a in e["anims"]:
        if a >= len(src.chr.motions):
            continue
        rel = src.chr.motions[a]
        # the source's clip is what was authored; ours (an earlier import may have added
        # events) is only the fallback when the dump lacks the file
        theirs, mine = clip_info(src.tree, rel), clip_info(ours.tree, rel)
        info = theirs or mine
        infos[slot] = (rel, info)
        where = ("NEW" if theirs else "MISSING") if not mine else \
            ("ours*" if theirs and theirs["blob"] != mine["blob"] else "ours")
        n_users = len(users.get(os.path.normpath(text(rel, "latin-1")).lower(), ()))
        say("      %2d %-48s %-7s %s" % (slot, text(rel, "latin-1").split("\\")[-1], where,
                                         "" if not info else "%d f @%d, events %s, %d attack frame(s)%s" % (
                                             info["frames"], info["fps"], info["events"] or "{}",
                                             info["attack"],
                                             ", %d of our monsters use it" % n_users if n_users else "")))
    for cast in sorted(s for s in anims if s >= 6 and s % 2 == 0):
        if cast not in infos or cast + 1 not in infos:
            continue
        say("")
        say("    skill pair %d/%d:" % (cast, cast + 1))
        for slot, role in ((cast, "cast"), (cast + 1, "release")):
            rel, info = infos[slot]
            say("      %-7s %s" % (role, text(rel, "latin-1")))
            if not info:
                say("        (file missing in both dumps)")
                continue
            if role == "release":
                say("        presents: %s; server attack frames %d" % (presents(info), info["attack"]))
            for label, dump in (("ours", ours), ("source", src)):
                hits = dump.skills_using_clip(rel)
                for srow, how, lab in hits[:6]:
                    say("        %-6s skill %d uses it as %s: %s" % (label, srow, how, lab))
                if hits:
                    break
            print_profile(info, bars)


def survey_weapon(src, ours, r, rd):
    rw = num(src.npc.get(r, C_RWEAPON))
    lw = num(src.npc.get(r, C_LWEAPON))
    if not rw and not lw:
        say("    bare-handed: its hits present through NPC_HAND_HIT_EFFECT (col 33)")
        return
    if rw:
        sw, ow = src.stb(WEAPON_STB), ours.stb(WEAPON_STB)
        sstl, ostl = src.stl(WEAPON_STL), ours.stl(WEAPON_STL)
        szsc, ozsc = Zsc(src.tree.find(WEAPON_ZSC)), Zsc(ours.tree.find(WEAPON_ZSC))
        nm = src.name(sw, sstl, rw) if sw and rw < sw.rows else "?"
        say("    right hand: source LIST_WEAPON %d %s%s" % (rw, nm,
                                                       ("  [%s]" % rd.gloss(nm)) if rd and not nm.isascii() else ""))
        if sw and rw < sw.rows:
            say("      type %s  need (cols 19/20) %s/%s  ATK %s" % (text(sw.get(rw, 4), "latin-1"), text(sw.get(rw, 19), "latin-1"),
                                                     text(sw.get(rw, 20), "latin-1"), text(sw.get(rw, 35), "latin-1")))
        ob = szsc.objects[rw] if rw < len(szsc.objects) else None
        for mi, ti, _ in (ob[1] if ob else []):
            mesh, tex = szsc.meshes[mi], szsc.materials[ti][0]
            say("      mesh %s [%s]  tex %s [%s]" % (text(mesh, "latin-1"), "ours" if ours.tree.has(mesh) else "NEW",
                                                     text(tex, "latin-1"), "ours" if ours.tree.has(tex) else "NEW"))
            mk, tk = mesh.lower(), tex.lower()
            same, other = [], []
            for i, oob in enumerate(ozsc.objects):
                for omi, oti, _ in (oob[1] if oob else []):
                    if ozsc.meshes[omi].lower() == mk:
                        (same if ozsc.materials[oti][0].lower() == tk else other).append(i)
            label = lambda i: "%d %s" % (i, ours.name(ow, ostl, i) if i < ow.rows else "")  # noqa: E731
            if same:
                say("      WE HAVE IT: our weapon %s (same mesh and texture)" % ", ".join(map(label, same[:5])))
            elif other:
                say("      same mesh, other texture: our %s -> a new item on art we ship (import-item.py --art-only)"
                    % ", ".join(map(label, other[:5])))
            else:
                say("      new model -> import-item.py --art-only")
    if lw:
        sz = Zsc(src.tree.find(SUBWPN_ZSC))
        ob = sz.objects[lw] if lw < len(sz.objects) else None
        parts = [(sz.meshes[mi], sz.materials[ti][0]) for mi, ti, _ in (ob[1] if ob else [])]
        say("    left hand: LIST_SUBWPN.ZSC %d %s" % (lw, ", ".join(
            "%s [%s]" % (text(m, "latin-1").split("\\")[-1], "ours" if ours.tree.has(m) else "NEW") for m, _ in parts)
            or "(empty object)"))


def survey_ai(src, ours, r):
    row = num(src.npc.get(r, C_AI))
    fai = src.stb(FILE_AI)
    if row is None:
        say("    no AI row")
        return
    if not fai or row >= fai.rows:
        say("    AI row %d, but the dump has %s: author our own" % (
            row, "no FILE_AI table" if not fai else "no such FILE_AI row"))
        return
    rel = text(fai.get(row, 0), "latin-1")
    p = src.tree.find(rel)
    say("    FILE_AI %d = %s  [%s]" % (row, rel, "shipped" if p else "NOT shipped: author our own"))
    if not p:
        return
    _h, _t, pats, _tail = aip.parse(open(p, "rb").read())
    casts, mons = Counter(), Counter()
    for _pn, evs in pats:
        for _en, _conds, acts in evs:
            for a in acts:
                kind = (aip.record_type(a) & 0xFF) - 1
                if kind == AI_CAST and len(a) >= 14:
                    casts[struct.unpack_from("<hh", a, 10)] += 1
                elif kind in AI_MONSTER_ACTS and len(a) >= 10:
                    mons[struct.unpack_from("<H", a, 8)[0]] += 1
    for (sid, motion), n in sorted(casts.items()):
        say("      cast %d on motion %d (x%d): source %s | ours %s" % (
            sid, motion, n, src.skill_label(sid), ours.skill_label(sid)))
    for mid, n in sorted(mons.items()):
        stl = src.stl(NPC_STL)
        say("      names monster %d (x%d): %s" % (mid, n, (src.names(src.npc, stl, mid)[0] or src.name(src.npc, stl, mid)) if mid < src.npc.rows else "?"))
    if not casts and not mons:
        say("      no casts, no monster references")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", help="the dump's folder (holds 3Ddata)")
    ap.add_argument("row", type=int, help="its LIST_NPC row")
    ap.add_argument("--ours", default=os.path.join(ROOT, "data"))
    ap.add_argument("--enc", help="the dump's text encoding (default: sniffed)")
    ap.add_argument("--family", type=int, default=4, help="free-run length to look for (default 4)")
    ap.add_argument("--profile", action="store_true", help="draw motion profiles as bars")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    try:
        rd = load_reader()
    except Exception:
        rd = None

    src = Dump(args.src, args.enc)
    ours = Dump(args.ours, ours=True)
    if not src.npc.occupied(args.row):
        raise SystemExit("source LIST_NPC row %d is blank" % args.row)
    say("(source names decoded as %s)" % src.enc)
    survey_row(src, args.row, rd)
    section("where it can land here")
    free_here(ours, args.row, args.family)
    section("model and animations (LIST_NPC.CHR)")
    survey_chr(src, ours, args.row, args.profile)
    section("weapon")
    survey_weapon(src, ours, args.row, rd)
    section("AI")
    survey_ai(src, ours, args.row)
    say("")
    say("Next: doc/importing-monsters.md; start the script from scripts/import-shadow-soldier.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
