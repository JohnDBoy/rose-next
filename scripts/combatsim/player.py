"""A character build and the server's stat block for it.

Ports (all server build, on foot -- mounted characters are out of scope):
  cuserdata.cpp   Cal_BattleAbility, Cal_MaxHP/MP, Cal_DEFENCE, Cal_RESIST, Cal_AvoidRATE,
                  Cal_CRITICAL, Cal_RecoverHP/MP, InitPassiveSkill, GetPassiveSkill*
  cobjavt.cpp     Cal_ATTACK, Cal_HIT, update_speed, Get_BaseAbilityValue
  mounted_item_bonuses.h  accumulate_item_bonuses
  mounted_stats.h resistance()
  gs_user.cpp     classUSER::total_* (+ server.toml [game] base_*)

The steady state modelled is a character **after a login**: InitPassiveSkill has
run, then Cal_BattleAbility, which is what every later stat recompute repeats.
One server bug follows from that order and the simulator reproduces it by default
(`fix_passive_bugs=True` shows the intended numbers instead): percentage STR..SENSE
passives are only computed in Skill_LEARN, so after a login they give nothing. No
skill in the data uses one (2026-10-14). The other one -- Cal_BattleAbility zeroing
the second passive range (AT_PSV_RES/HIT/CRITICAL/AVOID/SHIELD_DEF) -- was fixed
on the server on 2026-10-14 and is no longer modelled.
"""
import json

from .data import AT, SHOT_BY_WEAPON, SLOTS

BASE_STATS = dict(STR=15, DEX=15, INT=15, CON=15, CHARM=10, SENSE=10)  # INIT_AVATAR.STB
STAT_KEYS = ("STR", "DEX", "INT", "CON", "CHARM", "SENSE")
MAX_STAT = 300                                                            # GameStaticConfig

# Cal_MaxHP / Cal_MaxMP job tables (cuserdata.cpp:283-391); default = visitor
HP_TAB = {111: (7, 12), 121: (-3, 14), 122: (2, 13), 211: (11, 10), 221: (11, 10),
          222: (5, 11), 311: (10, 11), 321: (2, 13), 322: (11, 11), 411: (12, 10),
          421: (13, 10), 422: (6, 11)}
MP_TAB = {111: (3, 4.0), 121: (0, 4.5), 122: (-6, 5.0), 211: (0, 6.0), 221: (-7, 7.0),
          222: (-4, 6.5), 311: (4, 4.0), 321: (4, 4.0), 322: (0, 4.5), 411: (3, 4.0),
          421: (3, 4.0), 422: (0, 4.5)}

# GetPassiveSkillAttackPower / GetPassiveSkillAttackSpeed weapon-type maps
PSV_ATK_BY_WTYPE = {211: 42, 212: 42, 221: 43, 222: 43, 223: 43, 231: 44, 232: 45, 233: 45,
                    253: 45, 241: 46, 242: 46, 251: 48, 252: 48, 271: 47}
PSV_SPD_BY_WTYPE = {231: 49, 232: 50, 233: 50, 251: 51, 252: 51}

# Cal_HIT: the weapon's hit rate is ITEM_QUALITY x this (WEAPON_HIT_PER_QUALITY in
# citem.h; retail 0.6)
WEAPON_HIT_QUALITY = 1.4
DURABILITY_SLOTS = ("cap", "body", "back", "arms", "foot", "subwpn")  # Cal_BattleAbility


def short(v):
    v = int(v) & 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


def total_bonus_points(level):
    """gs_user.cpp Add_EXP: AddCur_BonusPOINT((short)(level*0.8) + 10) per level gained."""
    return sum(int(l * 0.8) + 10 for l in range(2, level + 1))


def stat_point_cost(base, target):
    """Get_NeedPoint2AbilityUP: (short)(current * 0.2) per +1."""
    return sum(int(v * 0.2) for v in range(base, target))


