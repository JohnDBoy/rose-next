#!/usr/bin/env python3
"""Import Jrose's Core Guardian (LIST_NPC 2337), a lv200 minotaur elite: legacy buff + telegraphed slam.

The user's pick (2026-10-27), the first import run through doc/importing-monsters.md and
scripts/survey-monster.py, and the first **hybrid**: one skill kept as Jrose had it
(variant 2, the self buff), the other rebuilt around a ground telegraph (variant 1, the
slam as a cone). User decisions: our own AI (not Jrose's), level 200, silver star.

What Jrose has, and what it does not
------------------------------------
  * **The row.** Jrose 2337 コアガーディアン "Core Guardian", level 250 on Jrose's scale,
    AI 370, mark 14, size 400. Our 2337 is blank with no CHR entry, so it lands at Jrose's
    number. Every stat is ours (STATS); the row is a copy of TEMPLATE (Melt Dizzle, a
    lv200 bare-handed Warrior with the same idle sound, 301), never Jrose's cells --
    except size, height (col 42, 1000 cm), attack range (col 26, 500), the grey glow
    (col 39) and the death shout (col 35, 322 = Mob36_D, the same file in both dumps).
  * **The model is new**: five minotaur meshes and textures (head, three body parts, the
    axe -- part of the model, so there is no weapon row to import: it is bare-handed, and
    its hits present through NPC_HAND_HIT_EFFECT, the template's 403) on our
    `stoneguard01` skeleton. rosedata.import_characters brings the CHR entry and the files.
  * **Every clip is ours**: the stoneguard03/04 family. Our copy of stoneguard04's
    `skill_A_01` carries 35/25 where Jrose's has 34/24 (our original data, not an import of
    ours); this script cuts its own copies, so neither matters.
  * **Jrose's AI is generic**: `ArenaMon.aip` (and `uc_minotaur.aip`, the other minotaurs'),
    an arena kit -- ATK buff, dispel and stun on the buff clip, two borrowed 40 m area
    blasts (Tenebrae / Apistogramma) on the slam clip. Reported; the user chose ours.

The skills
----------
  * **Slot 6/7, the buff (legacy, variant 2).** Jrose casts 2901 on motion 6, and our 2901
    is the very same row, "Self Buff: Attack Power Up" (type 8, Attack Power Up +15% for
    20 s, scope 14 m: nearby monsters get it too), already cast by the Aqua Guardian, the
    Candle Ghost and others. Nothing is written for it: the AI casts 2901 on motion 6 at
    itself (target 2), on Jrose's own clips -- stoneguard03 `casting_01` then `skill_S_01`
    (74 / 34 / 24 at 5 / 17 / 19: frame 19 presents the buff).
  * **Slot 8/9, the slam (variant 1): SLAM, type 7, a cone of SLAM_LENGTH x SLAM_ANGLE**
    toward where its target stood when the wind-up began, LIST_SKILL col 83 = 1. The
    clip, stoneguard04 `skill_A_01` (91 frames), raises the axe at 10-15, holds it still
    to 46 and slams at 47-50 (the motion profile peaks at 48-49), so it splits cleanly
    at SLAM_SPLIT: the cast is frames 0-46, **1.57 s at natural speed** (no slow motion),
    keeping Jrose's event 74 at 15 (casting effect 2: the `elc_support_wave` shockwave as
    the axe goes up, Jrose's 3690 kit); the action is 47-90 with the area event 24 at its
    frame 3, 0.1 s after the server's hit. Hit effect `mummy_k_skill01` (cracks, rocks,
    lightning: 3690's) and sound `skill_attack01`; the roar `Mob17_N` (3705's) is the
    fire sound at the impact. Jrose's cast clip `casting_01` on slot 8 is no longer used.
    Sized for the body: the axe reaches ~1.65 m forward in the bind pose, ~6.6 m at size
    400, the body stands ~7.8 m tall: an 11 m / 70 degree cone, cast on targets within 10 m (ranged players included).

Damage (combat sim, auto-built lv200 characters, typical play)
-------------------------------------------------------------
Magic formula (col 15 = 2; the physical one floors on the monster's ATK, see
doc/importing-monsters.md). The yardstick is the lv205 silver elite Ikaness Heavygear's
Mecha Crush (381-540 on the same builds, undodgeable); a dodgeable skill hits ~1.5x. At
SLAM_POWER 170 the slam lands 636-764 (Knight 699 of 5300 HP; Mage, Raider, Scout,
Artisan 2100-3000 HP), 0.6-2.1 times a solo fight (ranged builds more: they stand inside
the cone at range). Solo wins 72-100% (the Artisan lowest), the Sikuku elites' band.

The AI
------
Ours. It buffs itself on the first hit it takes (var 4), and again with a line under
MIRROR_HP (once). It slams every SLAM_EVERY hits taken (misses count; var 2) while its
target is within SLAM_REACH, and may slam a target that keeps its distance while it chases
(SLAM_CHASE). The idle search is in "stop" too (regen spawns never run "created").
Three sim findings shaped it (build_ai's comment): an order refused because the monster
is still casting runs the event's other actions anyway, so a slam ordered during a buff
was lost and reset its count; the slam therefore comes before the rally and the rally
restarts the count; and the reach covers a ranged player (~9.8 m off), who otherwise
never saw the slam.

Stats
-----
The live level trend at 200 (median of the 27 plain-role spawned monsters within +/-10
levels, 2026-10-27: HP 45/level, ATK 1141, HIT 492, DEF 655, RES 617, AVOID 350, ASPD 96,
EXP 1525) times the silver-star Captain profile of rebalance-monster-roles.py (HP 2.2, ATK
1.2, DEF 1.15, RES 1.15, HIT 1.1, AVOID 1.0, ASPD 1.05), frozen here. EXP seeded only.
Drop table: the template's. The row is in balance-trend-exclude.py. Run speed is 700, not
Jrose's 1500: a 4x minotaur sprinting at 2.4x a player's run is a different monster.

Not spawned anywhere. Test: `/mon 2337 1` with a character of about level 200.

    python scripts/import-core-guardian.py --dry-run
    python scripts/import-core-guardian.py
    python scripts/import-core-guardian.py --verify

Then: audit-ai-skill-refs.py, audit-ai-monster-refs.py, add-dds-mipmaps.py over the new
texture folder, bake, restart the servers. Originals of every table touched:
build/core-guardian/.
"""
import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import rosedata as oro  # noqa: E402
from rosefmt import zmo as rfzmo  # noqa: E402

