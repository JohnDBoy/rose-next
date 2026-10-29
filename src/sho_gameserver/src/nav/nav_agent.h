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
/// Phase 0 drives it from the GM probe (/nav trail); Phase 5 feeds it planned
/// paths. The character owns the agent (CObjCHAR::m_pNav) and drops it the
/// moment anything else re-commands it (Owns).
///
/// Two kinds:
///   - a walk (CMD_MOVE, or CMD_RUNAWAY for a leash), target-less: it stops at the
///     last corner, or (the probe) runs at chase_target from there;
///   - a chase (Phase 5): the character stays in CMD_ATTACK on chase_target while
///     the legs take it round what is in the way; the clients, told target-less
///     legs, are sent the chase again when it ends (CObjCHAR::Nav_ResumeChase).
class Agent {
public:
    /// lead_ms: send the next leg this long before the server reaches the
    /// corner, so the client turns without stopping (0 = at the corner).
    /// chase_target: object index to run at and attack after the last corner
    /// (0 = stop there); for a chase, the target being chased.
    /// goal: where the path was planned to (re-planned when that moves 4 m).
    Agent(std::vector<tPOINTF> points, bool run, DWORD lead_ms, int chase_target, bool chase = false,
        tPOINTF goal = {0, 0});

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
    bool IsChase() const { return m_bChase; }
    const tPOINTF& Goal() const { return m_Goal; }
    size_t PointCount() const { return m_Points.size(); }

private:
    void SendLeg(CObjCHAR& c, size_t idx);

    std::vector<tPOINTF> m_Points;
    size_t m_Cur = 0; ///< the waypoint the server walks to
    size_t m_Announced = 0; ///< the last waypoint sent to the clients
    bool m_bRun;
    DWORD m_dwLeadMS;
    int m_iChaseTarget;
    bool m_bChase;
    tPOINTF m_Goal;
};

} // namespace Nav
