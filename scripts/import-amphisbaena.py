#!/usr/bin/env python3
"""Import Jrose's Amphisbaena (LIST_NPC 2911) with its AI as shipped, and the four monsters it summons.

The user's test of the third import route (2026-10-27, doc/importing-monsters.md): **the
source's AI taken as is**. User decisions: level 200, gold star (two-player content), and
"import the whole tree" -- every monster the AI summons comes too, each with its own
Jrose AI.

The tree (scripts/survey-monster.py, then the AI files read rule by rule)
------------------------------------------------------------------------
  2911 アンフィスバエナ "Amphisbaena", a two-headed dragon (new skeleton, model and ten
       clips), Jrose lv254 king, AI `kmd_2911.aip`. **It never aggroes**: its stop pattern
       only wanders; it fights whoever hits it (damaged pattern, 40% of hits). On a hit it
       may cast an area blast (3761) or an area Attack-down (3759) -- both 30 m around it,
       Jrose's radius, kept -- a silence on its target (3096), a self buff (3758), and
       summon an Orc Archer + a Cyclops (three events); on death it summons seven Ghost
       Seeds.
  2914 オークアーチャー "Orc Archer" (new model; crossbow built into it), `uc_stoneguard_bow.aip`:
       attacks anyone within 20 m, buffs itself (3593 Cannibal Frenzy, ours = Jrose's).
  2915 キュクロプス "Cyclops" (new model), `kh_2676.aip` -- **already ours** (Karkia's Nigaki
       runs it, with Jrose's 923 re-pointed at our 7012 Heal Ally): FILE_AI row 1121 is
       reused, the file is not copied over ours.
  2920 KMDゴーストシード "Ghost Seed" (our Ghost Seed model), `kmd_2920.aip`: wanders, and
       every 5 s transforms (60%) into a Curse Shock. Killing the seeds before they hatch is
       the mechanic.
  2921 KMDカースショック "Curse Shock" (our Elec Ghost model and its weapon 1076),
       `uc_ghost.aip`: stuns, dispels, three debuffs, two self buffs -- eight casts, every one
       the same row here as in Jrose (our Candle / Elec Ghost kit) -- kites melee, and **kills
       itself in daytime** (30% per 4 s stop tick, 20% per hit). Jrose's behaviour, kept.

What had to change to run it here
---------------------------------
  * **Skills** (`import-monster-skills.py --skills 3758,3759,3761,3096`, rows and the
    reasoning recorded there): 3758/3759/3761 blank here, imported in place with Jrose's
    column-88 statuses moved into our columns; 3096 is a nameless type-0 row that our
    Berkana Stone and others cast for nothing, so Jrose's row (a 10 s silence) lands at
    7201 and **our copy of kmd_2911.aip casts 7201** (CAST_REMAP) -- the only edit to any
    of the AI files. audit-ai-skill-refs.py maps `kmd_`/`uc_` files to Jrose and
    allowlists 7201.
  * **The Orc Archer's weapon**: Jrose's 1047 is an invisible "mob dummy bow" whose only job
    is the projectile (LIST_EFFECT 421, sound 71: the same rows here). Our 1047 is blank but
    its model object is a visible bow, so the dummy lands at DUMMY_BOW (a free row, empty
    object) through import-item.py --art-only, then takes Jrose's presentation cells.
  * **Stats are ours** (the level-200 trend x the role profiles of
    rebalance-monster-roles.py): the dragon a gold star, the summons plain roles a few
    levels under it -- Hunter (archer), Fighter (cyclops), Magician (curse shock) -- and the
    seed a fragile, evasive non-attacker (Jrose's seed has half a normal monster's HP and
    1 ATK). Summons drop nothing and give little EXP (the Cerberus Hellhounds' rule).
  * Each row is a copy of TEMPLATE for the cells we do not set, with Jrose's cosmetic
    cells (speeds, size, ranges, sounds, glow, height; the sound and effect rows are the
    same here) and NPC_HAND_HIT_EFFECT 403 on the bare-handed ones.

Not spawned anywhere. Test: `/mon 2911 1` with a level-200 character (or two), hit it.

    python scripts/import-amphisbaena.py --dry-run
    python scripts/import-amphisbaena.py
    python scripts/import-amphisbaena.py --verify

Then: audit-ai-skill-refs.py, audit-ai-monster-refs.py, add-dds-mipmaps.py over the new
texture folders, bake, restart the servers. Originals: build/amphisbaena/.
"""
import argparse
import os
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import rosedata as oro  # noqa: E402
from rosefmt import aip  # noqa: E402