DEFAULT_SRC = r"C:\Users\Thomas\Desktop\Testclients\Jrose"
BUILD_DIR = os.path.join(ROOT, "build", "core-guardian")

NPC_STB_REL = r"3DDATA\STB\LIST_NPC.STB"
NPC_STL_REL = r"3DDATA\STB\LIST_NPC_S.STL"
NPC_CHR_REL = r"3DDATA\NPC\LIST_NPC.CHR"
PART_ZSC_REL = r"3DDATA\NPC\PART_NPC.ZSC"
SKILL_STB_REL = r"3DDATA\STB\LIST_SKILL.STB"
SKILL_STL_REL = r"3DDATA\STB\LIST_SKILL_S.STL"
AI_STB_REL = r"3DDATA\STB\FILE_AI.STB"
AI_STR_REL = r"3DDATA\AI\AI_s.STB"
AI_DIR_REL = r"3DDATA\AI"
TRACKED = [NPC_STB_REL, NPC_STL_REL, NPC_CHR_REL, PART_ZSC_REL, SKILL_STB_REL, SKILL_STL_REL,
           AI_STB_REL, AI_STR_REL]

# ---- the monster
GUARD = 2337                        # Jrose's row; blank here, no CHR entry
GUARD_SRC_NAME = "コアガーディアン".encode("cp932")
GUARD_NAME = "Core Guardian"
GUARD_STRID = "LCOREMOB2337"
TEMPLATE = 1588                     # Melt Dizzle: lv200 bare-handed Warrior, idle sound 301
C_NAME, C_MODEL, C_WALK, C_RUN, C_SIZE, C_RWEAPON, C_LWEAPON, C_LEVEL, C_HP, C_ATK, C_HIT, \
    C_DEF, C_RES, C_AVOID, C_ASPD, C_MAGIC, C_AI, C_EXP, C_DROP, C_MONEY, C_DROPRATE = range(21)
