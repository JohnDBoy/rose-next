#include "stdafx.h"

#include "BoneEffectBudget.h"
#include "CObjCHAR.h"
#include "cclientstorage.h"
#include "OBJECT.h"

namespace {
// A ceiling for pathological scenes, not a crowd limit. Measured 2026-10-22 on
// the mid-range target (RTX 5060): 30 Frozen Thorns at full tier = 1,982 live
// particles in 2 batched draws, 184 FPS, scnupd 0.8 ms, present 0.3 ms. The
// old 480-particle / 360 emit/s / 3-copies-per-aura limits predate batching
// and switched off a third of that pack for no measurable saving.
const int kCapacityBudget = 8000;
const DWORD kDemoteDelayMs = 250;
const DWORD kPromoteDelayMs = 1000;

int TierRank(EParticleEffectTier tier)
{
    return static_cast<int>(tier);
}
} // namespace

BoneEffectBudgetStats::BoneEffectBudgetStats() {
    groups = 0;
    effects = 0;
    emitters = 0;
    activeParticles = 0;
    runtimeCapacity = 0;
    configuredEmitRate = 0.0f;
    topNpc = 0;
    for (int i = 0; i < PARTICLE_EFFECT_TIER_COUNT; ++i)
        tierCounts[i] = 0;
}

CBoneEffectBudget&
CBoneEffectBudget::Instance() {
    static CBoneEffectBudget s_Instance;
    return s_Instance;
}

CBoneEffectBudget::CBoneEffectBudget() {}

void
CBoneEffectBudget::Register(CObjCHAR* pOwner, CEffect* pEffect, t_HASHKEY effectHash, int iBoneIndex) {
    if (!pOwner || !pEffect || pEffect->GetParticleEmitterCount() <= 0)
        return;

    for (std::vector<Record>::iterator it = m_Records.begin(); it != m_Records.end(); ++it) {
        if (it->effect == pEffect)
            return;
    }

    Record record;
    record.owner = pOwner;
    record.effect = pEffect;
    record.effectHash = effectHash;
    record.npcId = pOwner->Get_CharNO();
    record.boneIndex = iBoneIndex;
    record.configuredCapacity = pEffect->GetConfiguredParticleCapacity();
    record.configuredEmitRate = pEffect->GetConfiguredParticleEmitRate();
    record.emitterCount = pEffect->GetParticleEmitterCount();
    record.appliedTier = PARTICLE_EFFECT_TIER_FULL;
    record.desiredTier = PARTICLE_EFFECT_TIER_FULL;
    record.tierRequestTime = 0;
    record.distanceSq = 0.0f;
    record.visible = true;
    record.target = false;
    record.player = false;

    m_Records.push_back(record);
}

void
CBoneEffectBudget::Unregister(CEffect* pEffect) {
    if (!pEffect)
        return;

    for (std::vector<Record>::iterator it = m_Records.begin(); it != m_Records.end();) {
        if (it->effect == pEffect)
            it = m_Records.erase(it);
        else
            ++it;
    }
}

int
CBoneEffectBudget::CapacityForTier(const Record& record, EParticleEffectTier tier) const {
    switch (tier) {
        case PARTICLE_EFFECT_TIER_REDUCED:
            return max(8 * record.emitterCount, (int)(record.configuredCapacity * 0.40f));
        case PARTICLE_EFFECT_TIER_MINIMAL:
            return min(6 * record.emitterCount,
                max(2 * record.emitterCount, (int)(record.configuredCapacity * 0.12f)));
        case PARTICLE_EFFECT_TIER_OFF:
            return 0;
        case PARTICLE_EFFECT_TIER_FULL:
        default:
            return record.configuredCapacity;
    }
}

EParticleEffectTier
CBoneEffectBudget::PickTier(const Record& record, int& usedCapacity) {
    if (!record.visible)
        return PARTICLE_EFFECT_TIER_OFF;

    // [VIDEO] BONE_FX_BUDGET=0 lifts even the ceiling (testing only).
    if (!g_ClientStorage.GetBoneFxBudget())
        return PARTICLE_EFFECT_TIER_FULL;

    // Records arrive nearest-first, so past the ceiling the farthest degrade.
    const EParticleEffectTier tiers[] = {
        PARTICLE_EFFECT_TIER_FULL, PARTICLE_EFFECT_TIER_REDUCED, PARTICLE_EFFECT_TIER_MINIMAL};
    for (int i = 0; i < _countof(tiers); ++i) {
        const int capacity = CapacityForTier(record, tiers[i]);
        if (usedCapacity + capacity <= kCapacityBudget) {
            usedCapacity += capacity;
            return tiers[i];
        }
    }

    return PARTICLE_EFFECT_TIER_OFF;
}