DEFAULT_SRC = r"C:\Users\Thomas\Desktop\Testclients\Jrose"
BUILD_DIR = os.path.join(ROOT, "build", "amphisbaena")

NPC_STB_REL = r"3DDATA\STB\LIST_NPC.STB"
NPC_STL_REL = r"3DDATA\STB\LIST_NPC_S.STL"
NPC_CHR_REL = r"3DDATA\NPC\LIST_NPC.CHR"
PART_ZSC_REL = r"3DDATA\NPC\PART_NPC.ZSC"
SKILL_STB_REL = r"3DDATA\STB\LIST_SKILL.STB"
SKILL_STL_REL = r"3DDATA\STB\LIST_SKILL_S.STL"
SOUND_STB_REL = r"3DDATA\STB\FILE_SOUND.STB"
AI_STB_REL = r"3DDATA\STB\FILE_AI.STB"
AI_DIR_REL = r"3DDATA\AI"
WEAPON_STB_REL = r"3DDATA\STB\LIST_WEAPON.STB"
WEAPON_ZSC_REL = r"3DDATA\WEAPON\LIST_WEAPON.ZSC"
WEAPON_STL_REL = r"3DDATA\STB\LIST_WEAPON_S.STL"
TRACKED = [NPC_STB_REL, NPC_STL_REL, NPC_CHR_REL, PART_ZSC_REL, SKILL_STB_REL, SKILL_STL_REL,
           AI_STB_REL, WEAPON_STB_REL, WEAPON_ZSC_REL, WEAPON_STL_REL]

C_NAME, C_MODEL, C_WALK, C_RUN, C_SIZE, C_RWEAPON, C_LWEAPON, C_LEVEL, C_HP, C_ATK, C_HIT, \
    C_DEF, C_RES, C_AVOID, C_ASPD, C_MAGIC, C_AI, C_EXP, C_DROP, C_MONEY, C_DROPRATE = range(21)
C_TARGET, C_RANGE, C_TYPE, C_HAND_FX, C_GLOW, C_DEADEVENT, C_HEIGHT = 25, 26, 27, 33, 39, 41, 42
TEMPLATE = 1588                     # Melt Dizzle: lv200 bare-handed Warrior
# Jrose's cosmetic cells, copied verbatim (sounds 30-32/35, hit material 28, death fx 34)
JROSE_COLS = (C_WALK, C_RUN, C_SIZE, C_MAGIC, C_RANGE, 28, 29, 30, 31, 32, 34, 35, C_GLOW, C_HEIGHT)
SOUND_COLS = (30, 31, 32, 35)

# ---- the dummy bow (the Orc Archer's projectile)
DUMMY_BOW = 1018                    # blank, no model object
DUMMY_BOW_SRC = 1047                # Jrose's "MOB dummy bow"
DUMMY_BOW_TEMPLATE = 1076           # Candle Ghost Weapons: a monster weapon row of ours
DUMMY_BOW_NAME = "Mob Dummy Bow"
DUMMY_BOW_CELLS = {1: r"WEAPON\mobwpn\dummy\dummy_bow.txt", 8: 50, 38: 421, 41: 71}   # Jrose's

# ---- the AI files (FILE_AI rows appended; the Cyclops reuses ours)
AI_FILES = {   # monster: (our FILE_AI row, file) -- None row = an existing row of ours
    2911: (2261, "kmd_2911.aip"),
    2914: (2262, "uc_stoneguard_bow.aip"),
    2915: (1121, None),             # kh_2676.aip, ours since Karkia (923 -> 7012)
    2920: (2263, "kmd_2920.aip"),
    2921: (2264, "uc_ghost.aip"),
}
CAST_REMAP = {"kmd_2911.aip": {3096: 7201}}   # see import-monster-skills.py
SKILL_IDS = (3758, 3759, 3761, 3096)          # import-monster-skills.py --skills
SKILL_NAMES = {   # player-facing names (LMobSkill<row>), as name-monster-skills-players.py does
    3758: ("Twin Fury", "Both heads roar, raising its attack and defense."),
    3759: ("Withering Roar", "A roar that strikes everyone nearby and saps their attack."),
    3761: ("Twin Cataclysm", "Both heads unleash a blast that strikes everyone nearby."),
    7201: ("Hushing Gaze", "A stare that silences its target."),
}
AT_LEVEL = 0                        # (unused)