C_TARGET, C_RANGE, C_TYPE, C_DIESND, C_GLOW, C_DEADEVENT, C_HEIGHT = 25, 26, 27, 35, 39, 41, 42
TYPE_CAPTAIN = 9                    # silver star
AI_ROW = 2260                       # one past the end of FILE_AI
AI_FILE = "CORE_GUARDIAN.AIP"
STATS = {
    C_MODEL: "minotaur_0714_cr.mon",  # /mon refuses a row with no model text
    C_WALK: 200, C_RUN: 700, C_SIZE: 400, C_HEIGHT: 1000,
    C_RWEAPON: "", C_LWEAPON: "",   # the axe is part of the model
    C_LEVEL: 200, C_HP: 99, C_ATK: 1369, C_HIT: 541, C_DEF: 753, C_RES: 710,
    C_AVOID: 350, C_ASPD: 101, C_MAGIC: "", C_AI: AI_ROW, C_EXP: 2100,
    C_RANGE: 500,                   # Jrose's: the axe's reach at 4x
    C_TYPE: TYPE_CAPTAIN,
    C_DIESND: 322,                  # Jrose's death shout (Mob36_D)
    C_GLOW: 100100100,              # Jrose's grey glow
}

# ---- the skills
SK_NAME, SK_LINE, SK_TYPE, SK_RANGE, SK_SCOPE, SK_POWER = 0, 1, 5, 6, 8, 9
SK_STATUS, SK_SUCCESS, SK_DURATION, SK_DMGTYPE = 11, 13, 14, 15
SK_CAST_MOTION, SK_CAST_SPEED, SK_ACT_MOTION, SK_ACT_SPEED = 52, 53, 68, 69
SK_TELEGRAPH, SK_STL_KEY = 83, 86

BUFF = 2901                         # ours = Jrose's: Self Buff: Attack Power Up (type 8)
BUFF_MOTION = 6                     # stoneguard03 casting_01 -> skill_S_01, as Jrose's

SLAM = 7200                         # one past the end of LIST_SKILL
SLAM_NAME = "Core Breaker"
SLAM_STRID = "LMobSkill7200"
SLAM_DESC = "Raises its axe high and brings it down on everything in front of it."
SLAM_SRC = 3603                     # Charge: our clean type-7 monster row
SLAM_MOTION = 8                     # cast slot 8, released on 9
SLAM_LENGTH, SLAM_ANGLE = 1100, 70  # cm from its centre, full opening in degrees
SLAM_SCOPE = 100000000 + SLAM_LENGTH * 10000 + SLAM_ANGLE   # io_skill.h SKILL_SCOPE_CONE
SLAM_RANGE = 1050                   # cm: cast on a target this close, no chase first
SLAM_POWER = 170
FX_WAVE, FX_CRACK = 2512, 1382      # elc_support_wave, mummy_k_skill01 (Jrose's 3690)
SND_ROAR, SND_HIT = 245, 131        # Mob17_N (3705's fire sound), skill_attack01
SLAM_CELLS = {
    SK_TYPE: 7, SK_RANGE: SLAM_RANGE, SK_SCOPE: SLAM_SCOPE, SK_POWER: SLAM_POWER, SK_DMGTYPE: 2,
    SK_CAST_MOTION: SLAM_MOTION, SK_CAST_SPEED: 100,
    SK_ACT_MOTION: SLAM_MOTION + 1, SK_ACT_SPEED: 100,
    62: FX_WAVE, 63: 999, 64: "",                   # casting effect 2: event 74 (the raise)
    71: "", 72: "", 73: SND_ROAR,                   # no bullet; the fire sound on event 24
    74: FX_CRACK, 75: 999, 76: SND_HIT,
    SK_TELEGRAPH: 1,                                # the cone on the ground
}

# ---- the slam's clips: this monster's own copies (CHR slot: path)
SRC_SLAM = r"3Ddata\MOTION\NPC\stoneguard04\skill_A_01.ZMO"    # ours (35/25) == Jrose's body
SLAM_SPLIT = 47                     # the first frame of the slam
CLIP_DIR = r"3Ddata\MOTION\NPC\CORE_GUARDIAN"
CLIPS = {
    SLAM_MOTION: CLIP_DIR + r"\CORE_SLAM_WINDUP.ZMO",
    SLAM_MOTION + 1: CLIP_DIR + r"\CORE_SLAM.ZMO",
}

# ---- the AI
SEEK, LEASH = 15, 40                # m
SLAM_REACH = 10                     # m, inside SLAM_RANGE and the cone: a ranged player
                                    # stands ~9.8 m off; at 8 they were never slammed (sim)
SLAM_CHASE = (4, 25)                # m, %: while chasing a target at least this far
SLAM_EVERY = 5                      # hits taken between two skills (monster var 2); 6 with
                                    # the buffs not counted gave 0-1 slams per solo fight
