#!/usr/bin/env python3
"""Import tsuki's Necromancer (LIST_NPC 2414) with its Red Tetric Staff, a lv120 test kit.

The user's pick from the tsuki monster survey (2026-10-24): of five candidates it was the
only one with a model of its own (the other four are reskins on rigs we already ship), so
"the more interesting one". Level ~120 for now, to fight it with the user's test character;
"we can author other stats later".

What tsuki has, and what it does not
------------------------------------
  * **The row.** tsuki 2414 "Necromancer", level 240 on tsuki's scale, AI row 443 -- the
    same AI number tsuki gives its mummies, zombies, Kromtaurs and the Raknu Prisoner, so
    a shared placeholder rather than a kit (our 443 is the prisoner's own AI). Our row 2414
    is blank with no CHR entry, so it lands at tsuki's number, as Cerberus did. Every stat
    is ours (STATS); the row is a copy of TEMPLATE (Ruper Wizard, a lv102 Magician:
    voice, death sound, target type), never tsuki's cells.
  * **The model is all new**: NPC\\ETC\\NECROMANCER (skeleton, body + head, 2 textures)
    and MOTION\\NPC\\NECROMANCER (8 clips). rosedata.import_characters brings the CHR
    entry across with every index remapped. Nothing is missing from tsuki.
  * **The staff.** tsuki's weapon row 1050 "Red Tetric Staff" is a bare monster-weapon
    row: our Dark Staff's mesh (MAGIC\\MST26\\MST26.ZMS, byte-identical) with a red
    texture, MOB02.DDS. It comes in through import-item.py --art-only as a real item at
    STAFF_ROW (blank, in the staff variant band, under the 999 ceiling so it can drop or
    be a quest reward later): stats cloned from Dark Full Moon Rod (776, req lv120), the
    Dark Staff's icon (same mesh). Its hit effect and sounds are the staff family's.
  * **No AI, no sounds, no skills** in tsuki. The AI and the skill are written here.

The animation profile (what the clips say the kit was)
------------------------------------------------------
  * attack (ATT2): a melee staff swing, hit at frame 20.
  * cast (ATT001, slots 6 and 8) and release (ATT01, slots 7 and 9): ONE skill, both
    pairs. The release carries 35/10 at frames 7/9, 35/20 at 12/14 and 35/25 at 18/20:
    the retail multi-hit strike. 10 and 20 show the skill's two "hit dummy" effects on the
    target (LIST_SKILL cols 77/80), 25 lands it (col 74) -- and the server counts 10, 20
    and 25 as three attack frames, so the damage is x3 (Get_SkillDAMAGE: iDamage *=
    wHitCNT), as Pincer Strike (3513) is built.
  * Neither clip carries a casting-effect frame (44/64/74/84), so CLIP_EVENTS adds two to
    our copies (only this monster uses them): 44 early in the cast (the dark swirl) and 64
    just after the last hit (the drain streams on the Necromancer).

The kit: Soul Siphon (LIST_SKILL SIPHON)
----------------------------------------
Pincer Strike's row (3513: type 3, three hits, dummy hits) made a drain: **type 19**, the
type-3 hit plus an ability gain on the caster (Skill_START_19 -> Skill_ApplyIngSTATUS on
the attacker; col 21 AT_HP, col 22 the flat amount, scaled (INT + 300) / 315 and a
monster's INT is its level, so 200 heals ~270, about 6% of its HP). Magic damage (col 15
= 2), reach SIPHON_RANGE. The heal reaches clients through an effect packet the game server
now sends on the caster (Skill_START_19, 2026-10-24): before it, the server healed and no
client ever showed it. Effects, all one-shot: mummy_s_casting01 while casting (an
undead caster's), _runasujung_black_breakdown01 on the two dummy hits, _s_bloodout_hit_01
on the last (the Dealer drain's hit), _drain_01 on the caster. The first cut used two
looping effects (_PumpkinDark_Skill, scavenger_dark01): an effect a skill attaches to a
character goes only when it finishes, so the dark aura stayed under the player's feet. SIPHON_POWER is per hit (x3): 35 lands ~400 on a level-120
average Soldier and ~350 on a Mage (26% of its HP), ~2.5x its swing, about one cast per
8-10 s kill (combat sim, typical play, 2026-10-24); 60 landed 645 / 554, too hot for a
plain field Magician.

The AI
------
A plain Magician that swings its staff, plus the siphon: cast while chasing a target that
keeps its distance, every SIPHON_EVERY hits taken (misses count, and each drain counts one
on itself), and once -- with a local line -- when it drops under half HP, at least
DESPERATE_GAP hits after the last. Every cast is gated on the target already being in reach. Spawned
by /mon or a regen point, so no "created" reliance: the idle search is in "stop".

Stats
-----
The live level trend at 120 (median of plain-role spawned monsters within +/-10 levels, 19
rows, 2026-10-24) times the Magician profile of rebalance-monster-roles.py (HP 0.85, ATK
1.05, DEF 0.8, RES 1.4, ASPD 0.9), frozen here so a re-run does not drift. EXP is the
trend median, seeded only (rebalance-exp-rewards.py owns the column). Drop table 375 (the
Basilisk's, lv121) for now. Mark 7, Magician. The row is in balance-trend-exclude.py.

Not spawned anywhere (tsuki never spawned it either: none of its 9,934 regen points names
it). Test: `/mon 2414 1`, a character of about level 120 (a 240 resists and takes 0 from
a level-120 monster's magic: doc/making-monsters.md, "the level gate").

    python scripts/import-necromancer.py --dry-run
    python scripts/import-necromancer.py
    python scripts/import-necromancer.py --verify

Then: audit-ai-skill-refs.py, audit-ai-monster-refs.py, add-dds-mipmaps.py over the new
texture folders, bake, restart the servers (LIST_NPC, LIST_NPC.CHR, LIST_SKILL, FILE_AI,
AI_s.STB and the .AIP are server data). Originals of every table touched: build/necromancer/.
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
from rosefmt import zmo as rfzmo  # noqa: E402

DEFAULT_SRC = r"C:\Users\Thomas\Desktop\Testclients\tsuki"
BUILD_DIR = os.path.join(ROOT, "build", "necromancer")

NPC_STB_REL = r"3DDATA\STB\LIST_NPC.STB"
NPC_STL_REL = r"3DDATA\STB\LIST_NPC_S.STL"
NPC_CHR_REL = r"3DDATA\NPC\LIST_NPC.CHR"
PART_ZSC_REL = r"3DDATA\NPC\PART_NPC.ZSC"
SKILL_STB_REL = r"3DDATA\STB\LIST_SKILL.STB"
SKILL_STL_REL = r"3DDATA\STB\LIST_SKILL_S.STL"
AI_STB_REL = r"3DDATA\STB\FILE_AI.STB"
AI_STR_REL = r"3DDATA\AI\AI_s.STB"
AI_DIR_REL = r"3DDATA\AI"
WEAPON_STB_REL = r"3DDATA\STB\LIST_WEAPON.STB"
WEAPON_ZSC_REL = r"3DDATA\WEAPON\LIST_WEAPON.ZSC"
WEAPON_STL_REL = r"3DDATA\STB\LIST_WEAPON_S.STL"
TRACKED = [NPC_STB_REL, NPC_STL_REL, NPC_CHR_REL, PART_ZSC_REL, SKILL_STB_REL, SKILL_STL_REL,
           AI_STB_REL, AI_STR_REL, WEAPON_STB_REL, WEAPON_ZSC_REL, WEAPON_STL_REL]

# ---- the monster
NECRO = 2414                        # tsuki's row; blank here, no CHR entry
NECRO_NAME = "Necromancer"
NECRO_STRID = "LNCRMOB2414"
TEMPLATE = 347                      # Ruper Wizard: lv102 Magician, voice + death sound
C_NAME, C_MODEL, C_WALK, C_RUN, C_SIZE, C_RWEAPON, C_LWEAPON, C_LEVEL, C_HP, C_ATK, C_HIT, \
    C_DEF, C_RES, C_AVOID, C_ASPD, C_MAGIC, C_AI, C_EXP, C_DROP, C_MONEY, C_DROPRATE = range(21)
C_TARGET, C_RANGE, C_TYPE, C_DEADEVENT, C_HEIGHT = 25, 26, 27, 41, 42
TYPE_MAGICIAN = 7
AI_ROW = 2258                       # one past the end of FILE_AI
AI_FILE = "NECROMANCER.AIP"
STATS = {
    C_MODEL: "necromancer.mon",     # /mon refuses a row with no model text (cheatcmd.cpp)
    C_WALK: 200, C_RUN: 600,        # tsuki's 200 / 1000 sprinted; a caster jogs
    C_SIZE: 190, C_HEIGHT: 325,     # tsuki's
    C_RWEAPON: None, C_LWEAPON: "", # the staff (STAFF_ROW), filled in at build time
    C_LEVEL: 120, C_HP: 38, C_ATK: 604, C_HIT: 299, C_DEF: 282, C_RES: 459,
    C_AVOID: 176, C_ASPD: 92, C_MAGIC: 1, C_AI: AI_ROW, C_EXP: 295,
    C_DROP: 375, C_MONEY: 20, C_DROPRATE: 60,
    C_RANGE: 250,                   # melee staff swing (the template's 1500 is a bolt)
    C_TYPE: TYPE_MAGICIAN,
}

# ---- the staff
STAFF_ROW = 782                     # blank: the staff variant band ends at 781
STAFF_NAME = "Red Tetric Staff"
STAFF_DESC = "A staff of blood-red wood, carried by the Necromancer."
STAFF_SRC_ROW = 1050                # tsuki LIST_WEAPON
STAFF_TEMPLATE = 776                # Dark Full Moon Rod, req lv120
STAFF_ICON = 1298                   # the Dark Staff's (same mesh)

# ---- the skill
SIPHON = 7177                       # one past the end of LIST_SKILL
SIPHON_NAME = "Soul Siphon"
SIPHON_STRID = "LMobSkill7177"      # name-monster-skills-players.py's key convention
SIPHON_DESC = "Strikes the target three times with dark magic and drains its life."
SIPHON_SRC = 3513                   # Pincer Strike: type 3, three hits, two dummy hits
SIPHON_MOTION = 8                   # cast ATT001 on slot 8, release ATT01 on slot 9
SIPHON_RANGE = 1000                 # cm
SIPHON_POWER = 35                   # per hit (x3): ~2.5x its swing, sim 2026-10-24
SIPHON_HEAL = 200                   # flat AT_HP on the caster, x (INT + 300) / 315
AT_HP = 16
SK_NAME, SK_LINE, SK_TYPE, SK_RANGE, SK_POWER, SK_DMGTYPE = 0, 1, 5, 6, 9, 15
SK_STL_KEY, SK_DESC = 86, 87
# All one-shot: an effect a skill attaches to a character is removed only when it
# finishes, and a looping one never does. scavenger_dark01 (1376) and _PumpkinDark_Skill
# (1367) loop forever: the first test left a dark aura under the player's feet.
FX_CAST, FX_DARK_BURST, FX_BLOOD_OUT, FX_DRAIN = 1381, 1302, 1602, 2006
SND_CAST, SND_HIT, SND_DUMMY0, SND_DUMMY1 = 1001, 142, 137, 138
SIPHON_CELLS = {
    SK_TYPE: 19, SK_RANGE: SIPHON_RANGE, SK_POWER: SIPHON_POWER, SK_DMGTYPE: 2,
    21: AT_HP, 22: SIPHON_HEAL,
    29: 2,                                          # action mode: magic
    56: FX_CAST, 57: 999, 58: SND_CAST,       # casting effect 0: event 44
    59: FX_DRAIN, 60: 999, 61: "",                  # casting effect 1: event 64
    69: 100,                                        # release at full speed
    74: FX_BLOOD_OUT, 75: 999, 76: SND_HIT,         # the hit, event 25
    77: FX_DARK_BURST, 78: 999, 79: SND_DUMMY0,     # hit dummy 0, event 10
    80: FX_DARK_BURST, 81: 999, 82: SND_DUMMY1,     # hit dummy 1, event 20
}

# ---- casting-effect frames added to our copies of its clips (both new, Necromancer-only)
CLIP_EVENTS = {
    r"3Ddata\MOTION\NPC\NECROMANCER\ATT001.ZMO": {2: 44},    # 38 frames, none of its own
    r"3Ddata\MOTION\NPC\NECROMANCER\ATT01.ZMO": {21: 64},    # after the 25 at frame 20
}

# ---- the AI
SEEK, LEASH = 12, 40                # m
SIPHON_REACH = 9                    # m, inside SIPHON_RANGE
SIPHON_CHASE = (4, 25)              # m, %: while chasing a target at least this far
SIPHON_EVERY = 10                   # hits taken between two (monster var 2); 4 was a cast
                                    # every 2-3 s against a dual-sword Hawker (first test)
DESPERATE_HP = 50                   # %: the once-per-life siphon with a line (var 3)
DESPERATE_GAP = 3                   # hits since the last siphon before that one
LINES = {   # AI_s.STB, appended; AIACT28 kind 0 = local chat
    "siphon": "Your life is mine!",
    "kill": "Another soul for my collection.",
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


mon = load("audit_ai_monster_refs", "audit-ai-monster-refs.py")   # .aip codec
heb = load("import_hebarn", "import-hebarn.py")       # AI condition/action encoders


def P(root, rel):
    return os.path.join(root, rel.replace("\\", "/"))


def b(v):
    return str(v).encode("latin-1")


def keep_originals(ours):
    """Snapshot every table this script touches, once, before the first write."""
    for rel in TRACKED:
        src = P(ours, rel)
        dst = os.path.join(BUILD_DIR, "orig", rel.replace("\\", "/"))
        if os.path.isfile(src) and not os.path.isfile(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)


def sweep_baks(ours):
    """Move the codecs' and import-item.py's .bak files out of data/ -- pack.ps1 refuses
    to bake while one sits there."""
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
        print(f"    {'.bak files':26s} {moved} moved to build/necromancer/bak")


def clip_with_events(blob, events):
    """rosefmt.zmo.with_events, after opening an empty event table. tsuki's ATT001 has
    a 3ZMO trailer laid out exactly like ATT01's -- room for one short per frame -- but
    its count field reads 0, so with_events sees no frames; the count is set to the
    clip's frame count first (the slots are already zero)."""
    _, frames, _ = rfzmo.read_header(blob)
    base, ev = rfzmo.events(blob)
    if base is not None and not ev:
        if base + 2 * frames > len(blob) - 8:
            raise SystemExit("clip trailer has no room for its events")
        out = bytearray(blob)
        struct.pack_into("<H", out, base - 2, frames)
        blob = bytes(out)
    return rfzmo.with_events(blob, events)