# ---- the monsters: name, STL key, stats (trend at 200 x role; see the docstring)
# trend at 200 (27 peers, 2026-10-27): HP 45/lv, ATK 1141, HIT 492, DEF 655, RES 617,
# AVOID 350, ASPD 96, EXP 1525
MONSTERS = {
    2911: ("Amphisbaena", "LKMDMOB2911", {          # gold star: 4.0 1.35 1.2 1.2 1.15 1.0 1.05
        C_LEVEL: 200, C_HP: 180, C_ATK: 1540, C_HIT: 566, C_DEF: 786, C_RES: 740,
        C_AVOID: 350, C_ASPD: 101, C_TYPE: 10, C_EXP: 6000, C_HAND_FX: 403}),
    2914: ("Orc Archer", "LKMDMOB2914", {           # Hunter: 0.9 1.1 0.9 0.95 1.1 1.0 0.85
        C_LEVEL: 196, C_HP: 41, C_ATK: 1255, C_HIT: 541, C_DEF: 590, C_RES: 586,
        C_AVOID: 350, C_ASPD: 82, C_TYPE: 6, C_EXP: 300, C_RWEAPON: DUMMY_BOW,
        C_DROP: 0, C_MONEY: 0, C_DROPRATE: 0}),
    2915: ("Cyclops", "LKMDMOB2915", {              # Fighter: 1.0 1.05 1.0 0.95 1.05 1.05 1.05
        C_LEVEL: 196, C_HP: 45, C_ATK: 1198, C_HIT: 517, C_DEF: 655, C_RES: 586,
        C_AVOID: 368, C_ASPD: 101, C_TYPE: 3, C_EXP: 300, C_HAND_FX: 403,
        C_DROP: 0, C_MONEY: 0, C_DROPRATE: 0}),
    2920: ("Ghost Seed", "LKMDMOB2920", {           # Jrose: ~half HP, 1 ATK, evasive
        C_LEVEL: 196, C_HP: 25, C_ATK: 1, C_HIT: 1, C_DEF: 655, C_RES: 617,
        C_AVOID: 450, C_ASPD: 100, C_TYPE: 1, C_EXP: 50, C_HAND_FX: 403,
        C_DROP: 0, C_MONEY: 0, C_DROPRATE: 0}),
    2921: ("Curse Shock", "LKMDMOB2921", {          # Magician: 0.85 1.05 0.8 1.4 1.0 1.0 0.9
        C_LEVEL: 196, C_HP: 38, C_ATK: 1198, C_HIT: 492, C_DEF: 524, C_RES: 864,
        C_AVOID: 350, C_ASPD: 86, C_TYPE: 7, C_EXP: 300, C_RWEAPON: 1076,
        C_DROP: 0, C_MONEY: 0, C_DROPRATE: 0}),
}


