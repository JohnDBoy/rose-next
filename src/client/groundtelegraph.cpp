#include "stdafx.h"

#include "groundtelegraph.h"

#include "cobjchar.h"
#include "io_terrain.h"
#include "object.h"
#include "common/io_skill.h"
#include "zz_interface.h"

#include <math.h>

namespace {
const float LIFT_CM = 20.f; // over the terrain: GetHeight is bilinear, the mesh is triangles
const float SEGMENT_CM = 80.f; // rim length per segment
const float STEP_CM = 100.f; // radial spacing of the rings the terrain is sampled on
const int MIN_SEGMENTS = 24;
const int MAX_SEGMENTS = 96;
const unsigned long WAIT_MS = 3000; // past the clip, waiting for the server to fire it
const unsigned long FLASH_MS = 350; // the fired flash's fade
const unsigned long DEFAULT_CAST_MS = 1000; // a cast with no clip

const unsigned long RGB_AREA = 0xFF4020; // red-orange
const unsigned long RGB_FILL = 0xFF6A20;
const unsigned long RGB_FLASH = 0xFF9A50;
const float RIM_CM = 60.f;
const float EDGE_CM = 40.f;

unsigned long
Argb(unsigned long alpha, unsigned long rgb) {
    return (alpha << 24) | (rgb & 0xFFFFFF);
}

unsigned long
Lerp(unsigned long c0, unsigned long c1, float f) {
    unsigned long out = 0;
    for (int shift = 0; shift < 32; shift += 8) {
        const float a = (float)((c0 >> shift) & 0xFF);
        const float b = (float)((c1 >> shift) & 0xFF);
        out |= ((unsigned long)(a + (b - a) * f + 0.5f) & 0xFF) << shift;
    }
    return out;
}
} // namespace

CGroundTelegraphs&
CGroundTelegraphs::Instance() {
    static CGroundTelegraphs s_Instance;
    return s_Instance;
}

void
CGroundTelegraphs::OnCastStart(CObjCHAR* pCaster, short nSkillIDX, unsigned long dwCastMS) {
    if (!pCaster || nSkillIDX <= 0)
        return;
    const float fRadius = (float)SKILL_SCOPE_RADIUS(nSkillIDX);
    if (fRadius <= 0.f)
        return;

    Telegraph t;
    t.nObjIdx = pCaster->Get_INDEX();
    t.pCaster = pCaster;
    t.nSkillIDX = nSkillIDX;
    t.fX = pCaster->Get_CurPOS().x;
    t.fY = pCaster->Get_CurPOS().y;
    t.fZ = pCaster->Get_CurPOS().z;
    t.fRadius = fRadius;
    t.dwStart = ::GetTickCount();
    t.dwCastMS = dwCastMS ? dwCastMS : DEFAULT_CAST_MS;
    t.dwFiredAt = 0;

    for (Telegraph& old: m_List) {
        if (old.nObjIdx == t.nObjIdx) { // a new cast replaces the caster's last one
            old = t;
            return;
        }
    }
    m_List.push_back(t);
}

bool
CGroundTelegraphs::StillCasting(const Telegraph& t) const {
    // Casting_END clears m_nActiveSkillIDX for every way a cast ends: the action
    // starting, a stop, a stun or sleep, death, a cancel. A cast replaced without it
    // (SetCMD_MOVE) is caught by the time limit.
    return t.pCaster->m_nActiveSkillIDX == t.nSkillIDX && t.pCaster->Get_HP() > 0
           && ::GetTickCount() - t.dwStart < t.dwCastMS + WAIT_MS;
}

void
CGroundTelegraphs::Update() {
    const unsigned long now = ::GetTickCount();
    m_XYZ.clear();
    m_Colors.clear();

    for (size_t i = 0; i < m_List.size();) {
        Telegraph& t = m_List[i];
        const bool bAlive = g_pObjMGR && g_pObjMGR->Get_OBJECT(t.nObjIdx) == t.pCaster;
        bool bKeep = true;
        if (t.dwFiredAt) {
            bKeep = now - t.dwFiredAt < FLASH_MS;
        } else if (!bAlive) {
            bKeep = false;
        } else if (!this->StillCasting(t)) {
            // Fired: the action took over (ProcSkillAction sets m_nDoingSkillIDX in the
            // frame Casting_END runs). Anything else was an interruption.
            if (t.pCaster->m_nDoingSkillIDX == t.nSkillIDX) {
                t.dwFiredAt = now;
            } else {
                bKeep = false;
            }
        }
        if (!bKeep) {
            m_List.erase(m_List.begin() + i);
            continue;
        }
        this->AddTelegraph(t, now);
        ++i;
    }

    if (!m_XYZ.empty()) {
        ::setGroundOverlay(&m_XYZ[0], &m_Colors[0], (int)m_Colors.size());
        m_bSent = true;
    } else if (m_bSent) {
        ::setGroundOverlay(NULL, NULL, 0);
        m_bSent = false;
    }
}