def write_if_changed(path, blob, dry):
    if os.path.isfile(path) and open(path, "rb").read() == blob:
        return False
    if not dry:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(blob)
    return True


# ---------------------------------------------------------------------- the staff
def staff(ours, src, dry):
    w = oro.Stb(P(ours, WEAPON_STB_REL))
    cur = w.get(STAFF_ROW, C_NAME).decode("latin-1").strip()
    if cur == STAFF_NAME:
        print(f"    {'LIST_WEAPON.STB':26s} row {STAFF_ROW} {STAFF_NAME} already in place")
        return
    if cur:
        raise SystemExit(f"our LIST_WEAPON row {STAFF_ROW} is {cur!r}")
    cmd = [sys.executable, os.path.join(HERE, "import-item.py"), "--type", "weapon",
           "--source", src, "--source-row", str(STAFF_SRC_ROW), "--art-only",
           "--template-row", str(STAFF_TEMPLATE), "--name", STAFF_NAME, "--desc", STAFF_DESC,
           "--icon", str(STAFF_ICON), "--target-row", str(STAFF_ROW)]
    if dry:
        cmd.append("--dry-run")
    print(f"    {'import-item.py':26s} weapon {STAFF_SRC_ROW} -> {STAFF_ROW}")
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    for line in (res.stdout + res.stderr).strip().splitlines():
        print("        " + line)
    if res.returncode:
        raise SystemExit("import-item.py failed")


