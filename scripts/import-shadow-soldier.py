#!/usr/bin/env python3
"""Import Jrose's Shadow Soldier (LIST_NPC 2290 there) with its Rusted Lord of Blade, a lv190 elite.

The user's pick (2026-10-27): "a clone of what a high level player could be" -- a Soldier
in a Soldier's armour with a two-handed sword, and the Knight's sword-in-the-ground burst.
Level 190 for now. Both of its skills are telegraphed on the ground (LIST_SKILL col 83, the
Cerberus Lair's mechanic): a circle before the burst, a cone before the strike.

What Jrose has, and what it does not
------------------------------------
  * **The row.** Jrose 2290 シャドウソルジャー "Shadow Soldier", level 250 on Jrose's scale,
    AI 1004, mark 14, with three siblings (2291 Muse, 2292 Hawker, 2293 Dealer). Our 2290
    is the Ikaness Sand Tiller, so it lands on SHADOW, the first blank row after the
    Ikaness band (2298-2300 stay free for the siblings). Every stat is ours (STATS); the
    row is a copy of TEMPLATE (Sikuku Killer, a lv190 melee humanoid whose death effect and
    death shout, 1401 / 370, are the very cells Jrose gives the Shadow Soldier), never
    Jrose's cells -- except its blue glow (col 39) and its walk/run speeds and size.
  * **The model is a player's**: our male avatar skeleton (Jrose's NPC copy of it) and our
    Soldier body / arms / feet meshes under new "quest_job" textures, plus a new head, face
    and hair. rosedata.import_characters brings the CHR entry across with every index
    remapped and copies what we lack. **Every clip is a player clip we already ship.**
  * **The sword.** Jrose's LIST_WEAPON 4436 錆びたロード オブ ブレイド, "Rusted Lord of
    Blade" ("still rusted; it must be forged somehow"): our Dairo's mesh (1428,
    e_tsword_131205_cr.zms) under a rust texture we did not have. It comes in through
    import-item.py --art-only as a real item at SWORD_ROW (blank, the end of the
    two-handed sword band, under the 999 ceiling so it can drop or be a reward later):
    stats cloned from Moon Sword (122, req lv186, the 2H sword just under 190), Dairo's
    icon (same mesh). Its hit effect and sounds are the 2H sword family's.
  * **No AI** (Jrose never ships its .aip files), no sounds of its own. The AI and the two
    skill rows are written here.

The two skills (what its CHR slots say)
---------------------------------------
Jrose casts slot 6 -> releases on 7, and 8 -> 9:

  * slots 6/7: scope_casting01 -> **s_holysword01**, the clip of the Knight's Impact Wave
    (LIST_SKILL 511, type 17): the sword raised over frames 0-20, slammed into the ground
    at 21-23 (events 34/74/24 at 22/23/24), held there to 31, then the rise.
  * slots 8/9: near_casting01 -> **s_rightingcration**, the clip of Lightning Crasher (521,
    type 3): a spin-up, a leap (the root rises to frame 18) and a landing strike, 35/25 at
    28/30. One blow: the server counts 25, not 35, as an attack frame.

Both became telegraphed area skills. The server applies an area skill's damage when its
action clip starts (Skill_START), and the client draws the telegraph for one play of the
cast clip, then flashes it -- so the cast clip is the wind-up the player reads, and the
action should open as close to the blow as the clip allows:

  * **Impact Wave (IMPACT, type 17, a circle of IMPACT_RADIUS around it).** The clip splits
    cleanly at the top of the raise (frame 21, where the slam starts): the cast is frames
    0-20 at IMPACT_CAST_SPEED (~1.75 s, the raise in slow motion), the action is 21-45 and
    lands its area event 24 at its own frame 3 -- 0.1 s after the server's hit. Event 74
    (frame 2) plays casting effect 2, Impact Wave's crack-and-blast (holy_sword_01) at the
    slam; event 44 at the cast's first frame plays casting effect 0, the player skill's
    rotating rune (_scope_rotate_01). Hit effect and sound are Impact Wave's.
  * **Lightning Crasher (CRASH, type 7, a cone of CRASH_LENGTH x CRASH_ANGLE toward where
    its target stood when the wind-up began).** The strike clip is active from its first
    frame (spin, leap, strike), so it is not cut: the wind-up is Jrose's own cast clip,
    near_casting01 -- a quiet stance that loops seamlessly (0.4 degrees at the seam) --
    played CRASH_LOOPS times in one clip, ~1.8 s at natural speed. The release is the
    whole clip at CRASH_ACTION_SPEED, with its 25 turned into the area event 24 (25 would
    take the melee-skill path, ProcImmediateSkillHit, built for one target). The digits
    land ~0.8 s after the cone flashes; the flash is the moment it is decided. Lightning
    Crasher's casting effect (_sequence_casting_01) on the wind-up, its heavy hit and
    sound on whoever is struck, and its Fainted (status 32) at CRASH_STUN.

The four clips are this monster's own copies under CLIP_DIR; the player skills keep theirs.
Every effect attached to a character is one-shot (rosefmt.ptl: every sequence loops 1).

Damage (combat sim, auto-built lv190 characters, typical play, 2026-10-27)
--------------------------------------------------------------------------
Both skills use the **magic formula** (col 15 = 2), as the Cerberus Lair's and Charge do.
The weapon formula adds 0.2 x the monster's ATK to the power -- 241 here -- so it floors
high and barely follows the power: physical at power 200 landed ~1140 on a Raider (40% of
its HP), at 100 still ~890. Magic is proportional to the power and defended by DEF x 0.3 +
RES. The yardstick is the level-190-200 silver elites' Firestorm (Sikuku Elite
Slaughterer, ~390-420 on the same builds); a dodgeable skill hits harder (the Hellfire
Breath rule), so ~1.5x: Impact Wave 160 lands 500-600 (Mage / Raider / Scout / Artisan,
2000-2900 HP) and 555 on a Knight (5100); Lightning Crasher 180 lands 560-670 and stuns
about half the time. Solo wins 78-100% (Mage 78%, its losses are to the swings), in the
band of the Sikuku elites' 58-100%. The sim never moves a melee player out of an area, so
dodging only improves on that.

The AI
------
A melee bruiser that alternates its two skills, every SKILL_EVERY hits it takes (misses
count; monster var 2), Impact Wave first (var 3 picks which comes next), each only while
its target is already inside the area (doc/making-monsters.md: a cast ordered from further
away makes the server chase first). Once, when it drops under MIRROR_HP, it says a line and
slams at least MIRROR_GAP hits after its last skill (var 4). While chasing a target that
keeps its distance it may leap at it with Lightning Crasher (CRASH_CHASE). Spawned by /mon
or a regen point, so the idle search is in "stop" as well as "created".

Stats
-----
The live level trend at 190 (median of the 24 plain-role spawned monsters within +/-10
levels, 2026-10-27: HP 38.5/level, ATK 1006, HIT 442, DEF 554, RES 558, AVOID 312, ASPD 92)
times the silver-star Captain profile of rebalance-monster-roles.py (HP 2.2, ATK 1.2, DEF
1.15, RES 1.15, HIT 1.1, AVOID 1.0, ASPD 1.05): a mini-fight, the user's call to revisit
("for now"). Frozen here so a re-run does not drift. EXP is seeded only
(rebalance-exp-rewards.py owns the column). Drop table: the template's (lv190). The row is
in balance-trend-exclude.py.

Not spawned anywhere yet (Jrose's regen points are not ours). Test: `/mon 2297 1` with a
character of about level 190 -- a 240 resists the stun and shrugs off a level-190 monster
(doc/making-monsters.md, "the level gate").

    python scripts/import-shadow-soldier.py --dry-run
    python scripts/import-shadow-soldier.py
    python scripts/import-shadow-soldier.py --verify

Then: audit-ai-skill-refs.py, audit-ai-monster-refs.py, add-dds-mipmaps.py over the new
texture folders, bake, restart the servers (LIST_NPC, LIST_NPC.CHR, LIST_SKILL, FILE_AI,
AI_s.STB, the .AIP and the clips are server data). Originals of every table touched:
build/shadow-soldier/.
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import rosedata as oro  # noqa: E402
from rosefmt import zmo as rfzmo  # noqa: E402

DEFAULT_SRC = r"C:\Users\Thomas\Desktop\Testclients\Jrose"
BUILD_DIR = os.path.join(ROOT, "build", "shadow-soldier")

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
SHADOW = 2297                       # blank here, no CHR entry
SHADOW_SRC = 2290                   # Jrose's row
SHADOW_SRC_NAME = "シャドウソルジャー".encode("cp932")
SHADOW_NAME = "Shadow Soldier"
SHADOW_STRID = "LSHDMOB2297"
TEMPLATE = 1570                     # Sikuku Killer: lv190 melee humanoid, death fx/shout
C_NAME, C_MODEL, C_WALK, C_RUN, C_SIZE, C_RWEAPON, C_LWEAPON, C_LEVEL, C_HP, C_ATK, C_HIT, \
    C_DEF, C_RES, C_AVOID, C_ASPD, C_MAGIC, C_AI, C_EXP, C_DROP, C_MONEY, C_DROPRATE = range(21)
C_TARGET, C_RANGE, C_TYPE, C_GLOW, C_DEADEVENT, C_HEIGHT = 25, 26, 27, 39, 41, 42
C_SOUNDS = (30, 31, 32)             # the template's beast idle/attack/hurt sounds; Jrose
                                    # gives none (the sword's own sounds play)
TYPE_CAPTAIN = 9                    # silver star
AI_ROW = 2259                       # one past the end of FILE_AI
AI_FILE = "SHADOW_SOLDIER.AIP"
STATS = {
    C_MODEL: "shadow_soldier_m.mon",  # /mon refuses a row with no model text (cheatcmd.cpp)
    C_WALK: 200, C_RUN: 620, C_SIZE: 160,           # Jrose's: a head taller than a player
    C_RWEAPON: None, C_LWEAPON: "",                 # the sword (SWORD_ROW), at build time
    C_LEVEL: 190, C_HP: 85, C_ATK: 1207, C_HIT: 487, C_DEF: 637, C_RES: 642,
    C_AVOID: 312, C_ASPD: 97, C_MAGIC: "", C_AI: AI_ROW, C_EXP: 1600,
    C_RANGE: 250,                   # a two-handed sword's reach (Jrose 180)
    C_TYPE: TYPE_CAPTAIN,
    C_GLOW: 120120240,              # Jrose's: a cold blue shadow around it
}

# ---- the sword
SWORD_ROW = 130                     # blank: the 2H sword additions end at 129
SWORD_NAME = "Rusted Lord of Blade"
SWORD_DESC = "A great blade eaten by rust. Someone may yet forge it back to life."
SWORD_SRC_ROW = 4436                # Jrose LIST_WEAPON
SWORD_TEMPLATE = 122                # Moon Sword, req lv186
SWORD_ICON = 8782                   # Dairo's (same mesh)

# ---- the skills
SK_NAME, SK_LINE, SK_TYPE, SK_RANGE, SK_SCOPE, SK_POWER = 0, 1, 5, 6, 8, 9
SK_STATUS, SK_SUCCESS, SK_DURATION, SK_DMGTYPE = 11, 13, 14, 15
SK_CAST_MOTION, SK_CAST_SPEED, SK_ACT_MOTION, SK_ACT_SPEED = 52, 53, 68, 69
SK_TELEGRAPH, SK_STL_KEY = 83, 86

IMPACT = 7198                       # one past the end of LIST_SKILL
IMPACT_NAME = "Impact Wave"
IMPACT_STRID = "LMobSkill7198"      # name-monster-skills-players.py's key convention
IMPACT_DESC = "Drives its sword into the ground, blasting everything around it."
IMPACT_SRC = 3031                   # Area Blast (Terror Knight): monster type 17 on the
                                    # Impact Wave clip, Impact Wave's effects
IMPACT_MOTION = 6                   # cast slot 6, released on 7
IMPACT_RADIUS = 800                 # cm; the player skill's is 7-8 m, the body is 1.6x
IMPACT_POWER = 160                  # magic formula; see the docstring's "Damage"
IMPACT_CAST_SPEED = 40              # %: the 21-frame raise lasts ~1.75 s
FX_RUNE, FX_HOLY_SWORD, FX_IMPACT_HIT = 1764, 243, 1121
SND_HOLY_SWORD, SND_IMPACT_HIT = 127, 139
IMPACT_CELLS = {
    SK_TYPE: 17, SK_RANGE: "", SK_SCOPE: IMPACT_RADIUS, SK_POWER: IMPACT_POWER, SK_DMGTYPE: 2,
    SK_CAST_MOTION: IMPACT_MOTION, SK_CAST_SPEED: IMPACT_CAST_SPEED,
    SK_ACT_MOTION: IMPACT_MOTION + 1, SK_ACT_SPEED: 100,
    54: "",                                         # the player's cast-loop motion
    56: FX_RUNE, 57: 999, 58: "",                   # casting effect 0: event 44 (wind-up)
    59: "", 60: "",                                 # (Impact Wave's effect 1, now 0)
    62: FX_HOLY_SWORD, 63: 999, 64: SND_HOLY_SWORD,  # casting effect 2: event 74 (slam)
    74: FX_IMPACT_HIT, 75: 999, 76: SND_IMPACT_HIT,
    SK_TELEGRAPH: 1,                                # the circle on the ground
}

CRASH = 7199
CRASH_NAME = "Lightning Crasher"
CRASH_STRID = "LMobSkill7199"
CRASH_DESC = "Leaps and brings its sword down on everything in front of it, stunning."
CRASH_SRC = 3603                    # Charge: our type-7 monster row
CRASH_MOTION = 8                    # cast slot 8, released on 9
CRASH_LENGTH, CRASH_ANGLE = 700, 80  # cm from its centre, full opening in degrees
CRASH_SCOPE = 100000000 + CRASH_LENGTH * 10000 + CRASH_ANGLE   # io_skill.h SKILL_SCOPE_CONE
CRASH_RANGE = 600                   # cm: cast on a target this close, no chase first
CRASH_POWER = 180
CRASH_ACTION_SPEED = 125            # %: the strike lands ~0.8 s after the action starts
CRASH_STUN = (32, 50, 3)            # Fainted, success, seconds (it shows 1-3 s late)
FX_CRASH_CAST, FX_CRASH_HIT, SND_CRASH_HIT = 1031, 1067, 141
CRASH_CELLS = {
    SK_TYPE: 7, SK_RANGE: CRASH_RANGE, SK_SCOPE: CRASH_SCOPE, SK_POWER: CRASH_POWER,
    SK_DMGTYPE: 2,
    SK_STATUS: CRASH_STUN[0], SK_SUCCESS: CRASH_STUN[1], SK_DURATION: CRASH_STUN[2],
    SK_CAST_MOTION: CRASH_MOTION, SK_CAST_SPEED: 100,
    SK_ACT_MOTION: CRASH_MOTION + 1, SK_ACT_SPEED: CRASH_ACTION_SPEED,
    56: FX_CRASH_CAST, 57: 999, 58: "",             # casting effect 0: event 44 (wind-up)
    62: "", 63: "", 64: "",                         # Charge's charge effect
    71: "", 72: "", 73: "",                         # no bullet
    74: FX_CRASH_HIT, 75: 999, 76: SND_CRASH_HIT,
    SK_TELEGRAPH: 1,                                # the cone on the ground
}

# ---- the clips: this monster's own copies (CHR slot: (path, built from))
AV = r"3Ddata\MOTION\AVATAR"
CLIP_DIR = r"3Ddata\MOTION\NPC\SHADOW_SOLDIER"
SRC_IMPACT = AV + r"\s_holysword01_m1.ZMO"
SRC_CRASH_CAST = AV + r"\near_casting01_m1.ZMO"
SRC_CRASH = AV + r"\s_rightingcration_m1.ZMO"
IMPACT_SPLIT = 21                   # the first frame of the slam (the raise ends at 20)
CRASH_LOOPS = 5                     # near_casting01 x5: 55 frames, ~1.8 s
CRASH_CAST_FX_AT = (0, 22)          # event 44 on the 1st and 3rd loop
CLIPS = {
    IMPACT_MOTION: CLIP_DIR + r"\SHADOW_IMPACT_WINDUP.ZMO",
    IMPACT_MOTION + 1: CLIP_DIR + r"\SHADOW_IMPACT_SLAM.ZMO",
    CRASH_MOTION: CLIP_DIR + r"\SHADOW_CRASH_WINDUP.ZMO",
    CRASH_MOTION + 1: CLIP_DIR + r"\SHADOW_CRASH_STRIKE.ZMO",
}

# ---- the AI
SEEK, LEASH = 15, 40                # m
IMPACT_REACH = 6                    # m, inside IMPACT_RADIUS
CRASH_REACH = 5                     # m, inside CRASH_RANGE and the cone
CRASH_CHASE = (3, 25)               # m, %: while chasing a target at least this far
SKILL_EVERY = 5                     # hits taken between two skills (monster var 2); 10 gave
                                    # one cast per 10 s solo fight (sim, lv190 Knight)
MIRROR_HP = 50                      # %: the once-per-life slam with a line (var 4)
MIRROR_GAP = 3                      # hits since the last skill before that one
LINES = {   # AI_s.STB, appended; AIACT28 kind 0 = local chat
    "mirror": "I know every move you are about to make.",
    "kill": "Your shadow belongs to me now.",
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
        print(f"    {'.bak files':26s} {moved} moved to build/shadow-soldier/bak")


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
    """{CHR slot: clip bytes}, built from the avatar clips we ship (refusing any that is
    not the clip this was cut for)."""
    def read(rel, frames, events):
        blob = open(find_ci(ours, rel), "rb").read()
        _, ev = rfzmo.events(blob)
        got = {i: e for i, e in enumerate(ev or []) if e}
        if rfzmo.read_header(blob)[1] != frames or got != events:
            raise SystemExit(f"{rel} is not the {frames}-frame clip with events {events} this "
                             f"was cut for (has {got}) -- refusing")
        return blob

    impact = read(SRC_IMPACT, 46, {22: 34, 23: 74, 24: 24})
    crash_cast = read(SRC_CRASH_CAST, 11, {0: 44})
    crash = read(SRC_CRASH, 45, {28: 35, 30: 25})
    loop = crash_cast
    for _ in range(CRASH_LOOPS - 1):
        loop = rfzmo.joined(loop, crash_cast)
    return {
        IMPACT_MOTION: cleared(rfzmo.sliced(impact, 0, IMPACT_SPLIT), {0: 44}),
        IMPACT_MOTION + 1: rfzmo.sliced(impact, IMPACT_SPLIT, 46),     # 34/74/24 at 1/2/3
        CRASH_MOTION: cleared(loop, {f: 44 for f in CRASH_CAST_FX_AT}),
        CRASH_MOTION + 1: rfzmo.with_events(crash, {30: 24}),        # 25 -> the area event
    }


def set_clip_slots(ours, dry):
    """Point the Shadow Soldier's CHR slots 6-9 at its own clips."""
    chr_ = oro.Chr(P(ours, NPC_CHR_REL))
    entry = chr_.chars[SHADOW]
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
        raise SystemExit(f"LIST_NPC.CHR {SHADOW} has no slots {sorted(set(want) - slots)} -- refusing")
    anims = [(s, want.get(s, i)) for s, i in entry["anims"]]
    if anims == entry["anims"]:
        print(f"    {'LIST_NPC.CHR':26s} slots 6-9 already on its own clips")
        return
    entry["anims"] = anims
    chr_.save(dry)
    print(f"    {'LIST_NPC.CHR':26s} slots 6-9 -> {CLIP_DIR}")


