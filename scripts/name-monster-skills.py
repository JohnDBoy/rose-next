"""Readable English labels for the skills monsters cast (2026-10-16), for our tools.

Of the 247 LIST_SKILL rows monster AI files cast (AIACT24), 140 had a blank name (tools
printed "#3042") and 49 a Korean developer label -- and those labels are templates shared
by dozens of different skills (셀프지속형 "self buff, duration type", 볼트 발사 "bolt
shot", 범위데미지 "area damage"), so even translated they said nothing. Tools (the combat
simulator, Rose Dev Studio, the audits) show the name table (LIST_SKILL_S.STL) when a row
has an entry and LIST_SKILL col 0 otherwise; monster skills have no name-table entry, so
col 0 is what we read.

This writes col 0 of every monster-cast skill whose label is blank or Korean:

    <what it does>[: <its states>] (<who casts it>)
    e.g. 3042 "Area Blast (Asper, Asper Assassin, Asper Commander ...)"

  * what: Summon / Area Blast (type 17) / Target Area Blast (7) / Bolt (6) / Strike (3-5,
    19; "Magic Strike" when magic) / Self Buff or Self Effect (8, 12: Effect when a state
    is harmful) / Buff or Debuff (9, 13) / Heal (10, 11)
  * states: their LIST_STATUS names ("Attack Power Up", "Stunned", "Asleep" ...)
  * casters: up to three monster names (family prefixes dropped only past three)

English labels already there (55, e.g. Kera Stun Blast) and player skills are not touched.
Players never see col 0 (the client names skills from the name table); their names come
from name-monster-skills-players.py, which gives these rows name-table entries.

    python scripts/name-monster-skills.py --dry-run
    python scripts/name-monster-skills.py
    python scripts/name-monster-skills.py --verify
    python scripts/name-monster-skills.py --restore

Cell-level manifest in build/monster-skill-names/ ([old, written] per cell); verify checks
the written cells, restore puts back the cells nobody edited since. Re-bake to carry the
labels into the VFS (tools read data/ directly).
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import rosedata as oro  # noqa: E402
from combatsim import GameData  # noqa: E402
from combatsim.ai import load_for_npc  # noqa: E402
import combatsim.autobuild as autobuild  # noqa: E402

STB = os.path.join(REPO, "data", "3DDATA", "STB", "LIST_SKILL.STB")
MANIFEST = os.path.join(REPO, "build", "monster-skill-names", "manifest.json")
HANGUL = re.compile(r"[가-힣]")
PREFIX = re.compile(r"^(Darkened|Venerable|Vicious|Elder|Baby|Hooded|Crowned|Fiery|Barbed|Wise|"
                    r"Giant|Grand Master|Little|Captive) ")
KIND = {17: "Area Blast", 7: "Target Area Blast", 6: "Bolt", 3: "Strike", 4: "Strike",
        5: "Strike", 19: "Strike"}


def dec(b):
    for enc in ("utf-8", "cp949", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return ""


def casters(gd):
    npc = gd.stb("LIST_NPC")
    out = defaultdict(set)
    for r in range(1, npc.rows):
        if not npc.occupied(r):
            continue
        try:
            ai = load_for_npc(gd, r)
        except Exception:
            continue
        if not ai:
            continue
        for p in range(6):
            for s, _m, _t in ai.skills(p):
                out[s].add(r)
    return out


def label(gd, row, who):
    sk = gd.skill(row)
    states = [x for x in sk.states if x]
    names = [gd.name("LIST_STATUS", x) or f"state {x}" for x in states]
    harmful = any(gd.state_harmful(x) == 1 for x in states)
    if sk.type == 14:
        what = "Summon"
    elif sk.is_damage():
        what = KIND.get(sk.type, "Attack")
        if what == "Strike" and sk.damage_type == 2:
            what = "Magic Strike"
    elif sk.type in (8, 12):
        what = "Self Effect" if harmful else "Self Buff"
    elif sk.type in (9, 13):
        what = "Debuff" if harmful else "Buff"
    elif sk.type in (10, 11):
        what = "Heal"
    else:
        what = f"Skill (type {sk.type})"
    eff = f": {', '.join(dict.fromkeys(names))}" if names else ""
    full = sorted({(gd.name("LIST_NPC", r) or "").strip() for r in who} - {""})
    full = [m for m in full if "??" not in m]      # rows whose name is garbled in our data
    # family prefixes are dropped only to shorten a long list (a lone Giant Fiery Snapper
    # must not read as the regular Fiery Snapper)
    mobs = full if len(full) <= 3 else sorted({PREFIX.sub("", m) for m in full})
    by = ", ".join(mobs[:3]) + (" ..." if len(mobs) > 3 else "")
    return f"{what}{eff} ({by})" if by else f"{what}{eff}"


def plan(gd, stb):
    player = set()
    for job in (111, 121, 122, 131, 132, 211, 221, 222, 231, 232, 311, 321, 322, 331, 332,
                411, 421, 422, 431, 432):
        for f in autobuild.class_skills(gd, job):
            player.update(autobuild.skill_ranks(gd, f))
    out = {}
    for row, who in sorted(casters(gd).items()):
        if row in player or row <= 0 or row >= stb.rows:
            continue
        raw = dec(stb.get(row, 0).strip())
        if not raw or HANGUL.search(raw):
            out[(row, 0)] = label(gd, row, who)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()
    raw = open(STB, "rb").read()
    stb = oro.Stb(STB)
    if stb.to_bytes() != raw:
        print("ABORT: the STB writer does not round-trip LIST_SKILL.STB byte-for-byte")
        return 1
    man = json.load(open(MANIFEST, encoding="utf-8")) if os.path.isfile(MANIFEST) else None

    if args.restore or args.verify:
        if not man:
            print("not applied")
            return 0 if args.restore else 1
        bad = 0
        for key, (old, new) in man["cells"].items():
            r, c = (int(x) for x in key.split(","))
            cur = stb.get(r, c).strip()
            if cur != new.encode("utf-8"):
                bad += 1
                if args.restore:
                    print(f"   skip {key}: edited since")
                continue
            if args.restore:
                stb.set(r, c, old.encode("latin-1"))
        if args.verify:
            print("ALL CHECKS PASSED" if not bad else f"VERIFY FAILED: {bad} cell(s) differ")
            return 1 if bad else 0
        open(STB, "wb").write(stb.to_bytes())
        os.remove(MANIFEST)
        print(f"restored {len(man['cells']) - bad} cell(s)")
        return 0
    if man:
        print(f"already applied ({len(man['cells'])} cells); --restore first to redo")
        return 0

    gd = GameData()
    todo = plan(gd, stb)
    print(f"{len(todo)} labels to write; for example:")
    for (r, c), v in list(todo.items())[:12]:
        print(f"   {r:>5} col {c:>2}: {dec(stb.get(r, c).strip()) or '(blank)'} -> {v}")
    if args.dry_run:
        print("dry run: nothing written")
        return 0
    cells = {}
    for (r, c), v in todo.items():
        cells[f"{r},{c}"] = [stb.get(r, c).strip().decode("latin-1"), v]
        stb.set(r, c, v.encode("utf-8"))
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    json.dump({"cells": cells}, open(MANIFEST, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    open(STB, "wb").write(stb.to_bytes())
    print(f"wrote {len(todo)} cell(s) (undo: --restore)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