# ---------------------------------------------------------------------- the AI
def build_ai(L):
    def siphon():
        return [heb.a_cast(SIPHON, SIPHON_MOTION), heb.a_set_var(2, 0)]
    pats = [
        (heb.pat("created"), [heb.ev("hunt", [heb.c_enemies_near(SEEK)], [heb.a_attack_found()])]),
        (heb.pat("stop"), [
            heb.ev("go home", [heb.c_moved_from_spawn(LEASH)], [heb.a_run_home(3)]),
            heb.ev("seek", [heb.c_enemies_near(SEEK)], [heb.a_attack_found()]),
        ]),
        (heb.pat("attack move"), [       # runs only while it moves towards its target
            heb.ev("leash", [heb.c_moved_from_spawn(LEASH)], [heb.a_run_home(3)]),
            heb.ev("siphon", [heb.c_chance(SIPHON_CHASE[1]), heb.c_target_at_least(SIPHON_CHASE[0]),
                              heb.c_target_within(SIPHON_REACH)], siphon()),
        ]),
        (heb.pat("damaged"), [           # first match wins; var 2 = hits, var 3 = the line
            heb.ev("desperate", [heb.c_hp_at_most(DESPERATE_HP), heb.c_var(3, 0),
                                 heb.c_var(2, DESPERATE_GAP, 2),
                                 heb.c_target_within(SIPHON_REACH)],
                   [heb.a_say(L["siphon"], 0)] + siphon() + [heb.a_set_var(3, 1)]),
            heb.ev("siphon", [heb.c_var(2, SIPHON_EVERY, 2), heb.c_target_within(SIPHON_REACH)],
                   siphon()),
            heb.ev("retaliate", [heb.c_chance(20), heb.c_attacker_not_target()],
                   [heb.a_attack_attacker(), heb.a_set_var(2, 1, 6)]),
            heb.ev("count", [], [heb.a_set_var(2, 1, 6)]),
        ]),
        (heb.pat("kill"), [heb.ev("gloat", [heb.c_chance(50)], [heb.a_say(L["kill"], 0)])]),
        (heb.pat("dead"), []),
    ]
    # idle check every 2 s, the damaged pattern on every hit taken
    return mon.build_aip((len(pats), 2, 100), b"Necromancer\0", pats, b"")


