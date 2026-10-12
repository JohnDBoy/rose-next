"""Remove skill books that teach a skill which does not exist from NPC shops.

Pre-alpha #2 testers visiting [Mayor] Darren (NPC 1081, Junon Polis -- the
advanced-skill-book seller) found books with **no class requirement** for
skills that are in **no skill tree**: Advance Crossbow Mastery, Crossbow Speed
Mastery, and a handful more. Both symptoms have one cause.

A skill book is a LIST_USEITEM row of class 314 (`USE_ITEM_SKILL_LEARN`,
datatype.h) whose col 20 (`USEITEM_SCROLL_LEARN_SKILL`, rose/io/stb.h) names
the LIST_SKILL row it teaches. **The book has no class gate of its own.** The
tooltip (`CIconSkill::AddSkillRequireJob`) and the server's
`Skill_LearnCondition` both read the *target skill's* LIST_SKILL col 35
(`SKILL_AVAILBLE_CLASS_SET`). When col 20 points at a blank LIST_SKILL row,
col 35 reads 0 -> "no class required", and the learn fails with
`RESULT_SKILL_LEARN_INVALID_SKILL` -- so the book is on sale, shows no
requirement, and can never be used.

Surveying every LIST_SELL tab that a real NPC references (LIST_NPC col 27 ==
999, tab cols 21-24), ten tabs hold skill books and exactly nine slots point
at a skill that does not exist:

    tab slot  LIST_USEITEM row                 -> LIST_SKILL row
    462  23   669 Brave Howl                   -> 414   blank
    462  33   650 Advance Crossbow Mastery     -> 311   blank
    462  35   649 Double Shot*                 -> 541   stub (only col 35 = 61)
    462  37   679 Trap Arrow                   -> 561   stub
    462  38   680 Poisoned Shot                -> 571   stub
    462  39   681 Critical Shot                -> 581   stub
    462  40   648 Crossbow Speed Mastery       -> 431   blank
    468  12   823 Concussor                    -> 2291  blank
    217  26   649 Double Shot*                 -> 541   stub (Leonard)

(* in-game English name; the STB's internal col-0 name is "Double Crossbow
Shot". Book names are decorative -- several sold books were named after a
different skill than the one col 20 teaches, since fixed by
`fix-skill-book-names.py` -- so the join is by id only.)

Tabs 462/464/466/468 are Darren's (his `.CON` passes `bSpecialTab = 1`, so
all four draw) and are **shared** with the Akram Ministers Gamp/Nell/Rodath/Mel
(1084-1087) and Arua's Fairy (1108); tab 217 is [Righteous Crusader] Leonard's.
Clearing the cell fixes every seller at once.

The four "stub" rows carry a single cell -- col 35 = 61 (Knight Job) -- and
nothing else: no name, no STL key, no SKILL_TYPE, no icon (col 51 = 0, which
alone makes a skill unlearnable), and no place in any skilltree_*.xml. They
are the abandoned Knight crossbow line and are treated as dead.

What is deliberately **kept**, and why the rule is written the way it is:

  * Leonard's tab 219 and Pony's tab 308 sell the basic and emote books (Sit,
    Pick Up, Jump, Party, Trade, Vending, Hi, Laugh, ...). Those skills exist,
    are class-less *by design* and are in no tree. So `col 35 == 0` and "not
    in a skill tree" are **not** deletion criteria -- only "the skill row is
    effectively blank" is (see `dead_skill`).
  * The GM/test book block (LIST_USEITEM 871-896) is sold by nobody and is not
    touched; neither are the ~60 other unsold books.
  * The LIST_USEITEM rows of the nine pruned books stay. A tester who already
    bought one keeps a harmless, unusable item with a proper name; blanking the
    row would turn it into a nameless icon in their inventory.
  * The freed slots are left as **gaps**, not compacted. The client positions a
    shop icon by its slot index, and these tabs already have gaps (Darren's
    Soldier tab is empty at 4-7, 14-15, 29-31), so closing them would reshuffle
    every icon for no gain.

The rule is generic, but the script also carries the reviewed set above as
`EXPECTED`. If the rule ever matches a slot outside it -- say a future import
adds a book before its skill row -- the script prints the newcomer and refuses
to write unless `--allow-new`, so an old rule cannot silently prune new data.

Idempotent. `--dry-run` / `--verify` / `--restore`. Undo is **cell-level**: the
sidecar build/dead-skill-books.json records each cleared cell's old value and
`--restore` replays only those cells, so it cannot revert another script's
edits to the same table (a whole-file copy is kept alongside for forensics
only). Backups go to build/, never beside the data: src/pipeline/src/pack.rs
walks the data tree filtering only *hidden* entries, so a .bak in
data/3DDATA/STB gets baked into the .vfs.

After running: restart the servers (they cache STBs at startup and validate
purchases against the tab) and re-bake the client VFS.
"""
import argparse
import importlib.util
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STB = os.path.join(ROOT, "data", "3DDATA", "STB")
SELL_STB = os.path.join(STB, "LIST_SELL.STB")
NPC_STB = os.path.join(STB, "LIST_NPC.STB")
USEITEM_STB = os.path.join(STB, "LIST_USEITEM.STB")
USEITEM_STL = os.path.join(STB, "LIST_USEITEM_S.STL")
SKILL_STB = os.path.join(STB, "LIST_SKILL.STB")
BACKUP = os.path.join(ROOT, "build", "dead-skill-books-backup")
SIDECAR = os.path.join(ROOT, "build", "dead-skill-books.json")

