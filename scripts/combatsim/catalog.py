"""Pick lists for a build editor: items per slot, gems, ammo, skills, buffs, potions, monsters.

Each entry is (row, name, detail, sort_level); the detail is a short summary a picker
shows next to the name.
"""
from .autobuild import AMMO_TYPES, class_rows, class_skills
from .data import AT_NAME, ITEM_TABLES, JOBS, SLOTS

STAT_SHORT = {"STR": "STR", "DEX": "DEX", "INT": "INT", "CON": "CON", "CHARM": "CHA",
              "SENSE": "SEN", "ATK": "ATK", "DEF": "DEF", "HIT": "HIT", "RES": "RES",
              "AVOID": "AVO", "ATK_SPD": "ASPD", "CRITICAL": "CRIT", "MAX_HP": "HP",
              "MAX_MP": "MP", "SPEED": "MOVE", "SAVE_MP": "SaveMP"}


def bonus_text(pairs):
    out = []
    for ab, val in pairs:
        if ab and val:
            name = AT_NAME.get(ab, str(ab))
            out.append(f"{STAT_SHORT.get(name, name)} {val:+d}")
    return ", ".join(out)


def items(gd, slot):
    itype = SLOTS[slot][0]
    table = ITEM_TABLES[itype]
    s = gd.stb(table)
    names = gd.names(table)
    out = []
    for r in range(1, s.rows):
        if not s.occupied(r):
            continue
        if not (names.get(r) or s.s(r, 0).strip()):
            continue
        name = gd.name(table, r)          # with the in-game prefix (Saint, Dark ...)
        lv = gd.item_req_level(itype, r)
        bonus = bonus_text([(t, v) for _, t, v in gd.item_add(itype, r)])
        if itype == 8:
            atk = s.i(r, 35)
            if atk <= 0:
                continue
            detail = f"ATK {atk} · spd {s.i(r, 36)} · type {s.i(r, 4)}"
        else:
            d, res = s.i(r, 31), s.i(r, 32)
            if d <= 0 and res <= 0 and not bonus:
                continue
            detail = f"DEF {d} RES {res}" if (d or res) else ""
        if bonus:
            detail = f"{detail} · {bonus}" if detail else bonus
        if lv:
            detail += f" · Lv {lv}"
        out.append((r, name, detail, lv))
    out.sort(key=lambda e: (e[3], e[1]))
    return out


def gems(gd):
    s = gd.stb("LIST_JEMITEM")
    names = gd.names("LIST_JEMITEM")
    out = []
    for r in range(1, s.rows):
        txt = bonus_text(gd.gem_add(r))
        if not txt:
            continue
        name = names.get(r) or s.s(r, 0).strip() or f"option {r}"
        kind = "gem" if r > 300 else "option"
        out.append((r, name, f"{txt} · {kind}", r))
    return out


def ammo(gd, shot):
    s = gd.stb("LIST_NATURAL")
    want = AMMO_TYPES.get(shot)
    out = [(r, gd.name("LIST_NATURAL", r), f"quality {s.i(r, 8)}", s.i(r, 8))
           for r in range(1, s.rows) if s.i(r, 4) == want]
    out.sort(key=lambda e: e[3])
    return out


def _skill_entry(gd, r):
    sk = gd.skill(r)
    bits = []
    if sk.is_damage():
        bits.append(f"power {sk.power}")
    for n, st in enumerate(sk.states):
        if st:
            ab, flat, rate = sk.ability[n]
            what = AT_NAME.get(ab, "")
            if flat or rate:
                bits.append(f"{STAT_SHORT.get(what, what)} {flat:+d}{f' {rate:+d}%' if rate else ''}")
            else:
                bits.append(gd.name("LIST_STATUS", st))
    if not sk.is_passive():
        bits.append(f"cd {sk.reload_ms / 1000:.1f}s")
    if sk.is_passive():
        bits = [bonus_text([(a, f) for a, f, _ in sk.ability]) or ""]
        rates = [(a, r_) for a, _, r_ in sk.ability if r_]
        if rates:
            bits.append(", ".join(f"{STAT_SHORT.get(AT_NAME.get(a, ''), AT_NAME.get(a, a))} "
                                  f"{v:+d}%" for a, v in rates))
    return (r, sk.name, " · ".join(b for b in bits if b) + f" · rank {sk.level}", sk.level)