void
CBoneEffectBudget::ApplyTierWithHysteresis(Record& record, EParticleEffectTier desiredTier, DWORD now) {
    if (!record.effect)
        return;

    if (record.appliedTier == desiredTier) {
        record.desiredTier = desiredTier;
        record.tierRequestTime = 0;
        return;
    }

    if (!record.visible && desiredTier == PARTICLE_EFFECT_TIER_OFF) {
        record.effect->SetParticleTier(desiredTier);
        record.appliedTier = desiredTier;
        record.desiredTier = desiredTier;
        record.tierRequestTime = 0;
        return;
    }

    if (record.desiredTier != desiredTier) {
        record.desiredTier = desiredTier;
        record.tierRequestTime = now;
        return;
    }

    const bool demoting = TierRank(desiredTier) > TierRank(record.appliedTier);
    const DWORD delay = demoting ? kDemoteDelayMs : kPromoteDelayMs;
    if (now - record.tierRequestTime < delay)
        return;

    record.effect->SetParticleTier(desiredTier);
    record.appliedTier = desiredTier;
    record.tierRequestTime = 0;
}

void
CBoneEffectBudget::Update() {
    m_Stats = BoneEffectBudgetStats();

    if (m_Records.empty() || !g_pAVATAR)
        return;

    const DWORD now = g_GameDATA.GetGameTime();
    const D3DXVECTOR3 avatarPos = g_pAVATAR->Get_CurPOS();
    const int targetClientIndex =
        g_pObjMGR ? g_pObjMGR->Get_ClientObjectIndex(g_pAVATAR->Get_TargetIDX()) : 0;

    std::vector<int> order;
    order.reserve(m_Records.size());
    std::map<int, int> npcCost;

    for (int i = 0; i < (int)m_Records.size(); ++i) {
        Record& record = m_Records[i];
        if (!record.owner || !record.effect)
            continue;

        const D3DXVECTOR3 delta = record.owner->Get_CurPOS() - avatarPos;
        record.distanceSq = D3DXVec3LengthSq(&delta);
        record.visible = record.owner->IsVisible() && record.owner->IsInViewFrustum();
        record.target = (record.owner->Get_INDEX() == targetClientIndex);
        record.player = record.owner->IsA(OBJ_USER);
        record.configuredCapacity = record.effect->GetConfiguredParticleCapacity();
        record.configuredEmitRate = record.effect->GetConfiguredParticleEmitRate();
        record.emitterCount = record.effect->GetParticleEmitterCount();

        m_Stats.groups++;
        m_Stats.effects++;
        m_Stats.emitters += record.emitterCount;
        m_Stats.activeParticles += record.effect->GetActiveParticleCount();
        m_Stats.runtimeCapacity += record.effect->GetRuntimeParticleCapacity();
        m_Stats.configuredEmitRate += record.configuredEmitRate;
        if (record.appliedTier >= 0 && record.appliedTier < PARTICLE_EFFECT_TIER_COUNT)
            m_Stats.tierCounts[record.appliedTier]++;

        npcCost[record.npcId] += record.configuredCapacity;
        order.push_back(i);
    }

    for (std::map<int, int>::iterator it = npcCost.begin(); it != npcCost.end(); ++it) {
        if (!m_Stats.topNpc || it->second > npcCost[m_Stats.topNpc])
            m_Stats.topNpc = it->first;
    }

    std::sort(order.begin(), order.end(), [this](int lhs, int rhs) {
        const Record& a = m_Records[lhs];
        const Record& b = m_Records[rhs];
        if (a.player != b.player)
            return a.player;
        if (a.target != b.target)
            return a.target;
        if (a.visible != b.visible)
            return a.visible;
        return a.distanceSq < b.distanceSq;
    });

    int usedCapacity = 0;

    for (std::vector<int>::iterator it = order.begin(); it != order.end(); ++it) {
        Record& record = m_Records[*it];
        const EParticleEffectTier desiredTier = PickTier(record, usedCapacity);
        ApplyTierWithHysteresis(record, desiredTier, now);
    }
}
