#include "stdafx.h"

#include "nav/nav_agent.h"

#include "CObjCHAR.h"
#include "network.h"

#include <cmath>

using namespace Rose::Network;

namespace Nav {

namespace {

// A stalled zone tick hands Proc one big dwPassTIME. Uncapped, a single step
// could carry a character past several corners at once, so a path step is
// capped (the rest of a long stall is simply lost, as a frozen server would).
constexpr DWORD MAX_STEP_MS = 500;

// Corners crossed inside one step. Two legs plus the one it started on is
// plenty: legs are metres long and a step is at most MAX_STEP_MS of walking.
constexpr int MAX_LEGS_PER_STEP = 2;

float
dist2d(const tPOINTF& a, const tPOINTF& b) {
    const float dx = b.x - a.x;
    const float dy = b.y - a.y;
    return sqrtf(dx * dx + dy * dy);
}

} // namespace

Agent::Agent(std::vector<tPOINTF> points, bool run, DWORD lead_ms, int chase_target):
    m_Points(std::move(points)), m_bRun(run), m_dwLeadMS(lead_ms), m_iChaseTarget(chase_target) {
}

bool
Agent::Begin(CObjCHAR& c) {
    if (m_Points.empty()) {
        return false;
    }

    m_Cur = 0;
    m_Announced = 0;

    // The base move: no walkability gate and no packet. SendLeg sends a
    // target-less leg instead of the plain move packet.
    if (!c.CObjAI::SetCMD_MOVE2D(m_Points[0].x, m_Points[0].y, m_bRun ? 1 : 0)) {
        return false;
    }

    this->SendLeg(c, 0);
    return true;
}

bool
Agent::Owns(CObjCHAR& c) const {
    return CMD_MOVE == c.Get_COMMAND() && 0 == c.Get_TargetIDX()
        && c.m_PosGOTO.x == m_Points[m_Cur].x && c.m_PosGOTO.y == m_Points[m_Cur].y;
}

bool
Agent::Advance(CObjCHAR& c, DWORD dwPassTIME) {
    float fTime = (float)(dwPassTIME < MAX_STEP_MS ? dwPassTIME : MAX_STEP_MS);

    for (int iLegs = 0; iLegs <= MAX_LEGS_PER_STEP && fTime > 0.f; ++iLegs) {
        const float fStep = c.m_MoveVEC.Length(); // cm per ms
        if (fStep <= 0.f) {
            return true; // no speed (rooted, speed 0): hold the corner
        }

        const tPOINTF& goal = m_Points[m_Cur];
        const float fNeed = dist2d(c.m_PosCUR, goal) / fStep;
        if (fNeed > fTime) {
            c.m_PosCUR += c.m_MoveVEC * fTime;
            break;
        }

        // A corner: stand exactly on it, then spend the rest of the step on the
        // next leg. The plain mover overshoots its goal by up to one step.
        c.m_PosCUR = goal;
        fTime -= fNeed;
        if (m_Cur + 1 >= m_Points.size()) {
            return false;
        }

        ++m_Cur;
        c.m_PosGOTO = m_Points[m_Cur];
        c.Start_MOVE(c.total_move_speed());
        if (m_Announced < m_Cur) {
            this->SendLeg(c, m_Cur);
        }
    }

    // Tell the clients about the next leg a little early, so they turn at the
    // corner instead of stopping on it while the next packet is on its way.
    // They cut the corner by about speed x lead; the server still walks it.
    if (m_dwLeadMS && m_Announced == m_Cur && m_Cur + 1 < m_Points.size()) {
        const float fStep = c.m_MoveVEC.Length();
        if (fStep > 0.f && dist2d(c.m_PosCUR, m_Points[m_Cur]) <= fStep * m_dwLeadMS) {
            this->SendLeg(c, m_Cur + 1);
        }
    }

    return true;
}

void
Agent::Resend(CObjCHAR& c) {
    this->SendLeg(c, m_Announced);
}

void
Agent::SendLeg(CObjCHAR& c, size_t idx) {
    // What the server still has to walk to reach the point: the rest of the
    // current leg plus every leg up to it. The client compares it with its own
    // distance to decide whether it fell behind.
    float fRemain = dist2d(c.m_PosCUR, m_Points[m_Cur]);
    for (size_t i = m_Cur; i < idx; ++i) {
        fRemain += dist2d(m_Points[i], m_Points[i + 1]);
    }

    Packet pak = build_char_move_leg_packet(c, m_Points[idx], fRemain);
    send_packet_nearby(c, pak);
    m_Announced = idx;
}

} // namespace Nav
