"""Re-sync Karkia's monster names from `import-karkia.py`'s KARKIA_MONSTERS.

Written for one specific defect and kept as a general tool.

--- the defect

The Devil Pest monsters were authored as **`D-Victim`, `D-Ghoul Ein`, `D-Seed`**
and so on. The source spells that prefix with an **equals sign**, not a hyphen --
Jrose's own player-facing rows are `D=シード` and `Ｄ＝エラー` -- and one line of
dialog we shipped in stage 6c quotes it directly:

    "So every monster with 'D=' in its name is a victim of the Devil Pest."

which the Field Medic says while standing next to twelve monsters whose names all
began with a hyphen. The player was told to look for a prefix that appeared
nowhere in the game. Ten more lines name `D=Seed`, `D=Victim`, `D=Error`,
`D=Ghoul` and `D=Alma Core` the same way, several of them as hunt instructions.

So this is not a re-theme; it is one character, twelve rows, restoring agreement
between the monsters and the text that explains them.

--- two things deliberately NOT changed

**The " Alpha" suffix stays.** It looks like filler -- the ten Spire Village
monsters are the Cemetery roster again, same art, +13 levels -- but it is canon:
the source rows carry only *dev placeholders* (`KSヴィクティムf`), while the
dialog names the creatures outright as `D=ヴィクティムα` and `蘇った防疫団員α`,
and two quests tell the player to kill thirty of each by that name. Renaming them
would desynchronise those lines. What is genuinely open is the shared **art**, not
the names.

**`D=Victim` on both 2701 and 2702 stays.** Two rows, one name, and that is
normal here: 186 names in `LIST_NPC` are used by more than one row (Candle Ghost
by 32 of them). The source distinguishes them only by an editor label.

--- why a separate script

Correcting `KARKIA_MONSTERS` alone changes nothing on disk. `import-karkia.py`
stage 3 writes a name only into a row it is creating -- `if our_npc.occupied(i):
continue`, and the STL likewise `if our_stl.has(key): continue` -- which is what
makes re-running it safe for the balance passes, and also what makes it unable to
ever *revise* a name. This pass writes names and nothing else, so it can be run
against live, rebalanced data without touching a single stat.

--- both sides, always

A monster's name is stored twice and read by different processes:

    server   NPC_NAME(I) -> g_TblNPC.get_cstr(I, 0)          LIST_NPC.STB col 0
    client   NPC_NAME(I) -> CStringManager::GetNpcName(I)    LIST_NPC_S.STL,
                            keyed by NPC_STRING_ID = col 40

Writing only the STB renames it for the server -- GM tools, logs, `/item`-style
lookups -- while every player still reads the old name, and nothing warns you.

Idempotent. `--dry-run` / `--verify` / `--restore`. The sidecar goes to build/,
never beside the data: `pack.rs` walks the data tree filtering only *hidden*
entries, so a stray file in `data/3DDATA/STB` is baked into the `.vfs`.

After running: restart the servers (they cache STBs at startup) and re-bake the
client VFS.
"""
import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
NPC_STB = os.path.join(DATA, "3DDATA", "STB", "LIST_NPC.STB")
NPC_STL = os.path.join(DATA, "3DDATA", "STB", "LIST_NPC_S.STL")
SIDECAR = os.path.join(ROOT, "build", "karkia-monster-names.json")

NAME_COL = 0                # NPC_NAME, server side
STRID_COL = 40              # NPC_STRING_ID -> LIST_NPC_S.STL key, client side


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


def stl_index(stl):
    """key -> position in stl.keys / every stl.langs row list."""
    return {k.decode("latin-1"): j for j, (k, _i) in enumerate(stl.keys)}