def load(name, fname):
    """Import a sibling script as a module without running its main()."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fname))
    mod = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, [fname, "--help"]
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    finally:
        sys.argv = argv
    return mod


def P(root, rel):
    return os.path.join(root, rel.replace("\\", "/"))


def find_ci(root, rel):
    cur = root
    for part in rel.replace("\\", "/").split("/"):
        hit = [f for f in os.listdir(cur) if f.lower() == part.lower()] if os.path.isdir(cur) else []
        cur = os.path.join(cur, hit[0] if hit else part)
    return cur


def b(v):
    return str(v).encode("latin-1")


def keep_originals(ours):
    for rel in TRACKED:
        src = P(ours, rel)
        dst = os.path.join(BUILD_DIR, "orig", rel.replace("\\", "/"))
        if os.path.isfile(src) and not os.path.isfile(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)


def sweep_baks(ours):
    moved = 0
    for rel in TRACKED:
        folder, base = os.path.split(P(ours, rel))
        for f in os.listdir(folder):
            if f.lower().startswith(base.lower() + ".") and f.lower().endswith(".bak"):
                dest = os.path.join(BUILD_DIR, "bak", f)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.move(os.path.join(folder, f), dest)
                moved += 1
    if moved:
        print(f"    {'.bak files':26s} {moved} moved to build/amphisbaena/bak")


def write_if_changed(path, blob, dry):
    if os.path.isfile(path) and open(path, "rb").read() == blob:
        return False
    if not dry:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(blob)
    return True


def run(cmd, dry, what):
    if dry:
        cmd = cmd + ["--dry-run"]
    print(f"    {what}")
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    for line in (res.stdout + res.stderr).strip().splitlines()[-8:]:
        print("        " + line)
    if res.returncode:
        raise SystemExit(f"{what} failed")


# ---------------------------------------------------------------------- pieces
def dummy_bow(ours, src, dry):
    w = oro.Stb(P(ours, WEAPON_STB_REL))
    cur = w.get(DUMMY_BOW, C_NAME).decode("latin-1").strip()
    if cur not in ("", DUMMY_BOW_NAME):
        raise SystemExit(f"our LIST_WEAPON row {DUMMY_BOW} is {cur!r}")
    if not cur:
        icon = w.get(DUMMY_BOW_TEMPLATE, 9).decode().strip()   # monster weapons have none
        run([sys.executable, os.path.join(HERE, "import-item.py"), "--type", "weapon",
             "--source", src, "--source-row", str(DUMMY_BOW_SRC), "--art-only",
             "--template-row", str(DUMMY_BOW_TEMPLATE), "--name", DUMMY_BOW_NAME,
             "--desc", "The Orc Archer's projectile carrier (no model).",
             "--target-row", str(DUMMY_BOW),
             "--allow-placeholder"]                  # invisible on purpose: the arrow is all
            + (["--icon", icon] if icon else []),
            dry, f"import-item.py weapon {DUMMY_BOW_SRC} -> {DUMMY_BOW}")
        if dry:
            return
        w = oro.Stb(P(ours, WEAPON_STB_REL))
    # a monster's weapon row is presentation only: Jrose's cells, nothing else
    key_col = w.key_column()
    want = [b""] * w.cols
    want[C_NAME] = DUMMY_BOW_NAME.encode()
    for c, v in DUMMY_BOW_CELLS.items():
        want[c] = b(v)
    if key_col is not None:
        want[key_col] = w.d[DUMMY_BOW][key_col]
    if w.d[DUMMY_BOW] != want:
        w.d[DUMMY_BOW] = want
        w.save(dry, keep_backup=False)
        print(f"    {'LIST_WEAPON.STB':26s} row {DUMMY_BOW} = Jrose's presentation cells")


def remapped_ai(blob, remap):
    h, t, pats, tail = aip.parse(blob)
    out = []
    for pn, evs in pats:
        nevs = []
        for en, conds, acts in evs:
            nacts = []
            for a in acts:
                if (aip.record_type(a) & 0xFF) - 1 == 24:
                    sid = struct.unpack_from("<h", a, 10)[0]
                    if sid in remap:
                        a = bytearray(a)
                        struct.pack_into("<h", a, 10, remap[sid])
                        a = bytes(a)
                nacts.append(a)
            nevs.append((en, conds, nacts))
        out.append((pn, nevs))
    return aip.build(h, t, out, tail)


def ai_blobs(src):
    """{our file name: bytes} for the AI files that come across."""
    out = {}
    for npc, (_row, fn) in AI_FILES.items():
        if fn is None:
            continue
        blob = open(find_ci(src, rf"3Ddata\AI\{fn}"), "rb").read()
        if fn in CAST_REMAP:
            blob = remapped_ai(blob, CAST_REMAP[fn])
        out[fn.upper()] = blob
    return out


def npc_row(d_npc, s_npc, r):
    name, strid, stats = MONSTERS[r]
    row = list(d_npc.d[TEMPLATE])
    row[C_NAME] = name.encode()
    row[C_MODEL] = s_npc.get(r, C_MODEL)
    for c in (C_RWEAPON, C_LWEAPON, C_TARGET, C_DEADEVENT, C_HAND_FX, *oro.NPC_SELL_TAB_COLS):
        row[c] = b""
    for c in JROSE_COLS:
        row[c] = s_npc.get(r, c).strip()
    for c, v in stats.items():
        row[c] = b(v)
    row[C_AI] = b(AI_FILES[r][0])
    row[oro.NPC_STRID_COL] = strid.encode()
    row[oro.NPC_PVP_COL] = oro.DEFAULT_PVP_STATE
    if d_npc.get(r, C_NAME).strip():
        row[C_EXP] = d_npc.get(r, C_EXP)            # rebalance-exp-rewards.py owns it
    return row


def check_sounds(ours, src, s_npc):
    """Jrose's sound cells must name the same files here."""
    of, jf = oro.Stb(P(ours, SOUND_STB_REL)), oro.Stb(P(src, SOUND_STB_REL))
    for r in MONSTERS:
        for c in SOUND_COLS:
            v = s_npc.get(r, c).strip()
            if v.isdigit() and of.get(int(v), 0).lower() != jf.get(int(v), 0).lower():
                raise SystemExit(f"Jrose {r} col {c} sound {v} is {jf.get(int(v), 0)!r} there, "
                                 f"{of.get(int(v), 0)!r} here")