# ---------------------------------------------------------------------- the sword
def sword(ours, src, dry):
    w = oro.Stb(P(ours, WEAPON_STB_REL))
    cur = w.get(SWORD_ROW, C_NAME).decode("latin-1").strip()
    if cur == SWORD_NAME:
        print(f"    {'LIST_WEAPON.STB':26s} row {SWORD_ROW} {SWORD_NAME} already in place")
        return
    if cur:
        raise SystemExit(f"our LIST_WEAPON row {SWORD_ROW} is {cur!r}")
    cmd = [sys.executable, os.path.join(HERE, "import-item.py"), "--type", "weapon",
           "--source", src, "--source-row", str(SWORD_SRC_ROW), "--art-only",
           "--template-row", str(SWORD_TEMPLATE), "--name", SWORD_NAME, "--desc", SWORD_DESC,
           "--icon", str(SWORD_ICON), "--target-row", str(SWORD_ROW)]
    if dry:
        cmd.append("--dry-run")
    print(f"    {'import-item.py':26s} weapon {SWORD_SRC_ROW} -> {SWORD_ROW}")
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    for line in (res.stdout + res.stderr).strip().splitlines():
        print("        " + line)
    if res.returncode:
        raise SystemExit("import-item.py failed")


# ---------------------------------------------------------------------- the AI
def build_ai(L):
    def impact(next_var=1):
        return [heb.a_cast(IMPACT, IMPACT_MOTION), heb.a_set_var(2, 0), heb.a_set_var(3, next_var)]

    def crash():
        return [heb.a_cast(CRASH, CRASH_MOTION), heb.a_set_var(2, 0), heb.a_set_var(3, 0)]
    pats = [
        (heb.pat("created"), [heb.ev("hunt", [heb.c_enemies_near(SEEK)], [heb.a_attack_found()])]),
        (heb.pat("stop"), [
            heb.ev("go home", [heb.c_moved_from_spawn(LEASH)], [heb.a_run_home(3)]),
            heb.ev("seek", [heb.c_enemies_near(SEEK)], [heb.a_attack_found()]),
        ]),
        (heb.pat("attack move"), [       # runs only while it moves towards its target
            heb.ev("leash", [heb.c_moved_from_spawn(LEASH)], [heb.a_run_home(3)]),
            heb.ev("crasher", [heb.c_chance(CRASH_CHASE[1]), heb.c_target_at_least(CRASH_CHASE[0]),
                               heb.c_target_within(CRASH_REACH)], crash()),
        ]),
        (heb.pat("damaged"), [           # first match wins; var 2 = hits, 3 = next skill,
                                         # 4 = the line said
            heb.ev("mirror", [heb.c_hp_at_most(MIRROR_HP), heb.c_var(4, 0),
                              heb.c_var(2, MIRROR_GAP, 2), heb.c_target_within(IMPACT_REACH)],
                   [heb.a_say(L["mirror"], 0)] + impact() + [heb.a_set_var(4, 1)]),
            heb.ev("impact", [heb.c_var(2, SKILL_EVERY, 2), heb.c_var(3, 0),
                              heb.c_target_within(IMPACT_REACH)], impact()),
            heb.ev("crasher", [heb.c_var(2, SKILL_EVERY, 2), heb.c_var(3, 1),
                               heb.c_target_within(CRASH_REACH)], crash()),
            heb.ev("retaliate", [heb.c_chance(20), heb.c_attacker_not_target()],
                   [heb.a_attack_attacker(), heb.a_set_var(2, 1, 6)]),
            heb.ev("count", [], [heb.a_set_var(2, 1, 6)]),
        ]),
        (heb.pat("kill"), [heb.ev("gloat", [heb.c_chance(50)], [heb.a_say(L["kill"], 0)])]),
        (heb.pat("dead"), []),
    ]
    # idle check every 2 s, the damaged pattern on every hit taken
    return mon.build_aip((len(pats), 2, 100), b"Shadow Soldier\0", pats, b"")


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
    row[C_NAME] = SHADOW_NAME.encode()
    for c, v in STATS.items():
        row[c] = b(SWORD_ROW if c == C_RWEAPON else v)
    for c in (C_TARGET, C_DEADEVENT, *C_SOUNDS, *oro.NPC_SELL_TAB_COLS):
        row[c] = b""
    row[oro.NPC_STRID_COL] = SHADOW_STRID.encode()
    row[oro.NPC_PVP_COL] = oro.DEFAULT_PVP_STATE
    if d_npc.get(SHADOW, C_NAME).strip():
        row[C_EXP] = d_npc.get(SHADOW, C_EXP)       # rebalance-exp-rewards.py owns it
    return row


