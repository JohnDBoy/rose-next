"""src/common/calculation.cpp, server build, ported line for line.

Only the player-vs-monster branches are ported (`IsUSER() && IsUSER()` is never
true in a PVE fight, in either direction). The attacker and defender are any
objects exposing the getters calculation.cpp calls:

    level, total_atk, total_hit, get_def, get_res, get_avoid, get_crit,
    get_int, get_sense, magic, dummy_power

`get_*` are the floored totals (`CObjCHAR::Get_DEF` etc., floor 10) and
`total_*` the unfloored `total_attack_power` / `total_hit_rate`.

C++ evaluates these in 32-bit float; Python uses doubles, so a result sitting
exactly on an integer boundary can truncate one point differently. That is the
only intended deviation.
"""
MAX_DAMAGE = 9999           # GameStaticConfig::MAX_DAMAGE
LEVEL_GATE = 1.05           # kLevelGateScale in Get_SuccessRATE


def R(rng, n):
    """RANDOM(V) = rand() % V."""
    return rng.randrange(n)


def success_rate(rng, a, d):
    """CCal::Get_SuccessRATE (calculation.cpp:298)."""
    r1 = 1 + R(rng, 50)
    r2 = 1 + R(rng, 60)
    s = int((a.level + 10) - d.level * LEVEL_GATE + r1)
    if s <= 0:
        return 0
    return int(s * (a.total_hit * 1.1 - d.get_avoid * 0.93 + r2 + 5 + a.level * 0.2) / 80.0)


def cri_success_rate(rng, a):
    """CCal::Get_CriSuccessRATE: a critical lands when this is < 20."""
    return int(((1 + R(rng, 100)) * 3 + a.level + 30) * 16 / (a.get_crit + 70))


def _dummy(a, dmg):
    # FLAG_ING_DUMMY_DAMAGE: += iDamage * SKILL_POWER(state skill) / 100.f
    if a.dummy_power:
        dmg += int(dmg * a.dummy_power / 100.0)
    return dmg


def basic_damage(rng, a, d, hit_cnt, suc):
    """CCal::Get_BasicDAMAGE, monster branch. Returns (damage, critical)."""
    atk = a.total_atk
    if cri_success_rate(rng, a) < 20:
        dmg = int(atk * (suc * 0.05 + 29) * (atk - d.get_def + 230)
                  / ((d.get_def + d.get_avoid * 0.3 + 5) * 100))
        dmg = _dummy(a, dmg) * hit_cnt
        dmg = 10 if dmg < 10 else min(dmg, MAX_DAMAGE)
        return dmg, True
    dmg = int(atk * (suc * 0.03 + 26) * (atk - d.get_def + 250)
              / ((d.get_def + d.get_avoid * 0.4 + 5) * 145))
    dmg = _dummy(a, dmg) * hit_cnt
    dmg = 5 if dmg < 5 else min(dmg, MAX_DAMAGE)
    return dmg, False


def magic_damage(rng, a, d, hit_cnt, suc):
    """CCal::Get_MagicDAMAGE, monster branch. Returns (damage, critical)."""
    atk = a.total_atk
    if cri_success_rate(rng, a) < 20:
        dmg = int(atk * (suc * 0.05 + 33) * (atk - d.get_def * 0.8 + 310)
                  / ((d.get_res + d.get_avoid * 0.3 + 5) * 200))
        dmg = _dummy(a, dmg) * hit_cnt
        dmg = 10 if dmg < 10 else min(dmg, MAX_DAMAGE)
        return dmg, True
    dmg = int(atk * (suc * 0.03 + 30) * (atk - d.get_def * 0.8 + 280)
              / ((d.get_res + d.get_avoid * 0.3 + 5) * 280))
    dmg = _dummy(a, dmg) * hit_cnt
    dmg = 5 if dmg < 5 else min(dmg, MAX_DAMAGE)
    return dmg, False


def normal_attack(rng, a, d, hit_cnt):
    """CCal::Get_DAMAGE. Returns (damage, critical); damage 0 = miss.

    Below iSuc 20 the swing survives only on `1+RANDOM(100) + (alv-dlv)*0.6 >= 94`.
    """
    suc = success_rate(rng, a, d)
    if suc < 20:
        if int(1 + R(rng, 100) + (a.level - d.level) * 0.6) < 94:
            return 0, False
    if a.magic:
        return magic_damage(rng, a, d, hit_cnt, suc)
    return basic_damage(rng, a, d, hit_cnt, suc)


