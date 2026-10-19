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
        out = o + d * hi;
        bool bNF = false;
        const float hz = g_pTerrain->GetHeight(out.x, out.y, &bNF);
        if (!bNF)
            out.z = hz;
        return true;
    }
    return false;
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
        aim.x = me.x + dx / dist * range;
        aim.y = me.y + dy / dist * range;
        bool bNotFound = false;
        const float h = g_pTerrain ? g_pTerrain->GetHeight(aim.x, aim.y, &bNotFound) : me.z;
        aim.z = bNotFound ? me.z : h;
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
