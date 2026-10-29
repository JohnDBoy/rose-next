#include "stdafx.h"

#include "nav/nav_path.h"

#include "nav/nav_grid.h"
#include "nav/nav_settings.h"
#include "nav/nav_stats.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <memory>

namespace Nav {

namespace {

constexpr int WIN = 128; // the search window, cells a side
constexpr int WIN_MARGIN = 8; // the start stays at least this far inside it
constexpr int MAX_LAYERS = 4; // walkable floors kept per cell
constexpr int NODES = WIN * WIN * MAX_LAYERS;
constexpr float CELL = 100.f;
constexpr int START_SNAP_CELLS = 2; // a start in a blocked cell steps out within 2 m
constexpr int GOAL_SNAP_CELLS = 3; // a goal within 3 m
constexpr float SNAP_Z_CM = 300.f;
constexpr float PARTIAL_GAIN_CM = 200.f;
constexpr int MAX_WAYPOINTS = 16;
constexpr int MAX_PULL_CELLS = 40; // one pulled leg spans at most this many path cells
constexpr float LEG_Z_CM = 100.f; // a pulled leg must end on the path's own floor
constexpr int COST_STRAIGHT = 10, COST_DIAGONAL = 14, NARROW_FACTOR = 3;
constexpr unsigned char WALKABLE = SPAN_WALK | SPAN_REACHED;
constexpr unsigned char GENTLE = SPAN_TERRAIN | SPAN_STAIRS;

struct PathPoint {
    float x, y, z;
};

struct CellSpans {
    uint32_t stamp;
    unsigned char n;
    unsigned char flags[MAX_LAYERS];
    unsigned char clearance[MAX_LAYERS];
    unsigned short comp[MAX_LAYERS];
    float z[MAX_LAYERS];
};

struct NodeRec {
    uint32_t stamp;
    uint32_t g;
    int32_t parent;
    bool closed;
};

struct HeapItem {
    uint32_t f;
    int32_t node;
    bool operator<(const HeapItem& o) const { return f > o.f; } // a min-heap through std::*_heap
};

// One per zone thread: generation-stamped, so a search never clears its arrays.
struct Search {
    std::vector<CellSpans> cells;
    std::vector<NodeRec> nodes;
    std::vector<HeapItem> heap;
    uint32_t gen = 0;
    int ox = 0, oy = 0; // the window's first global cell

    Search(): cells(WIN * WIN), nodes(NODES) {
        for (auto& c: cells)
            c.stamp = 0;
        for (auto& n: nodes)
            n.stamp = 0;
        heap.reserve(4096);
    }

    void NewSearch() {
        if (++gen == 0) { // wrapped: forget every stamp once
            for (auto& c: cells)
                c.stamp = 0;
            for (auto& n: nodes)
                n.stamp = 0;
            gen = 1;
        }
        heap.clear();
    }

    const CellSpans& Cell(const Grid& grid, int wx, int wy) {
        CellSpans& c = cells[wy * WIN + wx];
        if (c.stamp == gen)
            return c;
        c.stamp = gen;
        c.n = 0;
        Span sp[32];
        const int n = grid.SpansAt((ox + wx + 0.5f) * CELL, (oy + wy + 0.5f) * CELL, sp, 32);
        for (int k = 0; k < n && c.n < MAX_LAYERS; ++k) {
            if ((sp[k].flags & WALKABLE) != WALKABLE)
                continue;
            c.z[c.n] = sp[k].z;
            c.flags[c.n] = sp[k].flags;
            c.clearance[c.n] = sp[k].clearance;
            c.comp[c.n] = sp[k].component;
            ++c.n;
        }
        return c;
    }