def skill_row(sk, src, name, line, cells, strid):
    row = list(sk.d[src])
    row[SK_NAME] = name.encode()
    row[SK_LINE] = b(line)
    for c, v in cells.items():
        row[c] = b(v)
    row[SK_STL_KEY] = strid.encode()
    return row


SKILLS = (  # row, source row, name, cells, STL key, description
    (IMPACT, IMPACT_SRC, IMPACT_NAME, IMPACT_CELLS, IMPACT_STRID, IMPACT_DESC),
    (CRASH, CRASH_SRC, CRASH_NAME, CRASH_CELLS, CRASH_STRID, CRASH_DESC),
)


def monster(ours, src, dry):
    s_npc, d_npc = oro.Stb(P(src, NPC_STB_REL), "cp932"), oro.Stb(P(ours, NPC_STB_REL))
    if s_npc.get(SHADOW_SRC, C_NAME) != SHADOW_SRC_NAME:
        raise SystemExit(f"Jrose LIST_NPC row {SHADOW_SRC} is {s_npc.get(SHADOW_SRC, C_NAME)!r}")
    cur = d_npc.get(SHADOW, C_NAME).decode("latin-1").strip()
    if cur and cur != SHADOW_NAME:
        raise SystemExit(f"our LIST_NPC row {SHADOW} is {cur!r}")
    want = npc_row(d_npc)
    if d_npc.d[SHADOW] != want:
        d_npc.d[SHADOW] = want
        d_npc.save(dry, keep_backup=False)
        print(f"    {'LIST_NPC.STB':26s} row {SHADOW} {SHADOW_NAME} (from {TEMPLATE})")
    else:
        print(f"    {'LIST_NPC.STB':26s} row {SHADOW} already in place")

    stl = oro.Stl(P(ours, NPC_STL_REL))
    if not stl.has(SHADOW_STRID):
        stl.append(SHADOW_STRID, SHADOW, SHADOW_NAME)    # NRST01: a name only
        stl.save(dry, keep_backup=False)
        print(f"    {'LIST_NPC_S.STL':26s} +1 key {SHADOW_STRID}")

    oro.import_characters([SHADOW], ours, src, dry, SHADOW_NAME, src_of={SHADOW: SHADOW_SRC})
    for slot, blob in build_clips(ours).items():
        changed = write_if_changed(P(ours, CLIPS[slot]), blob, dry)
        print(f"    {os.path.basename(CLIPS[slot]):26s} slot {slot} "
              f"{'written' if changed else 'in place'}")
    if not dry:
        set_clip_slots(ours, dry)

    sk = oro.Stb(P(ours, SKILL_STB_REL))
    sk_dirty = False
    for row, srow, name, cells, strid, _desc in SKILLS:
        if sk.rows <= row:
            sk.grow_to(row + 1)
        cur = sk.get(row, SK_NAME).decode("latin-1").strip()
        if cur and cur != name:
            raise SystemExit(f"our LIST_SKILL row {row} is {cur!r}")
        want = skill_row(sk, srow, name, row, cells, strid)
        if sk.d[row] != want:
            sk.d[row] = want
            sk_dirty = True
            print(f"    {'LIST_SKILL.STB':26s} row {row} {name} (from {srow})")
    if sk_dirty:
        sk.save(dry, keep_backup=False)
    skl = oro.Stl(P(ours, SKILL_STL_REL))
    added = 0
    for row, _srow, name, _cells, strid, desc in SKILLS:
        if not skl.has(strid):
            skl.append(strid, row, name, desc)
            added += 1
    if added:
        skl.save(dry, keep_backup=False)
        print(f"    {'LIST_SKILL_S.STL':26s} +{added} keys")

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
    row = d_npc.d[SHADOW]
    check(row[C_NAME] == SHADOW_NAME.encode(), f"LIST_NPC {SHADOW} is {SHADOW_NAME}")
    for c, v in STATS.items():
        if c == C_EXP:
            continue
        want = b(SWORD_ROW if c == C_RWEAPON else v)
        if row[c] != want:
            check(False, f"LIST_NPC {SHADOW} col {c} = {want!r} (is {row[c]!r})")
    check(oro.Stl(P(ours, NPC_STL_REL)).has(SHADOW_STRID), f"LIST_NPC_S {SHADOW_STRID}")
    chr_ = oro.Chr(P(ours, NPC_CHR_REL))
    entry = chr_.chars[SHADOW] if SHADOW < len(chr_.chars) else None
    check(entry is not None, f"LIST_NPC.CHR entry {SHADOW}")
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
                  for s, rel in CLIPS.items()), "slots 6-9 on its own clips")
    built = build_clips(ours)
    for slot, rel in CLIPS.items():
        p = P(ours, rel)
        check(os.path.isfile(p) and open(p, "rb").read() == built[slot],
              f"{os.path.basename(rel)} matches the builder")
    w = oro.Stb(P(ours, WEAPON_STB_REL))
    check(w.get(SWORD_ROW, C_NAME) == SWORD_NAME.encode(), f"LIST_WEAPON {SWORD_ROW} is {SWORD_NAME}")
    wz = oro.Zsc(P(ours, WEAPON_ZSC_REL))
    parts = wz.objects[SWORD_ROW][1] if SWORD_ROW < len(wz.objects) else []
    check(bool(parts) and all(os.path.isfile(find_ci(ours, wz.materials[t][0].decode("latin-1")))
                              for _, t, _ in parts), f"LIST_WEAPON.ZSC {SWORD_ROW} model + texture")
    sk = oro.Stb(P(ours, SKILL_STB_REL))
    skl = oro.Stl(P(ours, SKILL_STL_REL))
    for row, srow, name, cells, strid, _desc in SKILLS:
        check(sk.rows > row and sk.d[row] == skill_row(sk, srow, name, row, cells, strid),
              f"LIST_SKILL {row} {name}")
        check(skl.has(strid), f"LIST_SKILL_S {strid}")
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
    print("the sword")
    sword(args.ours, args.src, args.dry_run)
    print("the monster")
    monster(args.ours, args.src, args.dry_run)
    if not args.dry_run:
        sweep_baks(args.ours)
    print("dry run, nothing written" if args.dry_run else "done -- run --verify")
    return 0


if __name__ == "__main__":
    sys.exit(main())