MIRROR_HP = 50                      # %: the second buff, with a line (var 4: 0 -> 1 -> 2)
MIRROR_GAP = 2                      # hits since the last skill before that buff
LINES = {   # AI_s.STB, appended; AIACT28 kind 0 = local chat
    "rally": "The Core will not fall!",
    "kill": "Nothing reaches the Core.",
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


def find_ci(root, rel):
    """The file for a data-relative path, matched case-insensitively per component."""
    cur = root
    for part in rel.replace("\\", "/").split("/"):
        hit = [f for f in os.listdir(cur) if f.lower() == part.lower()] if os.path.isdir(cur) else []
        cur = os.path.join(cur, hit[0] if hit else part)
    return cur


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
    """Move the codecs' .bak files out of data/ -- pack.ps1 refuses to bake beside one."""
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
        print(f"    {'.bak files':26s} {moved} moved to build/core-guardian/bak")


def write_if_changed(path, blob, dry):
    if os.path.isfile(path) and open(path, "rb").read() == blob:
        return False
    if not dry:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(blob)
    return True


# ---------------------------------------------------------------------- the clips
def cleared(blob, keep=None):
    """The clip with every event zeroed, then `keep` ({frame: event}) written."""
    _, ev = rfzmo.events(blob)
    changes = {i: 0 for i, e in enumerate(ev) if e}
    changes.update(keep or {})
    return rfzmo.with_events(blob, changes)


def build_clips(ours):
    """{CHR slot: clip bytes} cut from our skill_A_01 (refusing any other clip)."""
    blob = open(find_ci(ours, SRC_SLAM), "rb").read()
    _, ev = rfzmo.events(blob)
    got = {i: e for i, e in enumerate(ev or []) if e}
    if rfzmo.read_header(blob)[1] != 91 or got != {15: 74, 48: 35, 50: 25}:
        raise SystemExit(f"{SRC_SLAM} is not the 91-frame clip with events 74/35/25 at 15/48/50 "
                         f"this was cut for (has {got}) -- refusing")
    return {
        SLAM_MOTION: cleared(rfzmo.sliced(blob, 0, SLAM_SPLIT), {15: 74}),   # the raise + hold
        SLAM_MOTION + 1: cleared(rfzmo.sliced(blob, SLAM_SPLIT, 91), {3: 24}),  # the slam
    }


def set_clip_slots(ours, dry):
    """Point the Core Guardian's CHR slots 8/9 at its own clips."""
    chr_ = oro.Chr(P(ours, NPC_CHR_REL))
    entry = chr_.chars[GUARD]
    want = {}
    for slot, rel in CLIPS.items():
        key = rel.encode("latin-1")
        hit = [i for i, m in enumerate(chr_.motions) if m.lower() == key.lower()]
        if not hit:
            chr_.motions.append(key)
            hit = [len(chr_.motions) - 1]
        want[slot] = hit[0]
    slots = {s for s, _ in entry["anims"]}
    if not set(want) <= slots:
        raise SystemExit(f"LIST_NPC.CHR {GUARD} has no slots {sorted(set(want) - slots)} -- refusing")
    anims = [(s, want.get(s, i)) for s, i in entry["anims"]]
    if anims == entry["anims"]:
        print(f"    {'LIST_NPC.CHR':26s} slots 8/9 already on its own clips")
        return
    entry["anims"] = anims
    chr_.save(dry)
    print(f"    {'LIST_NPC.CHR':26s} slots 8/9 -> {CLIP_DIR}")


# ---------------------------------------------------------------------- the AI
def build_ai(L):
    def buff():
        return [heb.a_cast(BUFF, BUFF_MOTION, target=2)]     # 2 = itself

    def slam():
        return [heb.a_cast(SLAM, SLAM_MOTION), heb.a_set_var(2, 0)]
    # Order matters (first match wins), and so does spacing: an order the server refuses
    # because the monster is still casting runs the event's other actions anyway, so a
    # slam ordered during a buff's cast was lost *and* reset the count. The first cut put
    # the rally before the slam: against a bursty build the rally came first, the slam
    # landed on its cast, and a solo fight saw no slam at all (sim, Raider / Scout /
    # Artisan). Now the slam comes before the rally, and the rally restarts the count, so
    # the next slam is SLAM_EVERY hits after it. The opening buff is at hit 1, with the
    # count at 0, so the first slam is SLAM_EVERY hits later (its cast long finished).
    pats = [
        (heb.pat("created"), [heb.ev("hunt", [heb.c_enemies_near(SEEK)], [heb.a_attack_found()])]),
        (heb.pat("stop"), [
            heb.ev("go home", [heb.c_moved_from_spawn(LEASH)], [heb.a_run_home(3)]),
            heb.ev("seek", [heb.c_enemies_near(SEEK)], [heb.a_attack_found()]),
        ]),
        (heb.pat("attack move"), [       # runs only while it moves towards its target
            heb.ev("leash", [heb.c_moved_from_spawn(LEASH)], [heb.a_run_home(3)]),
            heb.ev("slam", [heb.c_chance(SLAM_CHASE[1]), heb.c_target_at_least(SLAM_CHASE[0]),
                            heb.c_target_within(SLAM_REACH)], slam()),
        ]),
        (heb.pat("damaged"), [           # first match wins; var 2 = hits, var 4 = buffs cast
            heb.ev("opening buff", [heb.c_var(4, 0)], buff() + [heb.a_set_var(4, 1)]),
            heb.ev("slam", [heb.c_var(2, SLAM_EVERY, 2), heb.c_target_within(SLAM_REACH)], slam()),
            heb.ev("rally", [heb.c_hp_at_most(MIRROR_HP), heb.c_var(4, 1), heb.c_var(2, MIRROR_GAP, 2)],
                   [heb.a_say(L["rally"], 0)] + buff() + [heb.a_set_var(4, 2), heb.a_set_var(2, 0)]),
            heb.ev("retaliate", [heb.c_chance(20), heb.c_attacker_not_target()],
                   [heb.a_attack_attacker(), heb.a_set_var(2, 1, 6)]),
            heb.ev("count", [], [heb.a_set_var(2, 1, 6)]),
        ]),
        (heb.pat("kill"), [heb.ev("gloat", [heb.c_chance(50)], [heb.a_say(L["kill"], 0)])]),
        (heb.pat("dead"), []),
    ]
    # idle check every 2 s, the damaged pattern on every hit taken
    return mon.build_aip((len(pats), 2, 100), b"Core Guardian\0", pats, b"")


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


# ---------------------------------------------------------------------- the rows
def npc_row(d_npc):
    row = list(d_npc.d[TEMPLATE])
    row[C_NAME] = GUARD_NAME.encode()
    for c, v in STATS.items():
        row[c] = b(v)
    for c in (C_TARGET, C_DEADEVENT, *oro.NPC_SELL_TAB_COLS):
        row[c] = b""
    row[oro.NPC_STRID_COL] = GUARD_STRID.encode()
    row[oro.NPC_PVP_COL] = oro.DEFAULT_PVP_STATE
    if d_npc.get(GUARD, C_NAME).strip():
        row[C_EXP] = d_npc.get(GUARD, C_EXP)        # rebalance-exp-rewards.py owns it
    return row


def slam_row(sk):
    row = list(sk.d[SLAM_SRC])
    row[SK_NAME] = SLAM_NAME.encode()
    row[SK_LINE] = b(SLAM)
    for c, v in SLAM_CELLS.items():
        row[c] = b(v)
    row[SK_STL_KEY] = SLAM_STRID.encode()
    return row


def monster(ours, src, dry):
    s_npc, d_npc = oro.Stb(P(src, NPC_STB_REL), "cp932"), oro.Stb(P(ours, NPC_STB_REL))
    if s_npc.get(GUARD, C_NAME) != GUARD_SRC_NAME:
        raise SystemExit(f"Jrose LIST_NPC row {GUARD} is {s_npc.get(GUARD, C_NAME)!r}")
    cur = d_npc.get(GUARD, C_NAME).decode("latin-1").strip()
    if cur and cur != GUARD_NAME:
        raise SystemExit(f"our LIST_NPC row {GUARD} is {cur!r}")
    want = npc_row(d_npc)
    if d_npc.d[GUARD] != want:
        d_npc.d[GUARD] = want
        d_npc.save(dry, keep_backup=False)
        print(f"    {'LIST_NPC.STB':26s} row {GUARD} {GUARD_NAME} (from {TEMPLATE})")
    else:
        print(f"    {'LIST_NPC.STB':26s} row {GUARD} already in place")

    stl = oro.Stl(P(ours, NPC_STL_REL))
    if not stl.has(GUARD_STRID):
        stl.append(GUARD_STRID, GUARD, GUARD_NAME)       # NRST01: a name only
        stl.save(dry, keep_backup=False)
        print(f"    {'LIST_NPC_S.STL':26s} +1 key {GUARD_STRID}")

    oro.import_characters([GUARD], ours, src, dry, GUARD_NAME)
    for slot, blob in build_clips(ours).items():
        changed = write_if_changed(P(ours, CLIPS[slot]), blob, dry)
        print(f"    {os.path.basename(CLIPS[slot]):26s} slot {slot} "
              f"{'written' if changed else 'in place'}")
    if not dry:
        set_clip_slots(ours, dry)

    sk = oro.Stb(P(ours, SKILL_STB_REL))
    if sk.get(BUFF, SK_TYPE) != b"8":
        raise SystemExit(f"our LIST_SKILL {BUFF} is no longer the type-8 self buff")
    if sk.rows <= SLAM:
        sk.grow_to(SLAM + 1)
    cur = sk.get(SLAM, SK_NAME).decode("latin-1").strip()
    if cur and cur != SLAM_NAME:
        raise SystemExit(f"our LIST_SKILL row {SLAM} is {cur!r}")
    want = slam_row(sk)
    if sk.d[SLAM] != want:
        sk.d[SLAM] = want
        sk.save(dry, keep_backup=False)
        print(f"    {'LIST_SKILL.STB':26s} row {SLAM} {SLAM_NAME} (from {SLAM_SRC})")
    skl = oro.Stl(P(ours, SKILL_STL_REL))
    if not skl.has(SLAM_STRID):
        skl.append(SLAM_STRID, SLAM, SLAM_NAME, SLAM_DESC)
        skl.save(dry, keep_backup=False)
        print(f"    {'LIST_SKILL_S.STL':26s} +1 key {SLAM_STRID}")

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
    row = d_npc.d[GUARD]
    check(row[C_NAME] == GUARD_NAME.encode(), f"LIST_NPC {GUARD} is {GUARD_NAME}")
    for c, v in STATS.items():
        if c != C_EXP and row[c] != b(v):
            check(False, f"LIST_NPC {GUARD} col {c} = {b(v)!r} (is {row[c]!r})")
    check(oro.Stl(P(ours, NPC_STL_REL)).has(GUARD_STRID), f"LIST_NPC_S {GUARD_STRID}")
    chr_ = oro.Chr(P(ours, NPC_CHR_REL))
    entry = chr_.chars[GUARD] if GUARD < len(chr_.chars) else None
    check(entry is not None, f"LIST_NPC.CHR entry {GUARD}")
    if entry:
        files = [chr_.skeletons[entry["skel"]]] + [chr_.motions[a] for _, a in entry["anims"]]
        zsc = oro.Zsc(P(ours, PART_ZSC_REL))
        for m in entry["models"]:
            for mi, ti, _ in zsc.objects[m][1]:
                files += [zsc.meshes[mi], zsc.materials[ti][0]]
        missing = [f for f in files if not os.path.isfile(find_ci(ours, f.decode("latin-1")))]
        check(not missing, f"model files present ({len(files)})" + (f": {missing[:3]}" if missing else ""))
        anims = dict(entry["anims"])
        check(all(chr_.motions[anims[s]].lower() == rel.encode("latin-1").lower()
                  for s, rel in CLIPS.items()), "slots 8/9 on its own clips")
    built = build_clips(ours)
    for slot, rel in CLIPS.items():
        p = P(ours, rel)
        check(os.path.isfile(p) and open(p, "rb").read() == built[slot],
              f"{os.path.basename(rel)} matches the builder")
    sk = oro.Stb(P(ours, SKILL_STB_REL))
    check(sk.get(BUFF, SK_TYPE) == b"8", f"LIST_SKILL {BUFF} is the type-8 self buff")
    check(sk.rows > SLAM and sk.d[SLAM] == slam_row(sk), f"LIST_SKILL {SLAM} {SLAM_NAME}")
    check(oro.Stl(P(ours, SKILL_STL_REL)).has(SLAM_STRID), f"LIST_SKILL_S {SLAM_STRID}")
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
    ap.add_argument("--src", default=DEFAULT_SRC, help="the Jrose dump (holds 3Ddata)")
    ap.add_argument("--ours", default=os.path.join(ROOT, "data"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.verify:
        return verify(args.ours, args.src)
    if not args.dry_run:
        keep_originals(args.ours)
    print("the monster")
    monster(args.ours, args.src, args.dry_run)
    if not args.dry_run:
        sweep_baks(args.ours)
    print("dry run, nothing written" if args.dry_run else "done -- run --verify")
    return 0


if __name__ == "__main__":
    sys.exit(main())