    NodeRec& Node(int id) {
        NodeRec& r = nodes[id];
        if (r.stamp != gen) {
            r.stamp = gen;
            r.g = UINT32_MAX;
            r.parent = -1;
            r.closed = false;
        }
        return r;
    }
};

Search&
search_ctx() {
    thread_local std::unique_ptr<Search> s_pSearch;
    if (!s_pSearch)
        s_pSearch.reset(new Search());
    return *s_pSearch;
}

LONGLONG
qpc_now() {
    LARGE_INTEGER li;
    ::QueryPerformanceCounter(&li);
    return li.QuadPart;
}

LONGLONG
qpc_freq() {
    static const LONGLONG s_llFreq = [] {
        LARGE_INTEGER f;
        ::QueryPerformanceFrequency(&f);
        return f.QuadPart;
    }();
    return s_llFreq;
}

// The bake's own link rule (scripts/mapgen/navbake.py, rule 4; Grid::LineWalk).
bool
links(float za, unsigned char fa, float zb, unsigned char fb) {
    const bool bGentle = (fa & GENTLE) && (fb & GENTLE);
    return fabsf(za - zb) <= (bGentle ? STEP_CM : OBJ_STEP_CM);
}

bool
cell_links(const CellSpans& c, float z, unsigned char flags) {
    for (int k = 0; k < c.n; ++k)
        if (links(z, flags, c.z[k], c.flags[k]))
            return true;
    return false;
}

int
node_id(int wx, int wy, int k) {
    return (wy * WIN + wx) * MAX_LAYERS + k;
}

// The walkable floor nearest z in the window cell (wx, wy) or a cell within r of it, the
// nearest cell first. False if none within SNAP_Z_CM (any height when z is NO_Z).
bool
snap(Search& S, const Grid& grid, int wx, int wy, float z, int r, int& outX, int& outY, int& outK) {
    for (int ring = 0; ring <= r; ++ring) {
        float fBest = 1.0e30f;
        bool bFound = false;
        for (int dy = -ring; dy <= ring; ++dy) {
            for (int dx = -ring; dx <= ring; ++dx) {
                if ((std::max)(abs(dx), abs(dy)) != ring)
                    continue;
                const int cx = wx + dx, cy = wy + dy;
                if (cx < 0 || cy < 0 || cx >= WIN || cy >= WIN)
                    continue;
                const CellSpans& c = S.Cell(grid, cx, cy);
                for (int k = 0; k < c.n; ++k) {
                    const float d = (NO_Z == z) ? 0.f : fabsf(c.z[k] - z);
                    if (d <= SNAP_Z_CM && d < fBest) {
                        fBest = d;
                        outX = cx;
                        outY = cy;
                        outK = k;
                        bFound = true;
                    }
                }
            }
        }
        if (bFound)
            return true;
    }
    return false;
}

// Greedy string-pulling: from each anchor, the farthest path point (at most MAX_PULL_CELLS
// on) that a straight walk reaches on the path's own floor, found by bisection.
void
pull(const Grid& grid, const std::vector<PathPoint>& pts, std::vector<tPOINTF>& out) {
    out.clear();
    size_t anchor = 0;
    auto reaches = [&](size_t from, size_t to) {
        float fz;
        return grid.LineWalk(pts[from].x, pts[from].y, pts[from].z, pts[to].x, pts[to].y, nullptr,
                   nullptr, &fz)
            && fabsf(fz - pts[to].z) <= LEG_Z_CM;
    };
    while (anchor + 1 < pts.size() && out.size() < MAX_WAYPOINTS) {
        size_t lo = anchor + 1; // the next path cell: a step A* took, always walkable
        size_t hi = (std::min)(pts.size() - 1, anchor + MAX_PULL_CELLS);
        while (lo < hi) {
            const size_t mid = (lo + hi + 1) / 2;
            if (reaches(anchor, mid))
                lo = mid;
            else
                hi = mid - 1;
        }
        tPOINTF p;
        p.x = pts[lo].x;
        p.y = pts[lo].y;
        out.push_back(p);
        anchor = lo;
    }
}

} // namespace

void
TickBudget::Reset() {
    const Settings& s = settings();
    m_iSearches = s.path_tick_searches.load(std::memory_order_relaxed);
    m_iExpansions = s.path_tick_expansions.load(std::memory_order_relaxed);
    m_llTicksLeft = qpc_freq() * s.path_tick_us.load(std::memory_order_relaxed) / 1000000;
}

bool
TickBudget::CanSearch() const {
    return m_iSearches > 0 && m_iExpansions > 0 && m_llTicksLeft > 0;
}

void
TickBudget::Spend(int iExpansions, LONGLONG llTicks) {
    --m_iSearches;
    m_iExpansions -= iExpansions;
    m_llTicksLeft -= llTicks;
}

const char*
PathResultName(PathResult r) {
    switch (r) {
        case PathResult::Found:
            return "found";
        case PathResult::Partial:
            return "partial";
        case PathResult::Failed:
            return "failed";
        case PathResult::Unreachable:
            return "unreachable";
        case PathResult::NoFloor:
            return "no floor";
        case PathResult::Deferred:
            return "deferred";
    }
    return "?";
}

PathResult
FindPath(const Grid& grid, const PathQuery& q, TickBudget& budget, ZoneMeter& meter,
    std::vector<tPOINTF>& out, int* pExpansions) {
    out.clear();
    if (pExpansions)
        *pExpansions = 0;
    if (!budget.CanSearch()) {
        meter.CountPathDeferred();
        return PathResult::Deferred;
    }
    const LONGLONG llStart = qpc_now();
    Search& S = search_ctx();
    S.NewSearch();

    // The window: centred between start and goal, the start kept WIN_MARGIN inside it.
    const int scx = (int)floorf(q.x0 / CELL), scy = (int)floorf(q.y0 / CELL);
    const int gcx = (int)floorf(q.x1 / CELL), gcy = (int)floorf(q.y1 / CELL);
    S.ox = (std::min)((std::max)((scx + gcx) / 2 - WIN / 2, scx - (WIN - 1 - WIN_MARGIN)), scx - WIN_MARGIN);
    S.oy = (std::min)((std::max)((scy + gcy) / 2 - WIN / 2, scy - (WIN - 1 - WIN_MARGIN)), scy - WIN_MARGIN);

    PathResult result = PathResult::Failed;
    int iExp = 0;

    auto finish = [&](PathResult r) {
        const LONGLONG llTicks = qpc_now() - llStart;
        budget.Spend(iExp, llTicks);
        meter.CountPathSearch((int)r, iExp, (double)llTicks * 1000.0 / (double)qpc_freq());
        if (pExpansions)
            *pExpansions = iExp;
        return r;
    };

    int sx, sy, sk;
    if (!snap(S, grid, scx - S.ox, scy - S.oy, q.z0, START_SNAP_CELLS, sx, sy, sk)) {
        return finish(PathResult::NoFloor);
    }
    const CellSpans& startCell = S.Cell(grid, sx, sy);
    const unsigned short startComp = startCell.comp[sk];
    const float startZ = startCell.z[sk];

    // the goal: its own floor if the window holds it
    int gx = -1, gy = -1, gk = -1;
    const int gwx = gcx - S.ox, gwy = gcy - S.oy;
    const bool bGoalInWin = gwx >= 0 && gwy >= 0 && gwx < WIN && gwy < WIN;
    if (bGoalInWin) {
        if (!snap(S, grid, gwx, gwy, NO_Z == q.z1 ? q.z0 : q.z1, GOAL_SNAP_CELLS, gx, gy, gk)) {
            return finish(PathResult::NoFloor);
        }
        const unsigned short goalComp = S.Cell(grid, gx, gy).comp[gk];
        if (startComp && goalComp && startComp != goalComp) {
            return finish(PathResult::Unreachable);
        }
    } else {
        // only a partial path can come of it: aim at the real goal cell
        gx = gwx;
        gy = gwy;
    }
    const int goalId = bGoalInWin ? node_id(gx, gy, gk) : -1;

    auto heur = [&](int wx, int wy) -> uint32_t {
        const int dx = abs(wx - gx), dy = abs(wy - gy);
        const int h = COST_STRAIGHT * (std::max)(dx, dy) + (COST_DIAGONAL - COST_STRAIGHT) * (std::min)(dx, dy);
        return (uint32_t)(h * 6 / 5); // weighted 1.2: fewer cells, near-shortest paths
    };

    const int iMaxExp = (std::min)(settings().path_expansions.load(std::memory_order_relaxed),
        budget.ExpansionsLeft());
    const int iPref = q.iPrefClass < 1 ? 1 : (q.iPrefClass > 3 ? 3 : q.iPrefClass);

    const int startId = node_id(sx, sy, sk);
    {
        NodeRec& r = S.Node(startId);
        r.g = 0;
        S.heap.push_back({heur(sx, sy), startId});
    }
    int bestId = startId;
    uint32_t bestH = heur(sx, sy);
    int endId = -1;

    static const int DX[8] = {1, -1, 0, 0, 1, 1, -1, -1};
    static const int DY[8] = {0, 0, 1, -1, 1, -1, 1, -1};

    while (!S.heap.empty()) {
        std::pop_heap(S.heap.begin(), S.heap.end());
        const HeapItem it = S.heap.back();
        S.heap.pop_back();
        NodeRec& cur = S.Node(it.node);
        if (cur.closed)
            continue;
        cur.closed = true;
        ++iExp;

        if (it.node == goalId) {
            endId = it.node;
            break;
        }
        const int cell = it.node / MAX_LAYERS, ck = it.node % MAX_LAYERS;
        const int cx = cell % WIN, cy = cell / WIN;
        const uint32_t h = heur(cx, cy);
        if (h < bestH) {
            bestH = h;
            bestId = it.node;
        }
        if (iExp >= iMaxExp)
            break;

        const CellSpans& cc = S.Cell(grid, cx, cy);
        const float cz = cc.z[ck];
        const unsigned char cf = cc.flags[ck];
        const uint32_t g = cur.g;

        for (int d = 0; d < 8; ++d) {
            const int nx = cx + DX[d], ny = cy + DY[d];
            if (nx < 0 || ny < 0 || nx >= WIN || ny >= WIN)
                continue;
            const bool bDiag = d >= 4;
            // no corner cutting: both cells beside a diagonal step must be walkable from here
            if (bDiag
                && (!cell_links(S.Cell(grid, nx, cy), cz, cf) || !cell_links(S.Cell(grid, cx, ny), cz, cf)))
                continue;
            const CellSpans& nc = S.Cell(grid, nx, ny);
            for (int k = 0; k < nc.n; ++k) {
                if (!links(cz, cf, nc.z[k], nc.flags[k]))
                    continue;
                uint32_t cost = bDiag ? COST_DIAGONAL : COST_STRAIGHT;
                if (nc.clearance[k] < iPref)
                    cost *= NARROW_FACTOR;
                const int nid = node_id(nx, ny, k);
                NodeRec& nr = S.Node(nid);
                if (nr.closed || g + cost >= nr.g)
                    continue;
                nr.g = g + cost;
                nr.parent = it.node;
                S.heap.push_back({nr.g + heur(nx, ny), nid});
                std::push_heap(S.heap.begin(), S.heap.end());
            }
        }
    }

    if (endId < 0) {
        // the best partial path, if it gets at least 2 m closer
        const int bcell = bestId / MAX_LAYERS;
        const float bx = (S.ox + bcell % WIN + 0.5f) * CELL, by = (S.oy + bcell / WIN + 0.5f) * CELL;
        const float d0 = sqrtf((q.x1 - q.x0) * (q.x1 - q.x0) + (q.y1 - q.y0) * (q.y1 - q.y0));
        const float d1 = sqrtf((q.x1 - bx) * (q.x1 - bx) + (q.y1 - by) * (q.y1 - by));
        if (bestId == startId || d1 > d0 - PARTIAL_GAIN_CM)
            return finish(PathResult::Failed);
        endId = bestId;
        result = PathResult::Partial;
    } else {
        result = PathResult::Found;
    }

    // the cells, start to end
    static thread_local std::vector<PathPoint> s_Pts;
    s_Pts.clear();
    for (int id = endId; id >= 0; id = S.Node(id).parent) {
        const int cell = id / MAX_LAYERS, k = id % MAX_LAYERS;
        const int wx = cell % WIN, wy = cell / WIN;
        const CellSpans& c = S.Cell(grid, wx, wy);
        s_Pts.push_back({(S.ox + wx + 0.5f) * CELL, (S.oy + wy + 0.5f) * CELL, c.z[k]});
        if (id == startId)
            break;
    }
    std::reverse(s_Pts.begin(), s_Pts.end());
    s_Pts.front() = {q.x0, q.y0, startZ};
    if (PathResult::Found == result && gcx == S.ox + gx && gcy == S.oy + gy) {
        s_Pts.back().x = q.x1; // the goal's own spot, in its cell
        s_Pts.back().y = q.y1;
    }
    if (s_Pts.size() < 2)
        return finish(PathResult::Failed);

    pull(grid, s_Pts, out);
    return finish(result);
}

} // namespace Nav
