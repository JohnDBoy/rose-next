#include "stdafx.h"

#include "skillaim.h"

#include "cobjchar.h"
#include "groundtelegraph.h"
#include "io_terrain.h"
#include "object.h"
#include "common/io_skill.h"
#include "gamecommon/skill.h"
#include "interface/it_mgr.h"
#include "interface/slotcontainer/cskillslot.h"
#include "interface/typeresource.h"
#include "system/cgame.h"
#include "zz_interface.h"

#include <math.h>

namespace {
const float RANGE_MARGIN_CM = 50.f; // inside the range: the server's copy of us may lag a step
const float MIN_AIM_CM = 100.f; // a strip or cone aimed at our feet points where we face
const float MAX_RAY_CM = 60000.f; // how far along the mouse ray the ground is looked for
const float PICK_MARGIN_CM = 2000.f; // decks looked for beyond the skill's reach (it is clamped)
const float PICK_BELOW_CM = 10000.f; // ...and this far below the avatar
const float FLAT_CM = 150.f; // an aim this far over the terrain is on a deck (groundtelegraph.cpp)

// The nearest walkable map surface along the mouse ray, within reach of the avatar: a
// bridge deck, a platform, a wall walk. The terrain march goes straight through them to
// the ground below, but the server puts an area on the floor nearest the caster's height
// (doc/pathfinding-and-z-plan.md, Phase 3), so the aim has to land on the deck too.
// Walkable = what GetHeightTop stands characters on (CGroundTelegraphs::IsWalkableNode). A
// "not moveable" object (flag 12) counts too while the avatar stands on an object itself and the
// hit is near its height: the Shady Jungle rope bridges are flag 12, and the avatar walks them on
// its own foot collision, but tree crowns and cave ceilings are flag 12 as well.
bool
pick_walkable_object(const D3DXVECTOR3& o, const D3DXVECTOR3& d, float fMaxT, float fReach,
    D3DXVECTOR3& out) {
    const D3DXVECTOR3& me = g_pAVATAR->Get_CurPOS();
    bool bNF = false;
    const float fGround = g_pTerrain ? g_pTerrain->GetHeight(me.x, me.y, &bNF) : me.z;
    const bool bOnObject = !bNF && me.z > fGround + FLAT_CM;
    constexpr float NOT_MOVEABLE_REACH_CM = 300.f;
    D3DXVECTOR3 vMin(me.x - fReach, me.y - fReach, me.z - PICK_BELOW_CM);
    D3DXVECTOR3 vMax(me.x + fReach, me.y + fReach, (o.z > me.z ? o.z : me.z) + 500.f);
    const int n = ::collectByMinMaxVec3(vMin, vMax);
    bool bFound = false;
    float fBest = fMaxT;
    for (int i = 0; i < n; ++i) {
        HNODE h = ::getCollectNode(i);
        if (!CGroundTelegraphs::IsWalkableNode(h, bOnObject))
            continue;
        const bool bNotMoveable = CGroundTelegraphs::IsNotMoveableNode(h);
        float x, y, z, dist;
        if (::intersectRay(h, o.x, o.y, o.z, d.x, d.y, d.z, &x, &y, &z, &dist) && dist < fBest
            && (!bNotMoveable || fabsf(z - me.z) <= NOT_MOVEABLE_REACH_CM)) {
            fBest = dist;
            out = D3DXVECTOR3(x, y, z);
            bFound = true;
        }
    }
    return bFound;
}
const int RIGHT_CLICK_DRAG_PX = 5; // a right button that moved more turned the camera
} // namespace

CSkillAim&
CSkillAim::Instance() {
    static CSkillAim s_Instance;
    return s_Instance;
}

bool
CSkillAim::OnSkillPressed(int iSkillSlot) {
    if (!g_pAVATAR)
        return false;
    CSkill* pSkill = g_pAVATAR->GetSkillSlot()->GetSkill(iSkillSlot);
    if (!pSkill)
        return false;
    const short nSkillIDX = pSkill->GetSkillIndex();

    if (CSkillManager::GetSkillTargetType(nSkillIDX) != SKILL_TARGET_GROUND) {
        this->Cancel(); // another kind of skill: it runs as before
        return false;
    }
    if (this->IsAiming() && m_iSlot == iSkillSlot) {
        this->Cancel(); // the same key again puts it away
        return true;
    }
    this->Cancel();

    // Say now, at the key press, what would refuse it at the click.
    if (g_pAVATAR->Get_HP() <= 0 || g_pAVATAR->m_EndurancePack.GetStateValue(ING_DUMB))
        return true;
    if (CSkillManager::CheckConditionForFireSkill(nSkillIDX, 0) == false)
        return true;
    if (CSkillManager::CheckSkillTimer(iSkillSlot) == false) {
        g_itMGR.AppendChatMsg(CStr::Printf("%s", STR_NOTIFY_04), IT_MGR::CHAT_TYPE_SYSTEM);
        return true;
    }

    m_iSlot = iSkillSlot;
    m_nSkillIDX = nSkillIDX;
    m_bHaveAim = false;
    m_bRightDown = false;
    return true;
}

void
CSkillAim::Cancel() {
    if (m_iSlot >= 0)
        CGroundTelegraphs::Instance().ClearPreview();
    m_iSlot = -1;
    m_nSkillIDX = 0;
    m_bHaveAim = false;
    m_bRightDown = false;
}

bool
CSkillAim::StillValid() const {
    if (!g_pAVATAR || g_pAVATAR->Get_HP() <= 0)
        return false;
    CSkill* pSkill = g_pAVATAR->GetSkillSlot()->GetSkill(m_iSlot);
    return pSkill && pSkill->GetSkillIndex() == m_nSkillIDX;
}