def monsters(ours, src, dry):
    s_npc, d_npc = oro.Stb(P(src, NPC_STB_REL), "cp932"), oro.Stb(P(ours, NPC_STB_REL))
    check_sounds(ours, src, s_npc)
    dirty = False
    for r, (name, _k, _s) in MONSTERS.items():
        cur = d_npc.get(r, C_NAME).decode("latin-1").strip()
        if cur and cur != name:
            raise SystemExit(f"our LIST_NPC row {r} is {cur!r}")
        want = npc_row(d_npc, s_npc, r)
        if d_npc.d[r] != want:
            d_npc.d[r] = want
            dirty = True
            print(f"    {'LIST_NPC.STB':26s} row {r} {name}")
    if dirty:
        d_npc.save(dry, keep_backup=False)
    stl = oro.Stl(P(ours, NPC_STL_REL))
    added = 0
    for r, (name, strid, _s) in MONSTERS.items():
        if not stl.has(strid):
            stl.append(strid, r, name)
            added += 1
    if added:
        stl.save(dry, keep_backup=False)
        print(f"    {'LIST_NPC_S.STL':26s} +{added} keys")
    oro.import_characters(list(MONSTERS), ours, src, dry, "Amphisbaena tree")


def skills(ours, dry):
    run([sys.executable, os.path.join(HERE, "import-monster-skills.py"),
         "--skills", ",".join(map(str, SKILL_IDS))], dry,
        f"import-monster-skills.py --skills {','.join(map(str, SKILL_IDS))}")
    if dry:
        return
    sk = oro.Stb(P(ours, SKILL_STB_REL))
    skl = oro.Stl(P(ours, SKILL_STL_REL))
    sk_dirty = stl_dirty = False
    for row, (name, desc) in SKILL_NAMES.items():
        key = f"LMobSkill{row}"
        if sk.get(row, 86) != key.encode():
            sk.set(row, 86, key.encode())
            sk_dirty = True
        if not skl.has(key):
            skl.append(key, row, name, desc)
            stl_dirty = True
    if sk_dirty:
        sk.save(dry, keep_backup=False)
    if stl_dirty:
        skl.save(dry, keep_backup=False)
    print(f"    {'LIST_SKILL names':26s} {len(SKILL_NAMES)} rows keyed LMobSkill<row>")


def ai(ours, src, dry):
    fai = oro.Stb(P(ours, AI_STB_REL))
    dirty = False
    for npc, (row, fn) in AI_FILES.items():
        if fn is None:
            if not fai.get(row, 0).strip():
                raise SystemExit(f"our FILE_AI row {row} is blank")
            continue
        cell = rf"3DDATA\AI\{fn.upper()}".encode("latin-1")
        if fai.rows <= row:
            fai.grow_to(row + 1)
        if fai.get(row, 0) != cell:
            if fai.get(row, 0).strip():
                raise SystemExit(f"our FILE_AI row {row} is {fai.get(row, 0)!r}")
            fai.set(row, 0, cell)
            dirty = True
            print(f"    {'FILE_AI.STB':26s} row {row} = {fn.upper()}")
    if dirty:
        fai.save(dry, keep_backup=False)
    for fn, blob in ai_blobs(src).items():
        path = os.path.join(P(ours, AI_DIR_REL), fn)
        if os.path.isfile(find_ci(ours, rf"3DDATA\AI\{fn}")) and not os.path.isfile(path):
            raise SystemExit(f"{fn} exists here under another case -- refusing")
        changed = write_if_changed(path, blob, dry)
        print(f"    {fn:26s} {'written' if changed else 'in place'}"
              f"{' (casts re-pointed)' if fn.lower() in CAST_REMAP else ''}")