def class_skill_lists(gd, job):
    """(passives, actives) for a job, top rank of each skill."""
    passives, actives = [], []
    for first, r in sorted(class_skills(gd, job).items()):
        if gd.sk(r, 5) == 15:
            # a passive with no effect column filled is dead data (e.g. Reload Mastery stubs)
            if any(f or rt for _, f, rt in gd.skill(r).ability):
                passives.append(_skill_entry(gd, r))
        else:
            actives.append(_skill_entry(gd, r))
    return passives, actives


def summon_skills(gd, job):
    """(row, name, detail, None) for the job's summon skills (type 14), top rank: what
    each calls (LIST_SKILL col 28) and the capacity it takes (LIST_NPC col 21)."""
    out = []
    npc = gd.stb("LIST_NPC")
    for first, r in sorted(class_skills(gd, job).items()):
        if gd.sk(r, 5) != 14 or gd.sk(r, 28) <= 0:
            continue
        row = gd.sk(r, 28)
        out.append((r, gd.name("LIST_SKILL", r),
                    f"calls {gd.name('LIST_NPC', row)}, capacity {npc.i(row, 21)}", None))
    return out


def skill_ranks(gd, row):
    """Every rank row of the skill `row` belongs to, lowest first."""
    first = gd.sk(row, 1) or row
    s = gd.stb("LIST_SKILL")
    out = [r for r in range(max(1, first), min(s.rows, first + 40))
           if s.occupied(r) and (s.i(r, 1) or r) == first]
    return sorted(out, key=lambda r: s.i(r, 2))


def buff_skills(gd, include_cleric=False):
    """Self and party buffs (types 8/9/12/13 with a beneficial state), any class."""
    s = gd.stb("LIST_SKILL")
    cls = gd.stb("LIST_CLASS")
    cleric_only = {r for r in range(cls.rows)
                   if {cls.i(r, c) for c in range(1, 11)} - {0} <= {222, 232}
                   and any(cls.i(r, c) for c in range(1, 11))}
    names = gd.names("LIST_SKILL")
    groups = {}
    for r in range(1, s.rows):
        if not s.occupied(r) or s.i(r, 5) not in (8, 9, 12, 13) or r not in names:
            continue
        states = [s.i(r, 11), s.i(r, 12)]
        if not any(st and not gd.state_harmful(st) for st in states):
            continue
        first = s.i(r, 1) or r
        # player skills: learnable (skill points) or tied to a class on their first rank
        cset = s.i(first, 35) or s.i(r, 35)
        if not cset and not s.i(r, 3) and not s.i(first, 3):
            continue
        if not include_cleric and cset in cleric_only:
            continue
        if first not in groups or s.i(r, 2) > s.i(groups[first], 2):
            groups[first] = r
    out = []
    for r in sorted(groups.values()):
        e = _skill_entry(gd, r)
        first = s.i(r, 1) or r
        cset = s.i(first, 35) or s.i(r, 35)
        who = gd.name("LIST_CLASS", cset) if cset else "any class"
        out.append((r, e[1], f"{e[2]} · {who}", e[3]))
    return out


def potions(gd, kind):
    want = 16 if kind == "hp" else 17
    s = gd.stb("LIST_USEITEM")
    out = []
    for r in range(1, s.rows):
        if s.i(r, 19) != want or s.i(r, 20) <= 0:
            continue
        st = s.i(r, 24)
        if st:
            per = next((v for _, v in (gd.state_apply(st, n) for n in range(2)) if v), 0)
            how = f"{s.i(r, 20)} over {s.i(r, 20) / per:.0f} s" if per else f"{s.i(r, 20)}"
        else:
            how = f"{s.i(r, 20)} instant"
        out.append((r, gd.name("LIST_USEITEM", r), how, r))
    return out


def monsters(gd):
    s = gd.stb("LIST_NPC")
    names = gd.names("LIST_NPC")
    out = []
    for r in range(1, s.rows):
        if not s.occupied(r):
            continue
        atk, hpc, lv = s.i(r, 9), s.i(r, 8), max(1, s.i(r, 7))
        if atk <= 0 or hpc <= 0:
            continue
        name = names.get(r) or s.s(r, 0).strip()
        if not name:
            continue
        out.append((r, name, f"Lv {lv} · HP {lv * hpc:,} · ATK {atk} · DEF {s.i(r, 11)}", lv))
    out.sort(key=lambda e: (e[3], e[1]))
    return out


def jobs():
    return [(j, n) for j, n in JOBS.items() if j]


__all__ = ["items", "gems", "ammo", "class_skill_lists", "skill_ranks", "buff_skills",
           "potions", "monsters", "jobs", "class_rows"]