def skill_damage(rng, a, d, sk, hit_cnt):
    """CCal::Get_SkillDAMAGE (calculation.cpp:574), monster branches. 0 = miss."""
    power = sk.power
    t = sk.damage_type
    if t == 1:                                   # weapon skill
        suc = int(((a.level + 20) - d.level + (1 + R(rng, 60)))
                  * (a.total_hit - d.get_avoid * 0.6 + (1 + R(rng, 70)) + 10) / 110.0)
        if suc < 20:
            if suc < 10:
                return 0
            dmg = int(((power * 0.4) * (a.total_atk + 50)
                       * ((1 + R(rng, 30)) + a.get_sense * 1.2 + 340))
                      / (d.get_def + d.get_res + 20) / (250 + d.level - a.level) + 20)
        else:
            dmg = int(((power + a.total_atk * 0.2) * (a.total_atk + 60)
                       * ((1 + R(rng, 30)) + a.get_sense * 0.7 + 370))
                      * 0.01 * (120 - d.level + a.level)
                      / (d.get_def + d.get_res * 0.8 + d.get_avoid * 0.4 + 20) / 270 + 20)
    elif t == 2:                                 # magic skill
        suc = int(((a.level + 30) - d.level + (1 + R(rng, 50)))
                  * (a.total_hit - d.get_avoid * 0.56 + (1 + R(rng, 70)) + 10) / 110.0)
        if suc < 20:
            if suc < 8:
                return 0
            dmg = int((power * (a.total_atk * 0.8 + a.get_int + 80)
                       * ((1 + R(rng, 30)) + a.get_sense * 1.3 + 280) * 0.2)
                      / (d.get_def * 0.3 + d.get_res + 30) / (250 + d.level - a.level) + 20)
        else:
            dmg = int((power * (a.total_atk * 0.8 + a.get_int * 1.2 + 100)
                       * ((1 + R(rng, 30)) + a.get_sense * 0.7 + 350) * 0.01)
                      * (150 - d.level + a.level)
                      / (d.get_def * 0.3 + d.get_res + d.get_avoid * 0.3 + 60) / 350.0 + 20)
    elif t == 3:                                 # bare-hand skill
        suc = int(((a.level + 10) - d.level + (1 + R(rng, 80)))
                  * (a.total_hit - d.get_avoid * 0.5 + (1 + R(rng, 50)) + 50) / 90.0)
        if suc < 20:
            if suc < 6:
                return 0
            dmg = int((power * (power + a.get_int + 80)
                       * ((1 + R(rng, 30)) + a.get_sense * 2 + 290) * 0.2)
                      / (d.get_def * 0.2 + d.get_res + 30) / (250 + d.level - a.level) + 20)
        else:
            dmg = int(((35 + power) * (power + a.get_int + 140)
                       * ((1 + R(rng, 30)) + a.get_sense + 380) * 0.01)
                      * (150 - d.level + a.level)
                      / (d.get_def * 0.35 + d.get_res * 1.2 + d.get_avoid * 0.4 + 10) / 730
                      + 20)
    else:                                        # default: normal-attack-like
        # integer division by 90 in the C++ (no .f): the product is float, so /90 is float
        suc = int(((a.level + 8) - d.level + (1 + R(rng, 80)))
                  * (a.total_hit - d.get_avoid * 0.6 + (1 + R(rng, 50)) + 50) / 90)
        if suc < 20:
            if suc < 10:
                return 0
            dmg = int(((power + 40) * (a.total_atk + 40)
                       * ((1 + R(rng, 30)) + a.get_crit * 0.2 + 40)) * 0.4
                      / (d.get_def + d.get_res * 0.3 + d.get_avoid * 0.4 + 10) / 80 + 5)
        else:
            dmg = int(((power + a.get_crit * 0.15 + 40) * a.total_atk
                       * ((1 + R(rng, 30)) + a.get_crit * 0.32 + 35))
                      * 0.01 * (120 - d.level + a.level)
                      / (d.get_def + d.get_res * 0.3 + d.get_avoid * 0.4 + 10) / 100.0 + 20)

    dmg = _dummy(a, dmg)
    if dmg < 5:
        dmg = 5
    dmg *= hit_cnt
    return min(dmg, MAX_DAMAGE)


def skill_adjust_value(base_value, rate, flat, speller_int):
    """CCal::Get_SkillAdjustVALUE: (short)(base*RATE/100.f + FLAT*(INT+300)/315.f).

    `base_value` is Get_BaseAbilityValue of the TARGET: the pre-buff stat for a
    player (CObjAVT override), the current, already-debuffed one for a monster.
    """
    v = int(base_value * rate / 100.0 + flat * (speller_int + 300) / 315.0)
    return max(-32768, min(32767, v))


def harmful_state_lands(rng, ratio, speller_level, speller_int, target):
    """Skill_ApplyIngSTATUS, harmful branch (cobjchar.cpp:1471): the state FAILS when
    ratio*(LV*2+INT+20) / (RES*0.6f+5+AVOID) <= 1+RANDOM(100)."""
    if not ratio:
        return True
    lhs = ratio * (speller_level * 2 + speller_int + 20) / (target.get_res * 0.6 + 5
                                                             + target.get_avoid)
    return not (lhs <= 1 + R(rng, 100))


def harmful_state_chance(ratio, speller_level, speller_int, target):
    """Closed form of harmful_state_lands, for reports."""
    if not ratio:
        return 1.0
    lhs = ratio * (speller_level * 2 + speller_int + 20) / (target.get_res * 0.6 + 5
                                                             + target.get_avoid)
    return sum(1 for r in range(1, 101) if lhs > r) / 100.0