bool
CSkillAim::MouseOnGround(D3DXVECTOR3& out) const {
    if (!g_pTerrain)
        return false;
    POINT pt;
    CGame::GetInstance().Get_MousePos(pt);
    D3DXVECTOR3 o, d;
    if (!::getRay(pt.x, pt.y, &o.x, &o.y, &o.z, &d.x, &d.y, &d.z))
        return false;
    D3DXVec3Normalize(&d, &d);

    // Along the ray from the camera until it goes under the ground, steps growing with the
    // distance (1%, at least 25 cm), then halve the last step down to a few cm.
    bool bGround = false;
    D3DXVECTOR3 ground;
    float t = 0.f;
    for (int i = 0; i < 4000 && t < MAX_RAY_CM; ++i) {
        const float step = (t * 0.01f > 25.f) ? t * 0.01f : 25.f;
        t += step;
        D3DXVECTOR3 p = o + d * t;
        bool bNotFound = false;
        const float h = g_pTerrain->GetHeight(p.x, p.y, &bNotFound);
        if (bNotFound || p.z > h)
            continue;
        float lo = t - step, hi = t;
        for (int k = 0; k < 10; ++k) {
            const float mid = (lo + hi) * 0.5f;
            const D3DXVECTOR3 q = o + d * mid;
            bool bNF = false;
            const float hq = g_pTerrain->GetHeight(q.x, q.y, &bNF);
            if (!bNF && q.z <= hq)
                hi = mid;
            else
                lo = mid;
        }
        ground = o + d * hi;
        bool bNF = false;
        const float hz = g_pTerrain->GetHeight(ground.x, ground.y, &bNF);
        if (!bNF)
            ground.z = hz;
        t = hi;
        bGround = true;
        break;
    }

    // a deck or a platform in front of that ground wins
    const float fReach = (float)SKILL_DISTANCE(m_nSkillIDX) + PICK_MARGIN_CM;
    if (g_pAVATAR && pick_walkable_object(o, d, bGround ? t : MAX_RAY_CM, fReach, out))
        return true;
    if (bGround)
        out = ground;
    return bGround;
}

void
CSkillAim::ClampToRange(D3DXVECTOR3& aim) const {
    const D3DXVECTOR3& me = g_pAVATAR->Get_CurPOS();
    float dx = aim.x - me.x, dy = aim.y - me.y;
    float dist = sqrtf(dx * dx + dy * dy);

    if (SKILL_SCOPE_AIMED(m_nSkillIDX) && dist < MIN_AIM_CM) {
        // no direction to speak of: the way we face
        float v[3] = {0.f, -1.f, 0.f};
        ::getModelDirectionVector(g_pAVATAR->GetZMODEL(), v);
        const float len = sqrtf(v[0] * v[0] + v[1] * v[1]);
        if (len > 0.001f) {
            dx = v[0] / len * MIN_AIM_CM;
            dy = v[1] / len * MIN_AIM_CM;
            dist = MIN_AIM_CM;
            aim.x = me.x + dx;
            aim.y = me.y + dy;
        }
    }

    float range = (float)SKILL_DISTANCE(m_nSkillIDX) - RANGE_MARGIN_CM;
    if (range < 0.f)
        range = 0.f;
    if (dist > range && dist > 0.f) {
        // an aim on a deck stays at the deck's height; one on the ground follows the ground
        bool bNF0 = false;
        const float h0 = g_pTerrain ? g_pTerrain->GetHeight(aim.x, aim.y, &bNF0) : aim.z;
        const bool bOnDeck = !bNF0 && aim.z > h0 + FLAT_CM;
        aim.x = me.x + dx / dist * range;
        aim.y = me.y + dy / dist * range;
        if (!bOnDeck) {
            bool bNotFound = false;
            const float h = g_pTerrain ? g_pTerrain->GetHeight(aim.x, aim.y, &bNotFound) : me.z;
            aim.z = bNotFound ? me.z : h;
        }
    }
}

void
CSkillAim::Update() {
    if (!this->IsAiming())
        return;
    if (!this->StillValid()) {
        this->Cancel();
        return;
    }
    D3DXVECTOR3 hit;
    if (this->MouseOnGround(hit)) {
        this->ClampToRange(hit);
        m_PosAIM = hit;
        m_bHaveAim = true;
    }
    if (m_bHaveAim)
        CGroundTelegraphs::Instance().SetPreview(g_pAVATAR->Get_CurPOS(), m_PosAIM, m_nSkillIDX);
}

bool
CSkillAim::OnLeftClick() {
    if (!this->IsAiming())
        return false;
    // where the mouse is now, not where it was last frame
    D3DXVECTOR3 hit;
    if (this->MouseOnGround(hit)) {
        this->ClampToRange(hit);
        m_PosAIM = hit;
        m_bHaveAim = true;
    }
    if (!m_bHaveAim)
        return true; // the sky: nothing to aim at, keep aiming
    const int iSlot = m_iSlot;
    D3DXVECTOR3 pos = m_PosAIM;
    this->Cancel();
    g_SkillManager.FireSkill(iSlot, 0, pos);
    return true;
}

bool
CSkillAim::OnRightDown(int x, int y) {
    if (!this->IsAiming())
        return false;
    m_bRightDown = true;
    m_iRightX = x;
    m_iRightY = y;
    return true;
}

bool
CSkillAim::OnRightUp(int x, int y) {
    if (!this->IsAiming() || !m_bRightDown)
        return false;
    m_bRightDown = false;
    if (abs(x - m_iRightX) <= RIGHT_CLICK_DRAG_PX && abs(y - m_iRightY) <= RIGHT_CLICK_DRAG_PX) {
        this->Cancel();
        return true;
    }
    return false; // a drag: the camera turned, keep aiming
}