def auto_stats(level, weights, con_floor=0.0):
    """Spend a level's bonus points: CON up to `con_floor` x level first (players run CON
    about equal to their level, or 20-30% less -- more for melee), then the rest across
    stats in proportion to `weights`."""
    st = dict(BASE_STATS)
    bp = total_bonus_points(level)
    target = min(MAX_STAT, int(level * con_floor))
    while st["CON"] < target and int(st["CON"] * 0.2) <= bp:
        bp -= int(st["CON"] * 0.2)
        st["CON"] += 1
    order = [k for k in STAT_KEYS if weights.get(k, 0) > 0]
    tot = sum(weights[k] for k in order) or 1
    while bp > 0 and order:
        gained = {k: st[k] - BASE_STATS[k] for k in order}
        g = sum(gained.values()) or 1
        pick, worst = None, None
        for k in order:
            if st[k] >= MAX_STAT:
                continue
            deficit = weights[k] / tot - gained[k] / g
            if worst is None or deficit > worst:
                pick, worst = k, deficit
        if pick is None:
            break
        cost = int(st[pick] * 0.2)
        if cost > bp:
            break
        st[pick] += 1
        bp -= cost
    return st


class Item:
    def __init__(self, slot, d):
        d = d or {}
        self.slot = slot
        self.itype, self.equip_idx = SLOTS[slot]
        self.id = int(d.get("id", 0))
        self.grade = max(0, min(9, int(d.get("grade", 0))))
        self.gem = int(d.get("gem", 0))          # LIST_JEMITEM row: option (<=300) or gem
        self.durability = d.get("durability")    # None = the table's base durability

    def to_json(self):
        d = dict(id=self.id)
        if self.grade:
            d["grade"] = self.grade
        if self.gem:
            d["gem"] = self.gem
        if self.durability is not None:
            d["durability"] = self.durability
        return d


class Build:
    """A character as a JSON-friendly record (what the Dev Studio tab edits)."""

    def __init__(self, d=None):
        d = d or {}
        self.name = d.get("name", "New build")
        self.job = int(d.get("job", 121))
        self.level = int(d.get("level", 100))
        self.female = bool(d.get("female", False))
        self.union = int(d.get("union", 0))
        st = d.get("stats") or {}
        self.stats = {k: int(st.get(k, BASE_STATS[k])) for k in STAT_KEYS}
        self.equip = {s: Item(s, (d.get("equip") or {}).get(s)) for s in SLOTS}
        self.ammo = int(d.get("ammo", 0))                    # LIST_NATURAL row
        self.skills = [int(x) for x in d.get("skills", [])]  # learned rows (passives count)
        self.rotation = [int(x) for x in d.get("rotation", [])]
        # normal swings the player throws between two skills; 0 = cast whenever one is
        # ready (spam). Older builds have none: 0, the behaviour they were checked with.
        self.skill_spacing = int(d.get("skill_spacing", 0))
        # summon skill rows (one entry per summon kept out; a row may repeat)
        self.summons = [int(x) for x in d.get("summons", [])]
        self.buffs = [dict(skill=int(b["skill"]), caster_int=int(b.get("caster_int", 0)),
                           caster_level=int(b.get("caster_level", 0)))
                      for b in d.get("buffs", [])]
        p = d.get("potions") or {}
        self.potions = dict(
            enabled=bool(p.get("enabled", False)),
            hp=int(p.get("hp", 0)), hp_below=int(p.get("hp_below", 50)),
            mp=int(p.get("mp", 0)), mp_below=int(p.get("mp_below", 30)),
            # a longer reuse delay than the client's 500 ms, to try vials with a cooldown
            cooldown_s=float(p.get("cooldown_s", 0)))
        self.notes = d.get("notes", "")

    def to_json(self):
        return dict(
            name=self.name, job=self.job, level=self.level, female=self.female,
            union=self.union, stats=dict(self.stats),
            equip={s: it.to_json() for s, it in self.equip.items() if it.id},
            ammo=self.ammo, skills=list(self.skills), rotation=list(self.rotation),
            skill_spacing=self.skill_spacing, summons=list(self.summons),
            buffs=[dict(b) for b in self.buffs], potions=dict(self.potions),
            notes=self.notes)

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    def save(self, path):
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(self.to_json(), f, indent=2)
            f.write("\n")

    def points_spent(self):
        return sum(stat_point_cost(BASE_STATS[k], v) for k, v in self.stats.items()
                   if v > BASE_STATS[k])