def ai_lines(ours, dry):
    ais = oro.Stb(P(ours, AI_STR_REL))
    rows, added = {}, 0
    for key, text in LINES.items():
        raw = text.encode("latin-1")
        hit = [r for r in range(ais.rows) if ais.get(r, 1) == raw]
        if hit:
            rows[key] = hit[0]
            continue
        r = ais.rows
        ais.grow_to(r + 1)
        for c in range(ais.cols):
            ais.set(r, c, raw)
        rows[key] = r
        added += 1
    if added:
        ais.save(dry, keep_backup=False)
    return rows, added


# ---------------------------------------------------------------------- the monster
def npc_row(d_npc):
    row = list(d_npc.d[TEMPLATE])
    row[C_NAME] = NECRO_NAME.encode()
    for c, v in STATS.items():
        row[c] = b(STAFF_ROW if c == C_RWEAPON else v)
    for c in (C_TARGET, C_DEADEVENT, *oro.NPC_SELL_TAB_COLS):
        row[c] = b""
    row[oro.NPC_STRID_COL] = NECRO_STRID.encode()
    row[oro.NPC_PVP_COL] = oro.DEFAULT_PVP_STATE
    if d_npc.get(NECRO, C_NAME).strip():
        row[C_EXP] = d_npc.get(NECRO, C_EXP)        # rebalance-exp-rewards.py owns it
    return row


