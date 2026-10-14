#include "stdafx.h"
#include <chrono>
#include "gs_user.h"
#include "gs_threadzone.h"
#include "mounted_item_bonuses.h"
#include "rose/common/mounted_stats.h"
#include "rose/network/packets/tuning_preview_generated.h"

using namespace Rose;

Tuning::MountedStatsInput
classUSER::mounted_stats_input() {
    Tuning::MountedStatsInput in;
    tagITEM parts[MAX_RIDING_PART];
    std::copy(m_Inventory.m_ItemRIDE, m_Inventory.m_ItemRIDE + MAX_RIDING_PART, parts);
    auto& body = parts[RIDE_PART_BODY];
    if (body.GetTYPE() != ITEM_TYPE_RIDE_PART)
        return in;
    const int body_type = PAT_ITEM_TYPE(body.GetItemNO());
    in.vehicle_type = body_type == TUNING_PART_BODY_CART ? 1
        : body_type == TUNING_PART_BODY_CASTLEGEAR ? 2 : 0;
    if (!in.vehicle_type)
        return in;

    auto& engine = parts[RIDE_PART_ENGINE];
    auto& legs = parts[RIDE_PART_LEG];
    auto& weapon = parts[RIDE_PART_ARMS];
    in.engine_present = engine.GetTYPE() == ITEM_TYPE_RIDE_PART;
    in.complete = in.engine_present && legs.GetTYPE() == ITEM_TYPE_RIDE_PART;
    in.weapon_present = weapon.GetTYPE() == ITEM_TYPE_RIDE_PART
        && PAT_ITEM_ATK_RANGE(weapon.GetItemNO()) > 0;
    in.fuel_cost = in.engine_present ? PAT_ITEM_USE_FUEL_RATE(engine.GetItemNO()) : 0;
    const bool driving = GetCur_RIDE_MODE() == RIDE_MODE_DRIVE;
    if (in.engine_present)
        engine.m_nLife = Tuning::fuel_after_mount(engine.GetLife(), in.fuel_cost, driving);
    in.engine_working = engine.GetLife() > 0;
    in.legs_working = legs.GetLife() > 0;
    in.engine_speed = PAT_ITEM_MOV_SPD(engine.GetItemNO());
    in.legs_speed = PAT_ITEM_MOV_SPD(legs.GetItemNO());
    in.weapon_attack = PAT_ITEM_ATK_POW(weapon.GetItemNO());
    // update_speed uses a short temporary before converting the reciprocal.
    in.weapon_speed = static_cast<short>(PAT_ITEM_ATK_SPD(weapon.GetItemNO()) + 5) - 5;

    // Match Cal_BattleAbility: preserve the learned passive range, clear the
    // equipment ranges, then accumulate equipment in mounted mode. Never reuse
    // on-foot STR/CON/INT totals, which include bonuses that mounting removes.
    int bonuses[AT_MAX];
    std::copy(m_iAddValue, m_iAddValue + AT_MAX, bonuses);
    std::fill(bonuses, bonuses + AT_MONEY, 0);
    std::fill(bonuses + AT_AFTER_PASSIVE_SKILL, bonuses + AT_PSV_RES, 0);
    std::fill(bonuses + AT_AFTER_PASSIVE_SKILL_2ND, bonuses + AT_MAX, 0);
    accumulate_equipment_bonuses(m_Inventory.m_ItemEQUIP, parts, GetCur_UNION(), bonuses, true);
    in.level = GetCur_LEVEL();
    in.str = GetDef_STR() + bonuses[AT_STR] + m_PassiveAbilityFromRate[AT_STR - AT_STR];
    in.intelligence = GetDef_INT() + bonuses[AT_INT] + m_PassiveAbilityFromRate[AT_INT - AT_STR];
    in.con = GetDef_CON() + bonuses[AT_CON] + m_PassiveAbilityFromRate[AT_CON - AT_STR];
    in.bonus_def = bonuses[AT_DEF];
    in.bonus_res = bonuses[AT_RES];
    in.bonus_attack = bonuses[AT_ATK];
    in.bonus_speed = bonuses[AT_SPEED];
    in.bonus_attack_speed = bonuses[AT_ATK_SPD];
    in.passive_def = bonuses[AT_PSV_DEF_POW];
    in.passive_res = bonuses[AT_PSV_RES];
    // Both passive ranges survive Cal_BattleAbility (the second one only since 2026-10-14).
    in.passive_def_rate = m_nPassiveRate[AT_PSV_DEF_POW];
    in.passive_res_rate = m_nPassiveRate[AT_PSV_RES];
    for (int i = EQUIP_IDX_NULL + 1; i < MAX_EQUIP_IDX; ++i) {
        tagITEM item = m_Inventory.m_ItemEQUIP[i];
        if (!item.GetTYPE() || !item.GetLife())
            continue;
        const int def = ITEM_DEFENCE(item.GetTYPE(), item.GetItemNO());
        if (def) {
            in.armour_def += def;
            in.grade_def += ITEMGRADE_DEF(item.GetGrade());
        }
        const int res = ITEM_RESISTENCE(item.GetTYPE(), item.GetItemNO());
        if (res) {
            in.armour_res += res;
            in.grade_res += ITEMGRADE_RES(item.GetGrade());
        }
    }
    for (auto& part : parts) {
        if (part.GetTYPE() && part.GetLife())
            in.grade_def += ITEMGRADE_DEF(part.GetGrade());
    }
    tagITEM shield = m_Inventory.m_ItemEQUIP[EQUIP_IDX_WEAPON_L];
    if (shield.GetHEADER() && shield.GetLife() && ITEM_TYPE(shield.GetTYPE(), shield.GetItemNO()) == 261) {
        in.shield_def = bonuses[AT_PSV_SHIELD_DEF];
        in.shield_def_rate = m_nPassiveRate[AT_PSV_SHIELD_DEF];
    }
    in.base_overweight = Get_WeightRATE() >= WEIGHT_RATE_WALK;
    in.overweight = in.base_overweight;
    if (!driving) {
        // The client reports a new weight bracket after mounting recalculates
        // carrying capacity. Predict that final consumer cap without sending
        // SET_WEIGHT_RATE or changing the server's current bracket.
        tagITEM bag = m_Inventory.m_ItemEQUIP[EQUIP_IDX_KNAPSACK];
        const bool backpack = bag.GetHEADER() && bag.GetLife()
            && ITEM_TYPE(bag.GetTYPE(), bag.GetItemNO()) == 162;
        const int capacity = Tuning::weight_capacity(in.level, in.str, bonuses[AT_WEIGHT],
            backpack ? bonuses[AT_PSV_WEIGHT] : 0, backpack ? m_nPassiveRate[AT_PSV_WEIGHT] : 0);
        if (capacity > 0) {
            int weight = 0;
            for (int i = 0; i < INVENTORY_TOTAL_SIZE; ++i) {
                tagITEM item = m_Inventory.m_ItemLIST[i];
                if (!item.IsEmpty()) {
                    const int unit = ITEM_WEIGHT(item.GetTYPE(), item.GetItemNO());
                    weight += item.IsEnableDupCNT() ? unit * item.GetQuantity() : unit;
                }
            }
            in.overweight = weight * 100 / capacity >= WEIGHT_RATE_WALK;
        }
    }
    in.server_attack = server_config().game.base_attack_power;
    in.server_attack_speed = server_config().game.base_attack_speed;

    // StatusEffects owns only values. Filtering this copy cannot expire a real
    // buff, deduct fuel, send a packet, or change any command on the character.
    StatusEffects effects = m_IngSTATUS;
    if (!driving) {
        effects.ClearAllGOOD();
        effects.goddess_effect.update(in.level);
        // classUSER::UpdateAbility calls update_speed twice (the second call
        // is in Send_gsv_SPEED_CHANGED). Thus the final fairy adjustment uses
        // the new mounted base speed. DEF's fairy adjustment remains cached.
        const uint16_t mounted_speed = static_cast<uint16_t>(std::floor(Tuning::move_speed(
            in.engine_working && in.legs_working, in.legs_speed, in.engine_speed,
            in.bonus_speed, in.base_overweight)));
        effects.m_nAruaRunSPD = effects.IsSubSET(FLAG_SUB_ARUA_FAIRY)
            ? static_cast<short>(mounted_speed * 0.2f) : 0;
        effects.m_nAruaATK = effects.IsSubSET(FLAG_SUB_ARUA_FAIRY)
            ? static_cast<short>(Tuning::attack_power(in.level, in.con,
                in.weapon_attack, in.bonus_attack) * 0.2f) : 0;
    }
    in.adjust_def = effects.Adj_DPOWER();
    in.adjust_res = effects.Adj_RES();
    in.adjust_speed = effects.Adj_RUN_SPEED();
    in.adjust_attack = effects.Adj_APOWER();
    in.adjust_attack_speed = effects.Adj_ATK_SPEED();
    return in;
}

bool
classUSER::recv_tuning_preview(uint32_t sequence) {
    m_TuningRequests.submit(sequence);
    return true;
}

bool
classUSER::process_tuning_preview() {
    const ULONGLONG now = static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
    uint32_t sequence;
    if (!m_TuningRequests.take(now, sequence))
        return true;
    const auto input = mounted_stats_input();
    auto result = Tuning::calculate(input);
    // While already driving, wear/status updates may leave cached base stats
    // until their normal refresh. Report exactly what combat currently uses.
    if (GetCur_RIDE_MODE() == RIDE_MODE_DRIVE && input.complete) {
        result.defence = Get_DEF();
        result.resistance = Get_RES();
        result.speed = total_move_speed();
        result.attack = total_attack_power();
        result.attack_speed = total_attack_speed();
    }
    flatbuffers::FlatBufferBuilder builder;
    const auto response = Network::Packets::CreateTuningPreviewResponse(builder, sequence,
        result.vehicle_type, result.valid_fields, result.defence, result.resistance,
        result.fuel, result.speed, result.attack, result.attack_speed);
    return send_packet_from_offset(builder, response, Network::Packets::PacketType::TuningPreviewResponse);
}