class StatBlock:
    """The server's numbers for a build, before buffs (m_Battle / stats.*)."""

    def __init__(self, gd, build, fix_passive_bugs=False):
        self.gd, self.b = gd, build
        self.fix = fix_passive_bugs
        self.notes = []          # human-readable warnings for the report
        self._compute()

    # ------------------------------------------------------------ passives
    def _passives(self):
        """InitPassiveSkill (cuserdata.cpp:1637). Returns (value, rate, fromValue, fromRate)."""
        gd = self.gd
        psv_add = [0] * AT["MAX"]
        psv_rate = [0] * AT["MAX"]
        from_value = {k: 0 for k in STAT_KEYS}
        stat_rates = {k: 0 for k in STAT_KEYS}
        for row in self.b.skills:
            sk = gd.skill(row)
            if not sk.is_passive():
                continue
            for ab, flat, rate in sk.ability:
                if flat == 0 and rate == 0:
                    continue
                if AT["STR"] <= ab <= AT["SENSE"]:
                    key = STAT_KEYS[ab - AT["STR"]]
                    if rate:
                        stat_rates[key] += rate
                    else:
                        from_value[key] += flat
                elif (AT["PSV_ATK_POW_NO_WEAPON"] <= ab <= AT["AFTER_PASSIVE_SKILL"]
                      or AT["PSV_RES"] <= ab < AT["AFTER_PASSIVE_SKILL_2ND"]):
                    if rate:
                        psv_rate[ab] += rate
                    else:
                        psv_add[ab] += flat
        # Cal_BattleAbility keeps both passive ranges; it zeroed the second one
        # (AT_PSV_RES..AT_PSV_IMMUNITY) until 2026-10-14, which killed Weapon Research's crit.
        if any(stat_rates.values()) and not self.fix:
            self.notes.append("dead passive (server bug, % stat passives lost at login): "
                              + ", ".join(f"{k} +{v}%" for k, v in stat_rates.items() if v))
        return psv_add, psv_rate, from_value, stat_rates

    # ------------------------------------------------------------ items
    def _item_bonuses(self, add):
        """accumulate_equipment_bonuses (on foot)."""
        gd, b = self.gd, self.b
        for slot, it in b.equip.items():
            if it.id < 1:
                continue
            if it.gem:   # counted when IsAppraisal() || HasSocket(); a build's gem is live
                for ab, val in gd.gem_add(it.gem):
                    if 0 <= ab < AT["MAX"]:
                        add[ab] += short(val)
            for need_union, ab, val in gd.item_add(it.itype, it.id):
                if need_union and need_union != b.union:
                    continue
                if 0 <= ab < AT["MAX"]:
                    add[ab] += short(val)

    def _durability(self, it):
        if it.durability is not None:
            return int(it.durability)
        return self.gd.item_durability(it.itype, it.id)

    # ------------------------------------------------------------ main
    def _compute(self):
        gd, b = self.gd, self.b
        L = b.level
        psv_add, psv_rate, from_value, stat_rates = self._passives()
        # CUserDATA::GetMax_SummonCNT: 50 + the summon passives (Summon Mastery ...)
        self.summon_capacity = 50 + psv_add[62]     # AT_PSV_SUMMON_MOB_CNT

        add = [0] * AT["MAX"]
        add[AT["PSV_ATK_POW_NO_WEAPON"]:AT["AFTER_PASSIVE_SKILL"]] = \
            psv_add[AT["PSV_ATK_POW_NO_WEAPON"]:AT["AFTER_PASSIVE_SKILL"]]
        add[AT["PSV_RES"]:AT["AFTER_PASSIVE_SKILL_2ND"]] = \
            psv_add[AT["PSV_RES"]:AT["AFTER_PASSIVE_SKILL_2ND"]]
        rate = list(psv_rate)
        self._item_bonuses(add)
        self.item_add = list(add)

        # Cal_RecoverHP / MP -> short m_nRecoverHP / MP: passive + item + item x passive
        # rate (until 2026-10-14 the item value was only multiplied by the rate, which no
        # recovery passive has, so recovery items counted 0; the field was a wrapping BYTE)
        self.recover_hp = short(psv_add[AT["PSV_RECOVER_HP"]] + add[AT["RECOVER_HP"]]
                                + short(add[AT["RECOVER_HP"]] * rate[AT["PSV_RECOVER_HP"]] / 100.0))
        self.recover_mp = short(psv_add[AT["PSV_RECOVER_MP"]] + add[AT["RECOVER_MP"]]
                                + short(add[AT["RECOVER_MP"]] * rate[AT["PSV_RECOVER_MP"]] / 100.0))

        for k in STAT_KEYS:
            add[AT[k]] += from_value[k]
        cur = {}
        for k in STAT_KEYS:
            v = b.stats[k] + add[AT[k]]
            if self.fix and stat_rates[k]:
                v += int((b.stats[k] + add[AT[k]]) * stat_rates[k] / 100.0)
            cur[k] = v
        self.cur = cur
        STR, DEX, INT, CON, SEN = cur["STR"], cur["DEX"], cur["INT"], cur["CON"], cur["SENSE"]

        def psv(ab, base):
            return add[ab] + short(base * rate[ab] / 100.0)

        # Cal_MaxHP / Cal_MaxMP
        A, M1 = HP_TAB.get(b.job, (12, 8))
        hp = short((L + A) * M1 + STR * 2 + add[AT["MAX_HP"]])
        self.max_hp = short(hp + psv(AT["PSV_MAX_HP"], hp))
        A, fM1 = MP_TAB.get(b.job, (4, 3.0))
        mp = short(short((L + A) * fM1 + INT * 4) + add[AT["MAX_MP"]])
        self.max_mp = short(mp + psv(AT["PSV_MAX_MP"], mp))

        # Cal_ATTACK
        w = b.equip["weapon"]
        wid = w.id
        wtype = gd.weapon_type(wid) if wid else 0
        wap = gd.weapon_atk(wid) if wid else 0
        gatk = gd.grade(w.grade, 0) if wid else 0
        shot = SHOT_BY_WEAPON.get(wtype)
        self.wtype, self.shot = wtype, shot
        # CObjAVT::Get_AttackRange: WEAPON_ATTACK_RANGE + scale(1.0)*120, or 70 + 120 bare
        self.attack_range = (gd.weapon_range(wid) if wid else 70) + 120
        if shot is not None:
            q = gd.item_quality(12, b.ammo) if b.ammo else 0
            if not b.ammo:
                self.notes.append("ranged weapon without ammo: the server skips every "
                                  "normal swing (Dec_ShotITEM fails)")
            if shot == 0:
                ap = int((DEX * 0.62 + STR * 0.2 + L * 0.2 + q)
                         + ((wap + gatk) + q * 0.5 + 8) * (DEX * 0.04 + SEN * 0.03 + 29) / 30.0)
            elif shot == 1:
                ap = int((DEX * 0.4 + CON * 0.5 + L * 0.2 + q)
                         + ((wap + gatk) + q * 0.6 + 8) * (CON * 0.03 + SEN * 0.05 + 29) / 30)
            else:
                ap = int((STR * 0.52 + CON * 0.5 + L * 0.2 + q)
                         + ((wap + gatk) + q + 12) * (CON * 0.04 + SEN * 0.05 + 29) / 30)
        else:
            fam = wtype // 10
            if fam in (21, 22):
                ap = int((STR * 0.75 + L * 0.2) + (wap + gatk) * (STR * 0.05 + 29) / 30.0)
            elif fam == 24:
                if wtype == 241:
                    ap = int((STR * 0.4 + INT * 0.4 + L * 0.2)
                             + (wap + gatk) * (INT * 0.05 + 29) / 30.0)
                else:
                    ap = int((INT * 0.6 + L * 0.2) + (wap + gatk) * (SEN * 0.1 + 26) / 27.0)
            elif fam == 25:
                if wtype == 252:
                    ap = int((STR * 0.63 + DEX * 0.45 + L * 0.2)
                             + (wap + gatk) * (DEX * 0.05 + 25) / 26.0)
                else:
                    ap = int((STR * 0.42 + DEX * 0.55 + L * 0.2)
                             + (wap + gatk) * (DEX * 0.05 + 20) / 21.0)
            elif fam == 0:
                ap = int(STR * 0.5 + DEX * 0.3 + L * 0.2)
            else:
                ap = 0
                self.notes.append(f"weapon type {wtype} has no Cal_ATTACK branch: ATK 0")
        ap += add[AT["ATK"]]
        idx = AT["PSV_ATK_POW_NO_WEAPON"] if wid == 0 else PSV_ATK_BY_WTYPE.get(wtype)
        self.attack_power = ap + (psv(idx, ap) if idx else 0)

        # Cal_HIT
        if wid:
            hit = int((CON + 10) * 0.8) + int(gd.item_quality(8, wid) * WEAPON_HIT_QUALITY
                                              + gd.grade(w.grade, 1) + self._durability(w) * 0.8)
        else:
            hit = int((CON + 10) * 0.5 + 15)
        hit += add[AT["HIT"]]
        self.hit_rate = hit + psv(AT["PSV_HIT"], hit)

        # Cal_DEFENCE (on foot)
        tdef = tgdef = tgrade = tres = tgres = 0
        for it in b.equip.values():
            if not it.id:
                continue
            d = gd.item_def(it.itype, it.id)
            if d:
                tdef += d
                tgdef += gd.grade(it.grade, 2)
                tgrade += it.grade
            r = gd.item_res(it.itype, it.id)
            if r:
                tres += r
                tgres += gd.grade(it.grade, 3)
        df = short(int(tdef + tgdef + (STR + 5) * 0.35 + (L + 15) * 0.7) + add[AT["DEF"]])
        df = short(df + psv(AT["PSV_DEF_POW"], df))
        sub = b.equip["subwpn"]
        if sub.id and gd.item_type(9, sub.id) == 261:            # shield
            df = short(df + psv(AT["PSV_SHIELD_DEF"], df))
        self.defence = df
        self.def_grade = tgrade

        # Cal_RESIST -> Rose::Tuning::resistance
        res = short(short(int(tres + tgres + (INT + 5) * 0.6 + (L + 15) * 0.8)) + add[AT["RES"]])
        self.resist = short(res + psv(AT["PSV_RES"], res))

        # Cal_AvoidRATE (after DEF: uses m_iDefGrade)
        dura = sum(self._durability(b.equip[s]) for s in DURABILITY_SLOTS if b.equip[s].id)
        av = short(short((DEX * 1.9 + L * 0.3 + 10) * 0.4) + short(dura * 0.3) + tgrade)
        av = short(av + add[AT["AVOID"]])
        self.avoid = short(av + psv(AT["PSV_AVOID"], av))

        # Cal_CRITICAL
        cr = int(SEN + (CON + 20) * 0.2) + add[AT["CRITICAL"]]
        self.critical = cr + psv(AT["PSV_CRITICAL"], cr)

        # update_speed (on foot): 1500.f / (WEAPON_ATTACK_SPEED + 5) + AT_ATK_SPD
        fspeed = 1500.0 / (gd.weapon_speed(wid) + 5) + add[AT["ATK_SPD"]]
        sidx = PSV_SPD_BY_WTYPE.get(wtype)
        pspd = (add[sidx] + short(fspeed * rate[sidx] / 100.0)) if sidx else 0
        self.attack_speed = short(fspeed + pspd)

        # m_fRateUseMP = (100 - GetCur_SaveMP()) / 100.f
        save_mp = (add[AT["PSV_SAVE_MP"]] + add[AT["SAVE_MP"]]
                   + short(add[AT["SAVE_MP"]] * rate[AT["PSV_SAVE_MP"]] / 100.0))
        self.save_mp = save_mp
        self.rate_use_mp = (100 - save_mp) / 100.0

        self.magic = bool(wid and gd.weapon_is_magic(wid))
        self.weapon_motion_type = gd.weapon_motion_type(wid)
        self._check_requirements()

    def _check_requirements(self):
        gd, b = self.gd, self.b
        for slot, it in b.equip.items():
            if not it.id:
                continue
            rl = gd.item_req_level(it.itype, it.id)
            if rl > b.level:
                self.notes.append(f"{slot}: {gd.name('LIST_' + _table(it.itype), it.id)} "
                                  f"needs level {rl}")
        spent = b.points_spent()
        have = total_bonus_points(b.level)
        if spent > have:
            self.notes.append(f"stats cost {spent} bonus points; level {b.level} grants {have}")

    # Get_BaseAbilityValue (cobjavt.cpp:425): what a buff's percentage is taken off
    def base_ability(self, at):
        return {AT["ATK"]: self.attack_power, AT["HIT"]: self.hit_rate,
                AT["DEF"]: self.defence, AT["RES"]: self.resist, AT["AVOID"]: self.avoid,
                AT["CRITICAL"]: self.critical, AT["ATK_SPD"]: self.attack_speed,
                AT["MAX_HP"]: self.max_hp, AT["MAX_MP"]: self.max_mp,
                AT["INT"]: self.cur["INT"], AT["STR"]: self.cur["STR"],
                AT["DEX"]: self.cur["DEX"], AT["CON"]: self.cur["CON"],
                AT["SENSE"]: self.cur["SENSE"]}.get(at, 0)


def _table(itype):
    from .data import ITEM_TABLES
    return ITEM_TABLES[itype][5:]
