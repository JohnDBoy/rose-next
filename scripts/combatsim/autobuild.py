"""Starting builds: stats, gear and skills picked automatically for a class and level.

This is a convenience, not a claim about real players: "best" picks the best ATK weapon
in the newest tier the level unlocks and the best DEF+RES armour piece per slot;
"average" is what a typical player wears (see AVERAGE_*). Either way the skill points
are the ones the server awards by that level, spent on a mix of passives and actives
(spend_skill_points). Edit the result in the Dev Studio tab.
"""
from .data import AT, JOBS, PREFIXED_TABLES, SLOTS
from .player import PSV_ATK_BY_WTYPE, PSV_SPD_BY_WTYPE, STAT_KEYS, Build, StatBlock, auto_stats

# stat weights and usable weapon types per job (the old balance-sim profiles)
# CON as a share of level, spent before the weights: ROSE players run CON about equal to
# their level or 20-30% less, melee nearer the top of that range
MELEE_CON, OTHER_CON = 0.9, 0.75
# normal swings between two skills in an auto-build: casters spam (their auto-attack is
# weak), everyone else weaves a swing in (user guidance, 2026-10-14)
SPAM_JOBS = (211, 221, 222)
SKILL_SPACING = 1
# classes played with their summons out: the auto-build learns the summon skills and the
# capacity passive, and fills the summon bar (user guidance, 2026-10-14: a Bourgeois mixes
# summons and attacking skills; a Scout gets the hawk among its attacks). `skills`: the
# summon skills' first ranks (None = all of the class's); `priority`: bought before the
# other actives, like the own weapon mastery among passives.
SUMMONERS = {
    421: dict(skills=None, priority=False),          # Bourgeois: all three, mixed in
    322: dict(skills=(1711,), priority=False),       # Scout: Call Hawk (not Iron Skin)
}
SUMMONER_JOBS = tuple(SUMMONERS)
AT_PSV_SUMMON_MOB_CNT = 62
MELEE_JOBS = (111, 121, 122, 311, 321)

# "Average" gear (make_build(gear="average")): what a typical player wears rather than
# the best in slot. Their class's armour set of the newest tier (helm, body, gloves,
# boots: every class line has one at levels 10, 30, 50, 70, 88, 104, 120, 145 ...; shops
# sell them up to 70, crafting and the market after), a few prefixed upgrades, low
# refines. Only the upgrades may carry an item prefix (Saint, Demon, Golden ...): a
# level-80 player has two or three prefixed items at most (user guidance, 2026-10-14).
SET_SLOTS = ("cap", "body", "arms", "foot")
AVERAGE_LAG = (10, 25)             # armour required level, this many levels behind
AVERAGE_REFINES = (                # (below level, weapon grade, armour grade)
    (120, 3, 1),
    (180, 4, 2),
    (220, 6, 3),
    (999, 7, 4),
)

BEST_REFINES = (                   # best in slot is also well refined
    (120, 5, 3),
    (180, 7, 4),
    (220, 8, 5),
    (999, 9, 6),
)

PROFILES = {
    # a Soldier has no shield yet, so it swings two-handed (one-handed + shield is the Knight)
    111: dict(w=dict(STR=5, DEX=2), wt=(221, 222, 223)),
    121: dict(w=dict(STR=5, DEX=1, SENSE=1), wt=(211, 212), shield=True),
    122: dict(w=dict(STR=5, SENSE=2), wt=(221, 222, 223)),
    211: dict(w=dict(INT=5, SENSE=3, CON=2), wt=(242, 241)),
    221: dict(w=dict(INT=5, SENSE=3, CON=2), wt=(242, 241)),
    222: dict(w=dict(INT=5, CHARM=2, CON=3), wt=(241, 242)),
    311: dict(w=dict(DEX=5, STR=3, SENSE=2), wt=(251, 231)),
    321: dict(w=dict(STR=3, DEX=4, SENSE=3), wt=(251, 252, 253)),
    322: dict(w=dict(DEX=5, SENSE=3, CON=2), wt=(231,)),
    # the Dealer line's skills all need a gun or launcher (232/233), never a crossbow
    411: dict(w=dict(CON=4, DEX=3, SENSE=3), wt=(232, 233)),
    421: dict(w=dict(CON=4, DEX=3, SENSE=3), wt=(232, 233)),
    422: dict(w=dict(CON=4, DEX=3, SENSE=3), wt=(232, 233)),
}
JUNK = ("GM ", "GameMaster", "Game Master", "Christmas", "Wreath", "Test")
EVENT_PREFIXES = range(9, 17)          # STR_ITEMPREFIX [Costume], [Event], [X-mas] ...

