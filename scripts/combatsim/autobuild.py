"""Starting builds: stats, gear and passives picked automatically for a class and level.

This is a convenience, not a claim about real players: it picks the best ATK weapon in
the newest tier the level unlocks, the best DEF+RES armour piece per slot, and every
passive the class can learn at its top rank. Edit the result in the Dev Studio tab.
"""
from .data import AT, JOBS, SLOTS
from .player import Build, auto_stats

# stat weights and usable weapon types per job (the old balance-sim profiles)
PROFILES = {
    111: dict(w=dict(STR=5, CON=3, DEX=2), wt=(211, 212)),
    121: dict(w=dict(STR=5, CON=3, DEX=1, SENSE=1), wt=(211, 212), shield=True),
    122: dict(w=dict(STR=5, CON=3, SENSE=2), wt=(221, 222, 223)),
    211: dict(w=dict(INT=5, SENSE=3, CON=2), wt=(242, 241)),
    221: dict(w=dict(INT=5, SENSE=3, CON=2), wt=(242, 241)),
    222: dict(w=dict(INT=5, CHARM=2, CON=3), wt=(241, 242)),
    311: dict(w=dict(DEX=5, STR=3, SENSE=2), wt=(251, 231)),
    321: dict(w=dict(STR=3, DEX=4, SENSE=3), wt=(251, 252, 253)),
    322: dict(w=dict(DEX=5, SENSE=3, CON=2), wt=(231,)),
    411: dict(w=dict(CON=4, DEX=3, SENSE=3), wt=(232, 271)),
    421: dict(w=dict(CON=4, DEX=3, SENSE=3), wt=(271, 232)),
    422: dict(w=dict(CON=4, DEX=3, SENSE=3), wt=(232, 271)),
}
JUNK = ("GM ", "GameMaster", "Game Master", "Christmas", "Wreath", "Test")
AMMO_TYPES = {0: 431, 1: 432, 2: 433}   # LIST_NATURAL type of arrows/bullets/throwing


def _ok(gd, table, r, level):
    s = gd.stb(table)
    if not s.occupied(r):
        return False
    name = gd.name(table, r)
    return not any(j in name for j in JUNK)


def can_equip(gd, job, itype, row):
    """CUserDATA::Check_JobCollection(ITEM_EQUIP_REQUIRE_CLASS): LIST_CLASS row's job list
    (cols 1..8, CLASS_INCLUDE_JOB); an empty list lets every job through."""
    cls = gd.item_req_class(itype, row)
    c = gd.stb("LIST_CLASS")
    if c.i(cls, 1) == 0:
        return True
    for n in range(8):
        j = c.i(cls, 1 + n)
        if j == 0:
            return False
        if j == job:
            return True
    return False


def best_weapon(gd, level, wtypes, job=None):
    s = gd.stb("LIST_WEAPON")
    c = []
    for r in range(1, s.rows):
        if s.i(r, 4) not in wtypes or s.i(r, 35) <= 0 or not _ok(gd, "LIST_WEAPON", r, level):
            continue
        if job is not None and not can_equip(gd, job, 8, r):
            continue
        rl = gd.item_req_level(8, r)
        if rl > level:
            continue
        c.append((rl, s.i(r, 35) * 2 + s.i(r, 8), r))
    if not c:
        return 0
    top = max(x[0] for x in c)
    return max((x for x in c if x[0] >= top - 10), key=lambda x: x[1])[2]


def best_armor(gd, itype, level, only_type=None, job=None):
    from .data import ITEM_TABLES
    table = ITEM_TABLES[itype]
    s = gd.stb(table)
    cands = []
    for r in range(1, s.rows):
        if only_type and s.i(r, 4) != only_type:
            continue
        if not _ok(gd, table, r, level) or gd.item_req_level(itype, r) > level:
            continue
        if job is not None and not can_equip(gd, job, itype, r):
            continue
        d, res = s.i(r, 31), s.i(r, 32)
        if d <= 0 and res <= 0:
            continue
        cands.append((d + res, gd.item_req_level(itype, r), r))
    # skip statistical outliers: a few event/import rows carry 5-10x the DEF of their
    # level band (the Ghost/Spirit backpacks 803-805, the level-0 holiday backs) and
    # would make every generated character a tank nobody actually plays
    best, key = 0, None
    for tot, rl, r in cands:
        band = sorted(t for t, l, _ in cands if abs(l - rl) <= 15)
        if len(band) >= 5 and tot > 4 * band[len(band) // 2]:
            continue
        if key is None or (tot, rl) > key:
            best, key = r, (tot, rl)
    return best


def best_ammo(gd, shot, level):
    s = gd.stb("LIST_NATURAL")
    want = AMMO_TYPES.get(shot)
    c = [(s.i(r, 8), r) for r in range(1, s.rows)
         if s.i(r, 4) == want and gd.item_req_level(12, r) <= level]
    return max(c)[1] if c else 0


def class_rows(gd, job):
    """LIST_CLASS rows whose job list includes `job` (SKILL_AVAILBLE_CLASS_SET targets)."""
    s = gd.stb("LIST_CLASS")
    return {r for r in range(s.rows) if job in [s.i(r, c) for c in range(1, 11)]}


def class_skills(gd, job):
    """skill group (first-level row) -> top-rank row, for every skill the job can learn."""
    rows = class_rows(gd, job)
    s = gd.stb("LIST_SKILL")
    groups = {}
    for r in range(1, s.rows):
        if not s.occupied(r):
            continue
        first = s.i(r, 1) or r
        # SKILL_AVAILBLE_CLASS_SET is often filled on the first rank only
        if (s.i(first, 35) or s.i(r, 35)) not in rows:
            continue
        if first not in groups or s.i(r, 2) > s.i(groups[first], 2):
            groups[first] = r
    return groups


def make_build(gd, job, level, female=False):
    prof = PROFILES.get(job, PROFILES[111])
    b = Build(dict(name=f"{JOBS.get(job, job)} {level} (auto)", job=job, level=level,
                   female=female))
    b.stats = auto_stats(level, prof["w"])
    w = best_weapon(gd, level, prof["wt"], job)
    b.equip["weapon"].id = w
    for slot in ("cap", "body", "arms", "foot", "back"):
        b.equip[slot].id = best_armor(gd, SLOTS[slot][0], level, job=job)
    if prof.get("shield"):
        b.equip["subwpn"].id = best_armor(gd, 9, level, only_type=261, job=job)
    from .data import SHOT_BY_WEAPON
    shot = SHOT_BY_WEAPON.get(gd.weapon_type(w)) if w else None
    if shot is not None:
        b.ammo = best_ammo(gd, shot, level)
    groups = class_skills(gd, job)
    b.skills = sorted(r for r in groups.values() if gd.sk(r, 5) == 15
                      and any(f or rt for _, f, rt in gd.skill(r).ability))
    b.notes = ("Auto build: best gear by level, every class passive at top rank. "
               "Stats spend all bonus points by the class weights.")
    return b


def skill_choices(gd, job):
    """(row, name, type) for every non-passive top-rank skill the job can learn."""
    out = []
    for first, r in sorted(class_skills(gd, job).items()):
        t = gd.sk(r, 5)
        if t != 15:
            out.append((r, gd.name("LIST_SKILL", r), t))
    return out


__all__ = ["make_build", "class_skills", "skill_choices", "PROFILES", "AT"]