# Rose::Store::encode_store_item -- two regimes, see reference in
# src/common/include/rose/common/store_item_code.h.
WIDE_BASE = 100000
SLOTS = 48                  # LIST_SELL is 2 + 48 columns
FIRST_SLOT_COL = 2

T_USE = 10                  # ITEM_TYPE_USE -> LIST_USEITEM
USE_ITEM_SKILL_LEARN = 314  # datatype.h t_eItemCLASS
USE_COL_CLASS = 4           # ITEM_TYPE(): the use-item class
USE_COL_SKILL = 20          # USEITEM_SCROLL_LEARN_SKILL

NPC_COL_TYPE = 27           # 999 = real NPC (conversation/shop)
NPC_TYPE_REAL = 999
NPC_TAB_COLS = (21, 22, 23, 24)

SK_COL_NAME = 0
SK_COL_TYPE = 5             # SKILL_TYPE
SK_COL_CLASS = 35           # SKILL_AVAILBLE_CLASS_SET
SK_COL_ICON = 51            # SKILL_ICON_NO -- 0 means it cannot be learned
SK_COL_STL_KEY = 86         # LSkillNNNN

# (tab, slot, useitem row): the nine reviewed on 2026-09-22.
EXPECTED = {
    (462, 23, 669), (462, 33, 650), (462, 35, 649), (462, 37, 679),
    (462, 38, 680), (462, 39, 681), (462, 40, 648),
    (468, 12, 823),
    (217, 26, 649),
}


