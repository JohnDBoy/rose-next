#pragma once

#include <vector>

#include <d3dx9math.h>

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
/// (io_skill.h SKILL_SCOPE_*) and the cast length (one play of the cast clip at its
/// casting speed, as the server times it). Three shapes, as the server measures them
/// (CObjCHAR::Skill_DamageToAROUND):
///   - a circle of SKILL_SCOPE_RADIUS around the caster: a type-17 skill, or any area
///     cast on a target that has no aim (the server resets that aim to the caster);
///   - a cone (SKILL_SCOPE_CONE) or a frontal strip (SKILL_SCOPE_FRONTAL) from the
///     caster toward the spot the server aimed it at when the cast began, sent with
///     GSV_SKILL_START (CObjAI::m_PosSkillAIM). The fill runs out from the caster.
/// Monsters do not move while casting, so the shape stays where the cast began.
///
/// The geometry follows the terrain (CTERRAIN::GetHeight per vertex, lifted a little)
/// and goes to the engine's ground overlay (::setGroundOverlay) every frame, drawn
/// right after the terrain: z-tested, so rocks hide it and characters stand over it.
class CGroundTelegraphs {
public:
    static CGroundTelegraphs& Instance();

    /// pCaster has just started casting nSkillIDX; dwCastMS is its cast clip's length.
    /// Its aim, if any, is pCaster->m_PosSkillAIM while m_bSkillAimActive.
    void OnCastStart(CObjCHAR* pCaster, short nSkillIDX, unsigned long dwCastMS);
    /// The aim reached a cast that had already started without it (Recv_gsv_SKILL_START):
    /// its telegraph turns from the fallback circle into the cone or strip, timing kept.
    void OnAimArrived(CObjCHAR* pCaster);
    /// Per frame (CObjectMANAGER::ProcOBJECT): ends the finished casts, sends the geometry.
    void Update();
    /// CObjectMANAGER::Clear deleted every object: drop them all.
    void Forget();

    /// The player's own area skill while it is aimed (CSkillAim, 2026-10-19), set every
    /// frame until ClearPreview: its area at posAim -- or, for a strip or cone, from
    /// posCaster toward posAim -- in a friendly colour, and a faint ring at its range.
    void SetPreview(const D3DXVECTOR3& posCaster, const D3DXVECTOR3& posAim, short nSkillIDX);
    void ClearPreview() { m_bPreview = false; }

private:
    enum Shape { SHAPE_CIRCLE, SHAPE_CONE, SHAPE_STRIP };

    struct Telegraph {
        short nObjIdx;
        CObjCHAR* pCaster; // what the slot held at the cast start
        short nSkillIDX;
        Shape shape;
        float fX, fY, fZ; // the caster at the cast start, world cm (fZ: where there is no terrain)
        float fDirX, fDirY; // cone, strip: unit vector toward the aim
        float fLength; // cm: circle radius, cone or strip length
        float fHalfAngle; // cone, radians
        float fHalfWidth; // strip, cm
        unsigned long dwStart;
        unsigned long dwCastMS;
        unsigned long dwFiredAt; // 0 while casting; else when it fired (the flash)
    };

    CGroundTelegraphs() {}
    /// A cone or a strip toward the caster's aim; without one, the circle the server uses.
    static void Aim(Telegraph& t, CObjCHAR* pCaster);
    /// t's cone or strip pointed at aimX, aimY, if its skill has one and the spot is not at
    /// t's own position; else it stays a circle.
    static void PointAt(Telegraph& t, float aimX, float aimY);
    /// The area, a bright rim over its outline (and a cone's or strip's sides).
    void AddOutline(const Telegraph& t, unsigned long rgb, unsigned long alphaArea, unsigned long alphaRim);
    bool StillCasting(const Telegraph& t) const;
    float Height(const Telegraph& t, float fX, float fY) const;

    /// A grid of (nRows + 1) x (nCols + 1) points on the terrain, pos(fRow, fCol) giving
    /// each point's world x, y for fractions 0..1; its colour goes from c0 on row 0 to c1
    /// on the last row (ARGB).
    template <class PosFn>
    void AddGrid(const Telegraph& t, int nRows, int nCols, PosFn pos, unsigned long c0, unsigned long c1);
    /// Part of a disc around the caster: radii r0..r1 (colour c0 -> c1), angles a0..a1
    /// (radians, from the aim; a full circle is -pi..pi).
    void AddSector(const Telegraph& t, float r0, float r1, float a0, float a1, unsigned long c0, unsigned long c1);
    /// Part of a strip: from a0 to a1 along the aim (colour c0 -> c1), s0..s1 across it.
    void AddRect(const Telegraph& t, float a0, float a1, float s0, float s1, unsigned long c0, unsigned long c1);
    /// A band along the edge x0,y0 -> x1,y1, nx,ny pointing inward: cEdge on the edge,
    /// cInner fWidth inside.
    void AddEdge(const Telegraph& t, float x0, float y0, float x1, float y1, float nx, float ny, float fWidth,
        unsigned long cEdge, unsigned long cInner);
    /// The whole shape out to fReach along it (the fill), one colour.
    void AddArea(const Telegraph& t, float fFrom, float fReach, unsigned long c0, unsigned long c1);
    void AddTelegraph(const Telegraph& t, unsigned long now);

    std::vector<Telegraph> m_List;
    std::vector<float> m_XYZ; // this frame's triangles
    std::vector<unsigned long> m_Colors;
    bool m_bSent = false; // the engine holds a non-empty overlay
    bool m_bPreview = false;
    Telegraph m_Preview; // the aimed area
    Telegraph m_PreviewRange; // the ring at the skill's range, around the player
};
