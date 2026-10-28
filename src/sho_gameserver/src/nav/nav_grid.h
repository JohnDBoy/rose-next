#pragma once

#include <memory>
#include <string>
#include <vector>

namespace Nav {

/// No height known (a character the grid has not placed yet, a zone without a grid).
constexpr short NO_Z = -32768;

/// The avatar's step (UpdateFootHeight_Avatar casts down from foot + 135 cm).
constexpr float STEP_CM = 135.f;

enum SpanFlag : unsigned char {
    SPAN_WALK = 1, ///< nothing 30-180 cm above it: a body fits
    SPAN_REACHED = 2, ///< connected to the zone's start, revive, warp, regen or NPC points
    SPAN_TERRAIN = 4,
    SPAN_UP = 8, ///< an up-facing floor (or the terrain)
    SPAN_HAZARD = 16, ///< the client would draw a monster here 3 m+ higher (a roof)
};

/// One floor at a spot.
struct Span {
    float z;
    unsigned char flags;
    unsigned char clearance; ///< 1 next to an obstacle, 2 with 1.5 m clear, 3 with 2.5 m
    unsigned short component; ///< 0 = unreached
};

/// A zone's layered walk grid, <ZONE FOLDER>.lnav, baked by scripts/nav-bake.py (format:
/// scripts/rosefmt/lnav.py; design: doc/pathfinding-and-z-plan.md, section 3.1). Read-only
/// once loaded, so any thread may query it.
///
/// 1 m cells in 160 x 160 tiles, one per map chunk. Every cell has its terrain floor; a
/// "complex" cell lists every floor (decks, platforms, stairs, Z-only floors) lowest first,
/// and may carry the height the client draws a monster at (GetHeightTop).
class Grid {
public:
    /// Load zoneDir + folder + ".lnav". Null (and why, in err) when there is none or it
    /// does not parse. staleInputs: the bake's inputs that changed or vanished since
    /// (chunk files are read from zoneDir, the rest from baseDir).
    static std::unique_ptr<Grid> Load(const std::string& zoneDir,
        const std::string& baseDir,
        std::string& err,
        int& staleInputs);

    ~Grid();

    /// Terrain height at a world position (bilinear over the 2.5 m vertices, like the
    /// client's CMAP::GetHEIGHT), or NO_Z off the grid.
    float TerrainZ(float x, float y) const;

    /// Every floor at a world position, lowest first; returns the count (0 off the grid).
    int SpansAt(float x, float y, Span* out, int iMax) const;

    /// Where today's client draws a monster standing here (GetHeightTop), or NO_Z.
    float VisualTopZ(float x, float y) const;

    /// The height a walker reaches going from 'from' at fromZ to 'to', cell by cell: at
    /// each cell the highest floor no more than STEP_CM above its current height, or the
    /// lowest floor when every one is higher (it falls). The avatar's own rule.
    float FollowZ(float fromZ, float fromX, float fromY, float toX, float toY) const;

    /// The floor nearest z within 'within' cm at a world position; false if none.
    bool NearestSpan(float x, float y, float z, float within, Span& out) const;

    size_t Bytes() const { return m_Bytes; }
    int TileCount() const { return m_iTiles; }

private:
    struct Tile;
    Grid();
    const Tile* TileAt(float x, float y, int& cell) const;
    float CellZ(const Tile& t, int cell, float x, float y, float stored, unsigned char flags) const;
    float Pick(const Span* spans, int n, float curZ) const;

    Tile* m_pTiles[64][64];
    int m_iTiles = 0;
    size_t m_Bytes = 0;
};

} // namespace Nav
