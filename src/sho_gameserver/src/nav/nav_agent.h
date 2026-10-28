#pragma once

#include <vector>

class CObjCHAR;

namespace Nav {

/// Walks a character along a list of waypoints: the server-side half of a path
/// (doc/pathfinding-and-z-plan.md, section 3.2). The server clamps the character
/// exactly onto every corner; the clients are told one leg at a time with a
/// target-less CharacterMove, which they walk like any AI move. A move with a
/// target id would make them home straight on the target instead.
///
/// Phase 0 drives it from the GM probe (/nav trail); later phases feed it
/// planned paths. The character owns the agent (CObjCHAR::m_pNav) and drops it
/// the moment anything else re-commands it (Owns).
class Agent {
public:
    /// lead_ms: send the next leg this long before the server reaches the
    /// corner, so the client turns without stopping (0 = at the corner).
    /// chase_target: object index to run at and attack after the last corner
    /// (0 = stop there).
    Agent(std::vector<tPOINTF> points, bool run, DWORD lead_ms, int chase_target);

    /// Start the first leg. False if the character cannot move now.
    bool Begin(CObjCHAR& c);

    /// Does this agent still own the character's movement? False once anything
    /// else gave it a new command or destination.
    bool Owns(CObjCHAR& c) const;

    /// Move the character by dwPassTIME along its legs, stopping exactly on each
    /// corner and spending the rest of the step on the next leg. False once the
    /// last waypoint is reached.
    bool Advance(CObjCHAR& c, DWORD dwPassTIME);

    /// Send again the leg the clients were last told (move speed re-sync).
    void Resend(CObjCHAR& c);

    /// The waypoint the clients are walking to, for new viewers (tag_ADD_CHAR).
    const tPOINTF& AnnouncedPoint() const { return m_Points[m_Announced]; }

    int ChaseTarget() const { return m_iChaseTarget; }
    size_t PointCount() const { return m_Points.size(); }

private:
    void SendLeg(CObjCHAR& c, size_t idx);

    std::vector<tPOINTF> m_Points;
    size_t m_Cur = 0; ///< the waypoint the server walks to
    size_t m_Announced = 0; ///< the last waypoint sent to the clients
    bool m_bRun;
    DWORD m_dwLeadMS;
    int m_iChaseTarget;
};

} // namespace Nav