def siphon_row(sk):
    row = list(sk.d[SIPHON_SRC])
    row[SK_NAME] = SIPHON_NAME.encode()
    row[SK_LINE] = b(SIPHON)
    for c, v in SIPHON_CELLS.items():
        row[c] = b(v)
    row[SK_STL_KEY] = SIPHON_STRID.encode()
    return row


def monster(ours, src, dry):
    s_npc, d_npc = oro.Stb(P(src, NPC_STB_REL)), oro.Stb(P(ours, NPC_STB_REL))
    if s_npc.get(NECRO, C_NAME) != NECRO_NAME.encode():
        raise SystemExit(f"tsuki LIST_NPC row {NECRO} is {s_npc.get(NECRO, C_NAME)!r}")
    cur = d_npc.get(NECRO, C_NAME).decode("latin-1").strip()
    if cur and cur != NECRO_NAME:
        raise SystemExit(f"our LIST_NPC row {NECRO} is {cur!r}")
    want = npc_row(d_npc)
    if d_npc.d[NECRO] != want:
        d_npc.d[NECRO] = want
        d_npc.save(dry, keep_backup=False)
        print(f"    {'LIST_NPC.STB':26s} row {NECRO} {NECRO_NAME} (from {TEMPLATE})")
    else:
        print(f"    {'LIST_NPC.STB':26s} row {NECRO} already in place")

    stl = oro.Stl(P(ours, NPC_STL_REL))
    if not stl.has(NECRO_STRID):
        stl.append(NECRO_STRID, NECRO, NECRO_NAME)       # NRST01: a name only
        stl.save(dry, keep_backup=False)
        print(f"    {'LIST_NPC_S.STL':26s} +1 key {NECRO_STRID}")

    oro.import_characters([NECRO], ours, src, dry, NECRO_NAME)
    for rel, events in CLIP_EVENTS.items():
        blob = clip_with_events(open(P(src, rel), "rb").read(), events)
        changed = write_if_changed(P(ours, rel), blob, dry)
        print(f"    {os.path.basename(rel):26s} events {events} "
              f"{'written' if changed else 'in place'}")

    sk = oro.Stb(P(ours, SKILL_STB_REL))
    if sk.rows <= SIPHON:
        sk.grow_to(SIPHON + 1)
    cur = sk.get(SIPHON, SK_NAME).decode("latin-1").strip()
    if cur and cur != SIPHON_NAME:
        raise SystemExit(f"our LIST_SKILL row {SIPHON} is {cur!r}")
    want = siphon_row(sk)
    if sk.d[SIPHON] != want:
        sk.d[SIPHON] = want
        sk.save(dry, keep_backup=False)
        print(f"    {'LIST_SKILL.STB':26s} row {SIPHON} {SIPHON_NAME} (from {SIPHON_SRC})")
    skl = oro.Stl(P(ours, SKILL_STL_REL))
    if not skl.has(SIPHON_STRID):
        skl.append(SIPHON_STRID, SIPHON, SIPHON_NAME, SIPHON_DESC)
        skl.save(dry, keep_backup=False)
        print(f"    {'LIST_SKILL_S.STL':26s} +1 key {SIPHON_STRID}")

    line_rows, added = ai_lines(ours, dry)
    print(f"    {'AI_s.STB':26s} +{added} lines, rows {sorted(line_rows.values())}")
    fai = oro.Stb(P(ours, AI_STB_REL))
    cell = rf"3DDATA\AI\{AI_FILE}".encode("latin-1")
    if fai.rows <= AI_ROW:
        fai.grow_to(AI_ROW + 1)
    if fai.get(AI_ROW, 0) != cell:
        if fai.get(AI_ROW, 0).strip():
            raise SystemExit(f"our FILE_AI row {AI_ROW} is {fai.get(AI_ROW, 0)!r}")
        fai.set(AI_ROW, 0, cell)
        fai.save(dry, keep_backup=False)
        print(f"    {'FILE_AI.STB':26s} row {AI_ROW} = {AI_FILE}")
    changed = write_if_changed(os.path.join(P(ours, AI_DIR_REL), AI_FILE), build_ai(line_rows), dry)
    print(f"    {AI_FILE:26s} {'written' if changed else 'in place'}")