def load(name):
    spec = importlib.util.spec_from_file_location(
        name.replace("-", "_"), os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, [name]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved
    return mod


def cell_int(stb, r, c):
    v = stb.get(r, c).strip()
    try:
        return int(v)
    except ValueError:
        return 0


def decode_store_item(v):
    if v >= WIDE_BASE:
        return v // WIDE_BASE, v % WIDE_BASE
    return v // 1000, v % 1000


def npc_tabs(npc):
    """LIST_SELL row -> [npc row] for every tab a real NPC points at."""
    used = {}
    for r in range(npc.rows):
        if cell_int(npc, r, NPC_COL_TYPE) != NPC_TYPE_REAL:
            continue
        for c in NPC_TAB_COLS:
            t = cell_int(npc, r, c)
            if t > 0:
                used.setdefault(t, []).append(r)
    return used


def dead_skill(sk, s):
    """True when LIST_SKILL row `s` is effectively blank.

    Every condition must hold. A class-less emote (col 35 == 0) has a name, a
    type and an icon; a skill outside the trees still has a name. Only the
    abandoned rows -- blank, or a lone class cell -- fail all four.
    """
    if s <= 0 or s >= sk.rows:
        return True
    return (not sk.get(s, SK_COL_NAME).strip()
            and not sk.get(s, SK_COL_STL_KEY).strip()
            and cell_int(sk, s, SK_COL_TYPE) == 0
            and cell_int(sk, s, SK_COL_ICON) == 0)


def survey(oro, rd):
    """[(tab, slot, useitem row, skill row, book name, npc rows)] for every
    NPC-sold skill book whose skill is dead."""
    sell = oro.Stb(SELL_STB)
    npc = oro.Stb(NPC_STB)
    use = oro.Stb(USEITEM_STB)
    sk = oro.Stb(SKILL_STB)
    names = rd.Stl(USEITEM_STL, "utf-8").by_key(1)     # block 1 is English
    found = []
    for tab, npcs in sorted(npc_tabs(npc).items()):
        if tab >= sell.rows:
            continue                                     # dangling tab, blank in game
        for slot in range(SLOTS):
            v = cell_int(sell, tab, FIRST_SLOT_COL + slot)
            if v <= 0:
                continue
            ty, no = decode_store_item(v)
            if ty != T_USE or cell_int(use, no, USE_COL_CLASS) != USE_ITEM_SKILL_LEARN:
                continue
            s = cell_int(use, no, USE_COL_SKILL)
            if dead_skill(sk, s):
                key = use.get(no, use.cols - 1).decode("latin-1").strip()
                name = names.get(key, (use.get(no, 0).decode("latin-1"),))[0]
                found.append((tab, slot, no, s, name, npcs))
    return found


def describe(found, sk):
    lines = []
    for tab, slot, no, s, name, npcs in found:
        state = "out of range" if s <= 0 or s >= sk.rows else \
                ("blank" if not sk.occupied(s) else
                 "stub (class %d only)" % cell_int(sk, s, SK_COL_CLASS))
        lines.append(f"  tab {tab} slot {slot:2d}  10:{no} {name:<28} -> skill {s:<5} "
                     f"{state:<22} npcs {npcs}")
    return lines


def verify(oro, rd):
    bad = []
    sell = oro.Stb(SELL_STB)
    sk = oro.Stb(SKILL_STB)
    left = survey(oro, rd)
    if left:
        bad.append("dead skill books still on sale:")
        bad += describe(left, sk)
    for tab, slot, no in sorted(EXPECTED):
        v = sell.get(tab, FIRST_SLOT_COL + slot).strip()
        if v:
            bad.append(f"tab {tab} slot {slot} still holds {v.decode('latin-1')!r}")
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--allow-new", action="store_true",
                    help="also prune books the rule finds outside the reviewed set")
    args = ap.parse_args()

    import rosedata as oro  # the shared data layer (was import-oro.py)
    rd = load("rose-data-reader")

    if args.restore:
        if not os.path.isfile(SIDECAR):
            sys.exit("no sidecar -- nothing to restore")
        with open(SIDECAR, encoding="utf-8") as fh:
            side = json.load(fh)
        sell = oro.Stb(SELL_STB)
        n = 0
        for tab, slots in side["cells"].items():
            for slot, old in slots.items():
                sell.set(int(tab), FIRST_SLOT_COL + int(slot), old.encode("latin-1"))
                n += 1
        with open(SELL_STB, "wb") as fh:
            fh.write(sell.to_bytes())
        os.remove(SIDECAR)
        print(f"restored {n} cell(s) into LIST_SELL.STB")
        return 0

    if args.verify:
        bad = verify(oro, rd)
        print(f"{len(EXPECTED)} expected cells; {len(bad)} problem(s)"
              + ("\n  " + "\n  ".join(bad) if bad else ""))
        return 1 if bad else 0

    sk = oro.Stb(SKILL_STB)
    found = survey(oro, rd)
    if not found:
        print("no dead skill books on sale; nothing to do")
        return 0
    print(f"{len(found)} skill book(s) on sale teach a skill that does not exist:")
    print("\n".join(describe(found, sk)))

    new = [(t, s, n) for t, s, n, *_ in found if (t, s, n) not in EXPECTED]
    if new and not args.allow_new:
        print(f"\n{len(new)} of these are outside the reviewed set {sorted(new)} -- "
              "review them and re-run with --allow-new")
        return 1

    if args.dry_run:
        print("dry run: nothing written")
        return 0

    sell = oro.Stb(SELL_STB)
    side = {"cells": {}}
    if os.path.isfile(SIDECAR):
        with open(SIDECAR, encoding="utf-8") as fh:
            side = json.load(fh)
    for tab, slot, *_ in found:
        col = FIRST_SLOT_COL + slot
        side["cells"].setdefault(str(tab), {})[str(slot)] = \
            sell.get(tab, col).decode("latin-1")
        sell.set(tab, col, b"")

    os.makedirs(BACKUP, exist_ok=True)
    bak = os.path.join(BACKUP, os.path.basename(SELL_STB))
    if not os.path.exists(bak):
        shutil.copyfile(SELL_STB, bak)
    with open(SELL_STB, "wb") as fh:
        fh.write(sell.to_bytes())
    with open(SIDECAR, "w", encoding="utf-8") as fh:
        json.dump(side, fh, indent=1)

    bad = verify(oro, rd)
    if bad:
        print("VERIFY FAILED after writing:")
        for b in bad:
            print("  " + b)
        return 1
    print(f"\ncleared {len(found)} cell(s); written and verified. "
          "Restart the servers and re-bake the VFS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