def plan(oro, names):
    """[(id, key, stb_before, stl_before, want)] for every row that disagrees."""
    npc = oro.Stb(NPC_STB)
    stl = oro.Stl(NPC_STL)
    idx = stl_index(stl)
    out, missing = [], []
    for i in sorted(names):
        want = names[i]
        if i >= npc.rows:
            missing.append(f"{i}: past the end of LIST_NPC.STB ({npc.rows} rows)")
            continue
        key = npc.get(i, STRID_COL).decode("latin-1").strip()
        stb_now = npc.get(i, NAME_COL).decode("latin-1")
        j = idx.get(key)
        if not key:
            missing.append(f"{i} ({want}): no STL key in col {STRID_COL}")
            continue
        if j is None:
            missing.append(f"{i} ({want}): key {key} is not in LIST_NPC_S.STL")
            continue
        stl_now = stl.langs[0][j][0].decode("latin-1")
        if stb_now != want or stl_now != want:
            out.append((i, key, stb_now, stl_now, want))
    return out, missing


def apply(oro, todo, dry):
    npc = oro.Stb(NPC_STB)
    stl = oro.Stl(NPC_STL)
    idx = stl_index(stl)
    for i, key, _sb, _sl, want in todo:
        npc.set(i, NAME_COL, want.encode("latin-1"))
        j = idx[key]
        # every language block: the shipped STLs carry five, and a name left in
        # one of them would surface for any client not on the first.
        for rows in stl.langs:
            rows[j][0] = want.encode("latin-1")
    if dry:
        return
    with open(NPC_STB, "wb") as fh:
        fh.write(npc.to_bytes())
    with open(NPC_STL, "wb") as fh:
        fh.write(stl.to_bytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()

    import rosedata as oro  # the shared data layer (was import-oro.py)
    names = dict(load("import-karkia").KARKIA_MONSTERS)

    if args.restore:
        if not os.path.exists(SIDECAR):
            sys.exit("no sidecar -- nothing to restore")
        with open(SIDECAR, encoding="utf-8") as fh:
            saved = json.load(fh)
        old = {int(k): v["was_stb"] for k, v in saved["renamed"].items()}
        todo, _missing = plan(oro, old)
        apply(oro, todo, False)
        os.remove(SIDECAR)
        print(f"restored {len(todo)} name(s); sidecar removed")
        return 0

    todo, missing = plan(oro, names)

    if args.verify:
        print(f"{len(names)} Karkia rows; {len(todo)} name(s) out of sync"
              + ("".join(f"\n  {i} {sb!r}/{sl!r} -> {w!r}"
                         for i, _k, sb, sl, w in todo[:8]) if todo else ""))
        for m in missing:
            print(f"  !! {m}")
        return 1 if todo or missing else 0

    if missing:
        print("refusing to write:")
        for m in missing:
            print("  " + m)
        return 1
    if not todo:
        print(f"{len(names)} Karkia rows, all names already correct")
        return 0

    for i, _k, sb, sl, want in todo:
        where = "stb+stl" if sb != want and sl != want else (
            "stb only" if sb != want else "stl only")
        print(f"  {i:5d}  {sb!r} -> {want!r}   ({where})")
    if args.dry_run:
        print(f"\n{len(todo)} would be renamed; dry run, nothing written")
        return 0

    record = {"renamed": {str(i): {"was_stb": sb, "was_stl": sl, "now": w}
                          for i, _k, sb, sl, w in todo}}
    apply(oro, todo, False)
    os.makedirs(os.path.dirname(SIDECAR), exist_ok=True)
    with open(SIDECAR, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1, ensure_ascii=False)

    left, missing = plan(oro, names)
    if left or missing:
        print("VERIFY FAILED after writing:")
        for i, _k, sb, sl, w in left:
            print(f"  {i}: {sb!r}/{sl!r} != {w!r}")
        for m in missing:
            print("  " + m)
        return 1
    print(f"\n{len(todo)} renamed in both LIST_NPC.STB and LIST_NPC_S.STL; "
          f"sidecar {os.path.relpath(SIDECAR, ROOT)}")
    print("restart the servers and re-bake the VFS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
