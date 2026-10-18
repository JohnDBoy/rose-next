#pragma once

#include <vector>

class CObjCHAR;

/// Boss attack telegraphs (2026-10-18): while a monster casts a skill flagged in
/// LIST_SKILL col 83 (SKILL_TELEGRAPH), the area it is about to hit is drawn on the
/// ground -- a translucent red area with a bright rim, and an inner fill that grows to
/// the rim as the cast runs, so a player sees both where it lands and when. When the
/// skill fires the area flashes and fades; an interrupted cast (stun, death, cancel)
/// just goes.
///
/// Client-only, from data the client already has: the cast start
/// (CObjAI::ProcSkillCastingAction, the same moment the cast clip starts), the scope
/// (SKILL_SCOPE_RADIUS) and the cast length (one play of the cast clip at its casting
/// speed, as the server times it). A monster casts every area skill on itself -- type
/// 17 around its own position, and type 7 through SetCMD_Skill2OBJ, whose aim the
/// server resets to the caster (Goto_TARGET) -- so the area is a circle around the
/// caster where the cast began; monsters do not move while casting.
///
/// The geometry follows the terrain (CTERRAIN::GetHeight per vertex, lifted a little)
/// and goes to the engine's ground overlay (::setGroundOverlay) every frame, drawn
/// right after the terrain: z-tested, so rocks hide it and characters stand over it.
class CGroundTelegraphs {
public:
    static CGroundTelegraphs& Instance();

    /// pCaster has just started casting nSkillIDX; dwCastMS is its cast clip's length.
    void OnCastStart(CObjCHAR* pCaster, short nSkillIDX, unsigned long dwCastMS);
    /// Per frame (CObjectMANAGER::ProcOBJECT): ends the finished casts, sends the geometry.
    void Update();
    /// CObjectMANAGER::Clear deleted every object: drop them all.
    void Forget();

private:
    struct Telegraph {
        short nObjIdx;
        CObjCHAR* pCaster; // what the slot held at the cast start
        short nSkillIDX;
        float fX, fY, fZ; // centre, world cm (fZ: fallback where there is no terrain)
        float fRadius; // cm
        unsigned long dwStart;
        unsigned long dwCastMS;
        unsigned long dwFiredAt; // 0 while casting; else when it fired (the flash)
    };

    CGroundTelegraphs() {}
    bool StillCasting(const Telegraph& t) const;
    float Height(const Telegraph& t, float fX, float fY) const;
    /// An annulus r0..r1 around the telegraph's centre, its colour going from c0 at r0
    /// to c1 at r1 (ARGB).
    void AddRing(const Telegraph& t, float r0, float r1, unsigned long c0, unsigned long c1);
    void AddTelegraph(const Telegraph& t, unsigned long now);

    std::vector<Telegraph> m_List;
    std::vector<float> m_XYZ; // this frame's triangles
    std::vector<unsigned long> m_Colors;
    bool m_bSent = false; // the engine holds a non-empty overlay
};