# ---------------------------------------------------------------------- verify
def verify(ours, src):
    bad = []

    def check(ok, what):
        print(f"    {'ok  ' if ok else 'FAIL'} {what}")
        if not ok:
            bad.append(what)

    s_npc, d_npc = oro.Stb(P(src, NPC_STB_REL), "cp932"), oro.Stb(P(ours, NPC_STB_REL))
    chr_ = oro.Chr(P(ours, NPC_CHR_REL))
    zsc = oro.Zsc(P(ours, PART_ZSC_REL))
    stl = oro.Stl(P(ours, NPC_STL_REL))
    for r, (name, strid, _s) in MONSTERS.items():
        check(d_npc.d[r][:C_EXP] == npc_row(d_npc, s_npc, r)[:C_EXP]
              and d_npc.d[r][C_DROP:] == npc_row(d_npc, s_npc, r)[C_DROP:], f"LIST_NPC {r} {name}")
        check(stl.has(strid), f"LIST_NPC_S {strid}")
        e = chr_.chars[r] if r < len(chr_.chars) else None
        check(e is not None, f"LIST_NPC.CHR {r}")
        if e:
            files = [chr_.skeletons[e["skel"]]] + [chr_.motions[a] for _, a in e["anims"]
                                                    if a < len(chr_.motions)]
            for m in e["models"]:
                for mi, ti, _ in zsc.objects[m][1]:
                    files += [zsc.meshes[mi], zsc.materials[ti][0]]
            missing = [f for f in files if not os.path.isfile(find_ci(ours, f.decode("latin-1")))]
            check(not missing, f"  model files ({len(files)})" + (f": {missing[:2]}" if missing else ""))
    w = oro.Stb(P(ours, WEAPON_STB_REL))
    check(w.get(DUMMY_BOW, C_NAME) == DUMMY_BOW_NAME.encode() and w.get(DUMMY_BOW, 38) == b"421",
          f"LIST_WEAPON {DUMMY_BOW} dummy bow (projectile 421)")
    sk = oro.Stb(P(ours, SKILL_STB_REL))
    for row in SKILL_NAMES:
        check(sk.get(row, 5).strip() != b"" and sk.get(row, 86) == f"LMobSkill{row}".encode(),
              f"LIST_SKILL {row} {SKILL_NAMES[row][0]}")
    fai = oro.Stb(P(ours, AI_STB_REL))
    blobs = ai_blobs(src)
    for npc, (row, fn) in AI_FILES.items():
        if fn is None:
            check(fai.get(row, 0).strip() != b"", f"FILE_AI {row} (ours) for {npc}")
            continue
        check(fai.get(row, 0) == rf"3DDATA\AI\{fn.upper()}".encode(), f"FILE_AI {row} = {fn}")
        p = os.path.join(P(ours, AI_DIR_REL), fn.upper())
        check(os.path.isfile(p) and open(p, "rb").read() == blobs[fn.upper()], f"{fn} as shipped"
              + (" (+ re-pointed casts)" if fn in CAST_REMAP else ""))
    leftovers = [rel for rel in TRACKED
                 if any(f.lower().endswith(".bak") and f.lower().startswith(os.path.basename(P(ours, rel)).lower())
                        for f in os.listdir(os.path.dirname(P(ours, rel))))]
    check(not leftovers, "no .bak left beside the tables")
    print(f"{'OK' if not bad else f'{len(bad)} problem(s)'}")
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", default=DEFAULT_SRC, help="the Jrose dump (holds 3Ddata)")
    ap.add_argument("--ours", default=os.path.join(ROOT, "data"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.verify:
        return verify(args.ours, args.src)
    if not args.dry_run:
        keep_originals(args.ours)
    print("the dummy bow")
    dummy_bow(args.ours, args.src, args.dry_run)
    print("the skills")
    skills(args.ours, args.dry_run)
    print("the monsters")
    monsters(args.ours, args.src, args.dry_run)
    print("the AI")
    ai(args.ours, args.src, args.dry_run)
    if not args.dry_run:
        sweep_baks(args.ours)
    print("dry run, nothing written" if args.dry_run else "done -- run --verify")
    return 0


if __name__ == "__main__":
    sys.exit(main())