# Skill points: a typical player spreads them over passives and actives instead of
# maxing every passive first (user guidance, 2026-10-14); this is the passives' share.
PASSIVE_SHARE = 0.5
AMMO_TYPES = {0: 431, 1: 432, 2: 433}   # LIST_NATURAL type of arrows/bullets/throwing


def prefix_id(gd, table, r):
    """CItem::GetItemRareType: the STR_ITEMPREFIX id (col_count - 2), 0 = none."""
    if table not in PREFIXED_TABLES:
        return 0
    s = gd.stb(table)
    return max(0, s.i(r, s.cols - 2))


def _ok(gd, table, r, level):
    s = gd.stb(table)
    if not s.occupied(r) or prefix_id(gd, table, r) in EVENT_PREFIXES:
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


def class_only(gd, itype, row):
    """The item names a LIST_CLASS job list (class gear), rather than any job."""
    return gd.stb("LIST_CLASS").i(gd.item_req_class(itype, row), 1) != 0


def _armor_candidates(gd, itype, level, only_type=None, job=None, plain=False,
                      own_class=False):
    """(DEF+RES, required level, row) the job can wear at `level`, outliers dropped;
    `plain` leaves out prefixed (rare) items, `own_class` items any job can wear."""
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
        if plain and prefix_id(gd, table, r):
            continue
        if own_class and not class_only(gd, itype, r):
            continue
        d, res = s.i(r, 31), s.i(r, 32)
        if d <= 0 and res <= 0:
            continue
        cands.append((d + res, gd.item_req_level(itype, r), r))
    # skip statistical outliers: a few event/import rows carry 5-10x the DEF of their
    # level band (the Ghost/Spirit backpacks 803-805, the level-0 holiday backs) and
    # would make every generated character a tank nobody actually plays
    out = []
    for tot, rl, r in cands:
        band = sorted(t for t, l, _ in cands if abs(l - rl) <= 15)
        if len(band) >= 5 and tot > 4 * band[len(band) // 2]:
            continue
        out.append((tot, rl, r))
    return out


def best_armor(gd, itype, level, only_type=None, job=None, own_class=False):
    cands = (own_class and _armor_candidates(gd, itype, level, only_type, job,
                                             own_class=True)) \
        or _armor_candidates(gd, itype, level, only_type, job)
    return max(cands, key=lambda x: (x[0], x[1]))[2] if cands else 0


def class_set(gd, job, level):
    """{slot: row} -- the job's plain armour set of the newest tier it can wear: the
    highest required level at which class-only, unprefixed helm, body, gloves and boots
    all exist. Where a tier holds two sets (Steam / Crystal at 220), the pieces are
    grouped by their first word and the set with the most DEF+RES wins."""
    by_tier = {}
    for slot in SET_SLOTS:
        itype = SLOTS[slot][0]
        for tot, rl, r in _armor_candidates(gd, itype, level, job=job, plain=True,
                                            own_class=True):
            by_tier.setdefault(rl, {}).setdefault(slot, []).append((tot, r))
    from .data import ITEM_TABLES
    for rl in sorted(by_tier, reverse=True):
        tier = by_tier[rl]
        if not all(slot in tier for slot in SET_SLOTS):
            continue
        if all(len(tier[slot]) == 1 for slot in SET_SLOTS):
            return {slot: tier[slot][0][1] for slot in SET_SLOTS}
        groups = {}
        for slot in SET_SLOTS:
            table = ITEM_TABLES[SLOTS[slot][0]]
            for tot, r in tier[slot]:
                word = gd.name(table, r).split(" ")[0]
                groups.setdefault(word, {}).setdefault(slot, []).append((tot, r))
        full = [g for g in groups.values() if all(slot in g for slot in SET_SLOTS)]
        if full:
            best = max(full, key=lambda g: sum(max(g[slot])[0] for slot in SET_SLOTS))
            return {slot: max(best[slot])[1] for slot in SET_SLOTS}
        return {slot: max(tier[slot])[1] for slot in SET_SLOTS}
    return {}


def average_armor(gd, itype, level, only_type=None, job=None):
    """What a typical player wears: the median plain (unprefixed) piece of an older tier
    (required level AVERAGE_LAG levels under theirs), not the best of the current one."""
    cands = (_armor_candidates(gd, itype, level, only_type, job, plain=True)
             or _armor_candidates(gd, itype, level, only_type, job))
    lo, hi = level - AVERAGE_LAG[1], level - AVERAGE_LAG[0]
    band = [c for c in cands if lo <= c[1] <= hi] or cands
    if not band:
        return 0
    band.sort()
    return band[len(band) // 2][2]


def best_ammo(gd, shot, level):
    s = gd.stb("LIST_NATURAL")
    want = AMMO_TYPES.get(shot)
    eff = gd.stb("LIST_EFFECT")
    # NATURAL_BULLET_NO (col 17) is a LIST_EFFECT row whose col 11 is the projectile
    # (EFFECT_BULLET_NORMAL); Nova/Vortex Bullet and Molten Shell name empty rows and
    # fly invisible, so skip ammo without one
    c = [(s.i(r, 8), r) for r in range(1, s.rows)
         if s.i(r, 4) == want and gd.item_req_level(12, r) <= level
         and eff.i(s.i(r, 17), 11)]
    return max(c)[1] if c else 0


def average_ammo(gd, shot, level):
    """The median-quality ammo with a projectile, rather than the best."""
    s = gd.stb("LIST_NATURAL")
    eff = gd.stb("LIST_EFFECT")
    c = sorted((s.i(r, 8), r) for r in range(1, s.rows)
               if s.i(r, 4) == AMMO_TYPES.get(shot) and gd.item_req_level(12, r) <= level
               and eff.i(s.i(r, 17), 11))
    return c[len(c) // 2][1] if c else 0


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


def skill_ranks(gd, first):
    """Every rank row of the skill whose first rank is `first`, lowest first."""
    s = gd.stb("LIST_SKILL")
    out = [r for r in range(max(1, first), min(s.rows, first + 40))
           if s.occupied(r) and (s.i(r, 1) or r) == first]
    return sorted(out, key=lambda r: s.i(r, 2))


def skill_points(gd, level):
    """Skill points earned by `level`: GetSkillPointAwardForLevel (gs_user.cpp:39) summed
    over every level-up. LIST_SKILL_P rows are (level, points); a level the table does not
    list gets the points of its highest-level row."""
    sp = gd.stb("LIST_SKILL_P")
    award, top = {}, (0, 0)
    for r in range(sp.rows):
        lv, pt = sp.i(r, 0), sp.i(r, 1)
        award[lv] = pt
        if lv > top[0]:
            top = (lv, pt)
    return sum(award.get(lv, top[1]) for lv in range(2, level + 1))


def skills_cost(gd, rows):
    """Skill points a list of learned rows cost: each rank up to the highest one listed
    per skill (SKILL_NEED_LEVELUPPOINT, col 3)."""
    top = {}
    for row in rows:
        first = gd.sk(row, 1) or row
        top[first] = max(top.get(first, -1), gd.sk(row, 2))
    return sum(gd.sk(r, 3) for first, lvl in top.items() for r in skill_ranks(gd, first)
               if gd.sk(r, 2) <= lvl)


def _own_mastery(sk, wtype):
    """True for a passive that raises the build's own weapon's ATK or attack speed."""
    own = {PSV_ATK_BY_WTYPE.get(wtype), PSV_SPD_BY_WTYPE.get(wtype)} - {None}
    if not wtype:
        own.add(AT["PSV_ATK_POW_NO_WEAPON"])
    return any((f or rt) and ab in own for ab, f, rt in sk.ability)


# abilities a passive must raise to be worth points in a fighting build: the combat
# stats and passives (not weight, Charm, buying/selling prices, gathering, troops)
COMBAT_ATS = ({AT[k] for k in ("STR", "DEX", "INT", "CON", "SENSE", "HP", "MP", "ATK", "DEF",
                                "HIT", "RES", "AVOID", "SPEED", "ATK_SPD", "CRITICAL",
                                "RECOVER_HP", "RECOVER_MP", "SAVE_MP", "MAX_HP", "MAX_MP",
                                "PSV_SAVE_MP")}
              | set(range(AT["PSV_ATK_POW_NO_WEAPON"], AT["PSV_WEIGHT"]))
              | set(range(AT["PSV_RES"], AT["AFTER_PASSIVE_SKILL_2ND"])))
NON_COMBAT_TYPES = (1, 2, 10, 11, 14, 20)   # basic actions, crafting, heals, summons, revive


def _passive_fits(sk, wtype, summons=False):
    """False for a weapon mastery of another weapon type (AT_PSV_ATK_POW_* / _SPD_*) and for
    a passive that raises nothing a fight uses (the summon capacity counts for a summoner)."""
    own = {PSV_ATK_BY_WTYPE.get(wtype), PSV_SPD_BY_WTYPE.get(wtype)}
    if not wtype:
        own.add(AT["PSV_ATK_POW_NO_WEAPON"])
    useful = COMBAT_ATS | ({AT_PSV_SUMMON_MOB_CNT} if summons else set())
    for ab, flat, rate in sk.ability:
        if not (flat or rate) or ab not in useful:
            continue
        if not (AT["PSV_ATK_POW_NO_WEAPON"] <= ab <= AT["PSV_ATK_SPD_PAIR"]) or ab in own:
            return True
    return False


def spend_skill_points(gd, job, level, wtype, stats, share=PASSIVE_SHARE, summons=None):
    """The skill rows a typical player has learned: the server's points for `level`,
    one rank at a time, keeping passives near `share` of the points spent and buying
    the cheapest next rank in each kind -- so several skills climb together instead of
    every passive maxing first. The one exception is the mastery of the build's own
    weapon (and what it requires): players max it early, so it is bought before the
    other passives. Ranks respect the server's prerequisites (Skill_
    CheckLearnedSKILL, cols 39-44) and ability requirements (cols 45-48: level, stats).
    Skips weapon masteries for other weapons, actives the weapon cannot use, crafting,
    trade and other non-combat skills, heals, summons (unless `summons`, a SUMMONERS entry:
    then its summon skills count as actives -- bought first when it says `priority` -- and
    the summon capacity passive as useful), and skills no rank of which costs points."""
    sk_ = gd.sk
    groups = class_skills(gd, job)
    want = {}
    for first, top in groups.items():
        ranks = skill_ranks(gd, first)
        if not ranks or not sum(sk_(r, 3) for r in ranks):
            continue
        sk = gd.skill(top)
        if sk.is_passive():
            if any(f or rt for _, f, rt in sk.ability) and _passive_fits(sk, wtype,
                                                                         bool(summons)):
                want[first] = ("passive", ranks)
        elif sk.is_damage() and sk.power <= 0:
            continue                    # no SKILL_POWER: Double Scratch, never used
        elif sk.type not in NON_COMBAT_TYPES or (
                summons and sk.type == 14
                and (summons["skills"] is None or first in summons["skills"])):
            need = [w for w in sk.need_weapon if w]
            if not need or wtype in need or wtype // 10 in need:
                want[first] = ("active", ranks)
    # the prerequisites of what is wanted are bought too, whatever they are; those of the
    # own weapon mastery share its priority
    def prereqs(first):
        for r in want[first][1]:
            for t in range(3):
                v = sk_(r, 39 + 2 * t)
                if v:
                    yield sk_(v, 1) or v

    todo = list(want)
    while todo:
        for g in prereqs(todo.pop()):
            ranks = skill_ranks(gd, g) if g not in want else None
            if ranks:
                want[g] = ("passive" if sk_(ranks[-1], 5) == 15 else "active", ranks)
                todo.append(g)
    core = {g for g, (kind, ranks) in want.items()
            if kind == "passive" and _own_mastery(gd.skill(ranks[-1]), wtype)}
    if summons and summons["priority"]:
        core |= {g for g in summons["skills"] or () if g in want}
    todo = list(core)
    while todo:
        for g in prereqs(todo.pop()):
            if g in want and g not in core:
                core.add(g)
                todo.append(g)
    have = {}                                   # first -> ranks learned

    def ok(r):
        for t in range(3):
            v, n = sk_(r, 39 + 2 * t), sk_(r, 40 + 2 * t)
            if v and have.get(sk_(v, 1) or v, 0) < max(1, n):
                return False
        for t in range(2):
            at, n = sk_(r, 45 + 2 * t), sk_(r, 46 + 2 * t)
            if at == AT["LEVEL"] and level < n:
                return False
            if AT["STR"] <= at <= AT["SENSE"] and stats.get(STAT_KEYS[at - AT["STR"]], 0) < n:
                return False
        return True

    left = skill_points(gd, level)
    spent = {"passive": 0, "active": 0}
    while True:
        cands = []
        for first, (kind, ranks) in want.items():
            i = have.get(first, 0)
            if i < len(ranks) and sk_(ranks[i], 3) <= left and ok(ranks[i]):
                cands.append((kind, 0 if first in core else 1, sk_(ranks[i], 3), i, first))
        if not cands:
            break
        tot = spent["passive"] + spent["active"]
        kind = "passive" if spent["passive"] <= share * tot else "active"
        pick = min([c for c in cands if c[0] == kind] or cands, key=lambda c: c[1:])
        have[pick[4]] = pick[3] + 1
        spent[pick[0]] += pick[2]
        left -= pick[2]
    rows = sorted(want[g][1][n - 1] for g, n in have.items() if n)
    return rows, spent, left


USEFUL_DEBUFFS = ("DEC_APOWER", "DEC_DPOWER", "DEC_RES", "DEC_HIT", "DEC_AVOID", "DEC_ATK_SPD",
                  "DEC_CRITICAL", "FAINTING", "DUMB")


def auto_rotation(gd, rows):
    """A rotation from learned skill rows: the debuffs that hit the monster first (a
    harmful state cast on the target, types 9/13), then the damage skills, strongest
    SKILL_POWER first. The fight casts the first one that is ready, so a debuff opens
    and is recast when it drops, and the big hitters go out whenever they are up.
    Only debuffs that matter one on one count (USEFUL_DEBUFFS): not Taunt, not a move
    slow, not a sleep (the next hit wakes it). Self and party buffs stay out: they
    belong in the build's buffs."""
    from .data import ING
    useful = {ING[k] for k in USEFUL_DEBUFFS}
    debuffs, damage = [], []
    for r in rows:
        sk = gd.skill(r)
        if sk.is_passive():
            continue
        if sk.is_damage():
            if sk.power > 0:            # a damage skill with no power is never cast
                damage.append((-sk.power, r))
        elif sk.type in (9, 13) and any(st and gd.state_type(st) in useful for st in sk.states):
            debuffs.append((-sk.power, r))
    return [r for _, r in sorted(debuffs)] + [r for _, r in sorted(damage)]


def fill_summons(gd, b, allowed=None):
    """The summon bar a summoner keeps full: the learned summon skills, the one taking the
    most capacity (the strongest) first, one of each in turn until none fits
    (CUserDATA::GetMax_SummonCNT vs NPC_NEED_SUMMON_CNT, LIST_NPC col 21)."""
    npc = gd.stb("LIST_NPC")
    kinds = sorted((r for r in b.skills if gd.sk(r, 5) == 14 and gd.sk(r, 28) > 0
                    and (allowed is None or (gd.sk(r, 1) or r) in allowed)),
                   key=lambda r: -npc.i(gd.sk(r, 28), 21))
    cap = StatBlock(gd, b).summon_capacity
    out, used, added = [], 0, True
    while added:
        added = False
        for r in kinds:
            need = npc.i(gd.sk(r, 28), 21)
            if used + need <= cap:
                out.append(r)
                used += need
                added = True
    return out


def con_floor(job):
    return MELEE_CON if job in MELEE_JOBS else OTHER_CON


def average_upgrades(level):
    """Slots an average player has at the current tier: the weapon always, the body from
    60, the back from 150 -- the "one to three better items than usual". Only these may
    be prefixed items."""
    return ("weapon",) + (("body",) if level >= 60 else ()) + (("back",) if level >= 150 else ())


def refines(level, table):
    """(weapon grade, armour grade) at `level` from AVERAGE_REFINES or BEST_REFINES. A
    typical player sits at +1..+3 for most of the levelling, more at the top (user
    guidance, 2026-10-14); best in slot is a few grades higher."""
    for lv, wg, ag in table:
        if level < lv:
            return wg, ag
    return table[-1][1], table[-1][2]


def make_build(gd, job, level, female=False, gear="best"):
    """A starting build. gear="best": best in slot at the level, refined per BEST_REFINES.
    gear="average": what a typical player runs -- see average_upgrades/average_refines."""
    prof = PROFILES.get(job, PROFILES[111])
    label = "average" if gear == "average" else "best gear"
    b = Build(dict(name=f"{JOBS.get(job, job)} {level} ({label})", job=job, level=level,
                   female=female))
    b.stats = auto_stats(level, prof["w"], con_floor(job))
    w = best_weapon(gd, level, prof["wt"], job)
    b.equip["weapon"].id = w
    up = average_upgrades(level) if gear == "average" else None
    cset = class_set(gd, job, level) if up is not None else {}
    for slot in ("cap", "body", "arms", "foot", "back"):
        if up is None or slot in up:
            # best in slot / an upgrade: the best piece, the class's own where it has one
            b.equip[slot].id = best_armor(gd, SLOTS[slot][0], level, job=job,
                                          own_class=slot in SET_SLOTS)
        elif slot in cset:
            b.equip[slot].id = cset[slot]
        else:
            b.equip[slot].id = average_armor(gd, SLOTS[slot][0], level, job=job)
    if prof.get("shield"):
        pick = best_armor if up is None else average_armor
        b.equip["subwpn"].id = pick(gd, 9, level, only_type=261, job=job)
    from .data import SHOT_BY_WEAPON
    shot = SHOT_BY_WEAPON.get(gd.weapon_type(w)) if w else None
    if shot is not None:
        b.ammo = (best_ammo if up is None else average_ammo)(gd, shot, level)
    wg, ag = refines(level, BEST_REFINES if up is None else AVERAGE_REFINES)
    for slot, it in b.equip.items():
        if it.id:
            it.grade = wg if slot == "weapon" else ag
    summoner = SUMMONERS.get(job)
    b.skills, spent, left = spend_skill_points(gd, job, level, gd.weapon_type(w) if w else 0,
                                               b.stats, summons=summoner)
    if summoner:
        b.summons = fill_summons(gd, b, summoner["skills"])
    b.rotation = auto_rotation(gd, b.skills)
    b.skill_spacing = 0 if job in SPAM_JOBS else SKILL_SPACING
    sp = (f"{spent['passive'] + spent['active']} skill points (passives {spent['passive']}, "
          f"actives {spent['active']}, {left} left)")
    if up is None:
        b.notes = (f"Auto build, best gear: best item per slot at this level, weapon +{wg}, "
                   f"armour +{ag}, no gems; {sp}.")
    else:
        b.notes = (f"Auto build, average gear: the class armour set of the newest tier, "
                   f"best {', '.join(up)}; weapon +{wg}, armour +{ag}; no gems; {sp}.")
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