void
CGroundTelegraphs::Forget() {
    m_List.clear();
    if (m_bSent) {
        ::setGroundOverlay(NULL, NULL, 0);
        m_bSent = false;
    }
}

float
CGroundTelegraphs::Height(const Telegraph& t, float fX, float fY) const {
    bool bNotFound = false;
    float fZ = g_pTerrain ? g_pTerrain->GetHeight(fX, fY, &bNotFound) : t.fZ;
    if (!g_pTerrain || bNotFound)
        fZ = t.fZ;
    return fZ + LIFT_CM;
}

void
CGroundTelegraphs::AddRing(const Telegraph& t, float r0, float r1, unsigned long c0, unsigned long c1) {
    if (r0 < 0.f)
        r0 = 0.f;
    if (r1 <= r0)
        return;

    int nSegs = (int)(2.f * 3.14159265f * t.fRadius / SEGMENT_CM);
    if (nSegs < MIN_SEGMENTS)
        nSegs = MIN_SEGMENTS;
    if (nSegs > MAX_SEGMENTS)
        nSegs = MAX_SEGMENTS;
    int nSteps = (int)ceilf((r1 - r0) / STEP_CM);
    if (nSteps < 1)
        nSteps = 1;

    // The rings' points, once each: (nSteps + 1) x nSegs, the terrain sampled at every one.
    static std::vector<float> s_Grid; // x, y, z
    s_Grid.resize((size_t)(nSteps + 1) * nSegs * 3);
    for (int k = 0; k <= nSteps; ++k) {
        const float r = r0 + (r1 - r0) * k / nSteps;
        for (int s = 0; s < nSegs; ++s) {
            const float a = 2.f * 3.14159265f * s / nSegs;
            float* p = &s_Grid[((size_t)k * nSegs + s) * 3];
            p[0] = t.fX + r * cosf(a);
            p[1] = t.fY + r * sinf(a);
            p[2] = this->Height(t, p[0], p[1]);
        }
    }

    for (int k = 0; k < nSteps; ++k) {
        const unsigned long cIn = Lerp(c0, c1, (float)k / nSteps);
        const unsigned long cOut = Lerp(c0, c1, (float)(k + 1) / nSteps);
        for (int s = 0; s < nSegs; ++s) {
            const int s2 = (s + 1) % nSegs;
            const float* a = &s_Grid[((size_t)k * nSegs + s) * 3];
            const float* b = &s_Grid[((size_t)k * nSegs + s2) * 3];
            const float* c = &s_Grid[((size_t)(k + 1) * nSegs + s) * 3];
            const float* d = &s_Grid[((size_t)(k + 1) * nSegs + s2) * 3];
            const float* tri[6] = {a, c, d, a, d, b};
            const unsigned long col[6] = {cIn, cOut, cOut, cIn, cOut, cIn};
            for (int v = 0; v < 6; ++v) {
                m_XYZ.push_back(tri[v][0]);
                m_XYZ.push_back(tri[v][1]);
                m_XYZ.push_back(tri[v][2]);
                m_Colors.push_back(col[v]);
            }
        }
    }
}

void
CGroundTelegraphs::AddTelegraph(const Telegraph& t, unsigned long now) {
    const float R = t.fRadius;

    if (t.dwFiredAt) { // the hit: a flash that fades
        const float f = 1.f - (float)(now - t.dwFiredAt) / FLASH_MS;
        const unsigned long alpha = (unsigned long)(0x90 * (f > 0.f ? f : 0.f));
        this->AddRing(t, 0.f, R, Argb(alpha, RGB_FLASH), Argb(alpha, RGB_FLASH));
        return;
    }

    float p = (float)(now - t.dwStart) / t.dwCastMS;
    if (p > 1.f)
        p = 1.f;

    // The area and its rim.
    this->AddRing(t, 0.f, R - RIM_CM, Argb(0x30, RGB_AREA), Argb(0x30, RGB_AREA));
    this->AddRing(t, R - RIM_CM, R, Argb(0x30, RGB_AREA), Argb(0xC0, RGB_AREA));
    // The fill: grows from the centre to the rim over the cast, a brighter leading edge.
    const float rFill = R * p;
    this->AddRing(t, 0.f, rFill - EDGE_CM, Argb(0x38, RGB_FILL), Argb(0x38, RGB_FILL));
    this->AddRing(t, rFill - EDGE_CM, rFill, Argb(0x38, RGB_FILL), Argb(0x90, RGB_FILL));
}