# ---------------------------------------------------------------------- verify
def verify(ours, src):
    bad = []

    def check(ok, what):
        print(f"    {'ok  ' if ok else 'FAIL'} {what}")
        if not ok:
            bad.append(what)

    d_npc = oro.Stb(P(ours, NPC_STB_REL))
    row = d_npc.d[NECRO]
    check(row[C_NAME] == NECRO_NAME.encode(), f"LIST_NPC {NECRO} is {NECRO_NAME}")
    for c, v in STATS.items():
        if c == C_EXP:
            continue
        want = b(STAFF_ROW if c == C_RWEAPON else v)
        if row[c] != want:
            check(False, f"LIST_NPC {NECRO} col {c} = {want!r} (is {row[c]!r})")
    check(oro.Stl(P(ours, NPC_STL_REL)).has(NECRO_STRID), f"LIST_NPC_S {NECRO_STRID}")
    chr_ = oro.Chr(P(ours, NPC_CHR_REL))
    entry = chr_.chars[NECRO] if NECRO < len(chr_.chars) else None
    check(entry is not None, f"LIST_NPC.CHR entry {NECRO}")
    if entry:
        files = [chr_.skeletons[entry["skel"]]] + [chr_.motions[a] for _, a in entry["anims"]]
        zsc = oro.Zsc(P(ours, PART_ZSC_REL))
        for m in entry["models"]:
            for mi, ti, _ in zsc.objects[m][1]:
                files += [zsc.meshes[mi], zsc.materials[ti][0]]
        missing = [f for f in files if not os.path.isfile(P(ours, f.decode("latin-1")))]
        check(not missing, f"model files present ({len(files)})" + (f": {missing[:3]}" if missing else ""))
        check(chr_.motions[dict(entry["anims"])[SIPHON_MOTION + 1]].upper().endswith(b"ATT01.ZMO"),
              f"slot {SIPHON_MOTION + 1} releases on ATT01")
    for rel, events in CLIP_EVENTS.items():
        _, ev = rfzmo.events(P(ours, rel))
        check(ev is not None and all(ev[f] == e for f, e in events.items()),
              f"{os.path.basename(rel)} carries {events}")
    w = oro.Stb(P(ours, WEAPON_STB_REL))
    check(w.get(STAFF_ROW, C_NAME) == STAFF_NAME.encode(), f"LIST_WEAPON {STAFF_ROW} is {STAFF_NAME}")
    wz = oro.Zsc(P(ours, WEAPON_ZSC_REL))
    parts = wz.objects[STAFF_ROW][1] if STAFF_ROW < len(wz.objects) else []
    check(bool(parts) and all(os.path.isfile(P(ours, wz.materials[t][0].decode("latin-1")))
                              for _, t, _ in parts), f"LIST_WEAPON.ZSC {STAFF_ROW} model + texture")
    sk = oro.Stb(P(ours, SKILL_STB_REL))
    check(sk.rows > SIPHON and sk.d[SIPHON] == siphon_row(sk), f"LIST_SKILL {SIPHON} {SIPHON_NAME}")
    check(oro.Stl(P(ours, SKILL_STL_REL)).has(SIPHON_STRID), f"LIST_SKILL_S {SIPHON_STRID}")
    fai = oro.Stb(P(ours, AI_STB_REL))
    check(fai.get(AI_ROW, 0) == rf"3DDATA\AI\{AI_FILE}".encode(), f"FILE_AI {AI_ROW} = {AI_FILE}")
    aip = os.path.join(P(ours, AI_DIR_REL), AI_FILE)
    check(os.path.isfile(aip) and open(aip, "rb").read() == build_ai(ai_lines(ours, True)[0]),
          f"{AI_FILE} matches the builder")
    leftovers = [rel for rel in TRACKED
                 if any(f.lower().endswith(".bak") and f.lower().startswith(os.path.basename(P(ours, rel)).lower())
                        for f in os.listdir(os.path.dirname(P(ours, rel))))]
    check(not leftovers, "no .bak left beside the tables")
    print(f"{'OK' if not bad else f'{len(bad)} problem(s)'}")
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", default=DEFAULT_SRC, help="the tsuki dump (holds 3Ddata)")
    ap.add_argument("--ours", default=os.path.join(ROOT, "data"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.verify:
        return verify(args.ours, args.src)
    if not args.dry_run:
        keep_originals(args.ours)
    print("the staff")
    staff(args.ours, args.src, args.dry_run)
    print("the monster")
    monster(args.ours, args.src, args.dry_run)
    if not args.dry_run:
        sweep_baks(args.ours)
    print("dry run, nothing written" if args.dry_run else "done -- run --verify")
    return 0


if __name__ == "__main__":
    sys.exit(main())
