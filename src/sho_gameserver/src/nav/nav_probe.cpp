#include "stdafx.h"

#include "nav/nav_probe.h"

#include "nav/nav_agent.h"
#include "nav/nav_grid.h"
#include "nav/nav_settings.h"
#include "nav/nav_stats.h"

#include "GS_ThreadZONE.h"
#include "GS_USER.h"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdlib>
#include <mutex>
#include <unordered_map>

namespace Nav::Probe {

namespace {

constexpr float MIN_CORNER_CM = 100.f; // closer clicks are the same corner
constexpr size_t MAX_CORNERS = 32;
constexpr int PICK_RADIUS_CM = 3000; // nearest monster within 30 m
constexpr DWORD DEFAULT_LEAD_MS = 100;
constexpr DWORD MAX_LEAD_MS = 1000;

struct Trail {
    bool bRecording = false;
    std::vector<tPOINTF> points;
};

// Keyed by character name. Users of every zone thread touch it, but only while
// someone records (g_iRecording) or types /nav.
std::mutex g_TrailMutex;
std::unordered_map<std::string, Trail> g_Trails;
std::atomic<int> g_iRecording{0};

void
add_corner(Trail& trail, const tPOINTF& pos) {
    if (!trail.points.empty()) {
        const float dx = pos.x - trail.points.back().x;
        const float dy = pos.y - trail.points.back().y;
        if (dx * dx + dy * dy < MIN_CORNER_CM * MIN_CORNER_CM) {
            return;
        }
    }
    if (trail.points.size() < MAX_CORNERS) {
        trail.points.push_back(pos);
    }
}

void
stop_recording(Trail& trail) {
    if (trail.bRecording) {
        trail.bRecording = false;
        g_iRecording.fetch_sub(1, std::memory_order_relaxed);
    }
}

CObjCHAR*
pick_monster(classUSER& user) {
    CObjCHAR* pTarget = (CObjCHAR*)user.Get_TARGET(true);
    if (pTarget && pTarget->IsA(OBJ_MOB)) {
        return pTarget;
    }

    CObjCHAR* pBest = NULL;
    float fBest = (float)PICK_RADIUS_CM * PICK_RADIUS_CM;
    for (CObjCHAR* pFind = (CObjCHAR*)user.AI_FindFirstOBJ(PICK_RADIUS_CM); pFind;
         pFind = (CObjCHAR*)user.AI_FindNextOBJ()) {
        if (!pFind->IsA(OBJ_MOB) || pFind->Get_HP() <= 0) {
            continue;
        }
        const float dx = pFind->m_PosCUR.x - user.m_PosCUR.x;
        const float dy = pFind->m_PosCUR.y - user.m_PosCUR.y;
        if (dx * dx + dy * dy < fBest) {
            fBest = dx * dx + dy * dy;
            pBest = pFind;
        }
    }
    return pBest;
}

bool
cmd_trail(classUSER& user, const std::vector<std::string>& args) {
    DWORD dwLeadMS = DEFAULT_LEAD_MS;
    bool bRun = true;
    bool bChase = false;
    for (size_t i = 2; i < args.size(); ++i) {
        if (args[i] == "walk") {
            bRun = false;
        } else if (args[i] == "run") {
            bRun = true;
        } else if (args[i] == "chase") {
            bChase = true;
        } else {
            const int iLead = std::atoi(args[i].c_str());
            dwLeadMS = (DWORD)(iLead < 0 ? 0 : (iLead > (int)MAX_LEAD_MS ? MAX_LEAD_MS : iLead));
        }
    }

    std::vector<tPOINTF> points;
    {
        std::lock_guard<std::mutex> lock(g_TrailMutex);
        auto it = g_Trails.find(user.Get_NAME());
        if (it == g_Trails.end() || it->second.points.empty()) {
            user.send_server_whisper("No trail yet: /nav rec, walk the route, then /nav trail.");
            return false;
        }
        // The first /nav trail ends the recording where you stand; later ones
        // replay the same corners (to try another lead or speed).
        if (it->second.bRecording) {
            add_corner(it->second, user.m_PosCUR);
            stop_recording(it->second);
        }
        points = it->second.points;
    }

    CObjCHAR* pMob = pick_monster(user);
    if (!pMob) {
        user.send_server_whisper("No monster: target one, or stand within 30 m of one.");
        return false;
    }

    const size_t nPoints = points.size();
    if (!pMob->Nav_Start(new Agent(std::move(points), bRun, dwLeadMS, bChase ? user.Get_INDEX() : 0))) {
        user.send_server_whisper("That monster cannot move right now (casting?). Try again.");
        return false;
    }

    user.send_server_whisper(fmt::format("{} (obj {}) walks {} corners, {}, lead {} ms{}.",
        pMob->Get_NAME(),
        pMob->Get_INDEX(),
        nPoints,
        bRun ? "running" : "walking",
        dwLeadMS,
        bChase ? ", then chases you" : ""));
    return true;
}

std::string
floors_text(const Span* spans, int n) {
    // highest first: that is how one reads a stack of floors
    std::string out;
    for (int k = n - 1; k >= 0; --k) {
        const Span& s = spans[k];
        out += fmt::format("{}{:.1f} m {}{}{}{}", out.empty() ? "" : "; ", s.z / 100.f,
            (s.flags & SPAN_TERRAIN) ? "terrain" : "object",
            (s.flags & SPAN_REACHED) ? fmt::format(" reached c{}", (int)s.clearance) : " unreached",
            (s.flags & SPAN_WALK) ? "" : " blocked", (s.flags & SPAN_HAZARD) ? " ROOF-HAZARD" : "");
    }
    return out;
}

void
cmd_here(classUSER& user) {
    CZoneTHREAD* pZone = user.GetZONE();
    Grid* pGrid = pZone ? pZone->NavGrid() : nullptr;
    if (!pGrid) {
        user.send_server_whisper("This zone has no walk grid (scripts/nav-bake.py).");
        return;
    }
    const float x = user.m_PosCUR.x, y = user.m_PosCUR.y;
    Span spans[16];
    const int n = pGrid->SpansAt(x, y, spans, 16);
    user.send_server_whisper(fmt::format("nav at ({:.1f}, {:.1f}) m: terrain {:.1f} m, client draws monsters at {:.1f} m",
        x / 100.f, y / 100.f, pGrid->TerrainZ(x, y) / 100.f, pGrid->VisualTopZ(x, y) / 100.f));
    // m_nPosZ is the only height a client sends: where its last move started (cli_MOUSECMD),
    // so on a slope it differs from where it stands now.
    user.send_server_whisper(fmt::format("you: server {:.1f} m (your client was at {:.1f} m where your last move started)",
        user.Nav_Z() / 100.f, user.m_nPosZ / 100.f));
    user.send_server_whisper("floors: " + floors_text(spans, n));

    CObjCHAR* pTarget = (CObjCHAR*)user.Get_TARGET(true);
    if (pTarget && pTarget != &user && pTarget->GetZONE() == pZone) {
        const float tx = pTarget->m_PosCUR.x, ty = pTarget->m_PosCUR.y;
        const int tn = pGrid->SpansAt(tx, ty, spans, 16);
        user.send_server_whisper(fmt::format("target {} (obj {}): server {:.1f} m; floors under it: {}",
            pTarget->Get_NAME(), pTarget->Get_INDEX(), pTarget->Nav_Z() / 100.f, floors_text(spans, tn)));
    }
}

// What an area effect centred on you would do under the current vertical rule: a test needs no
// aiming and no counting of damage numbers.
void
cmd_aoe(classUSER& user, const std::vector<std::string>& args) {
    float fRadius = args.size() >= 3 ? (float)std::atof(args[2].c_str()) * 100.f : 1500.f;
    fRadius = fRadius < 100.f ? 100.f : (fRadius > 5000.f ? 5000.f : fRadius);
    static const char* s_szRule[] = {"off (2D)", "band", "sphere", "cylinder"};
    const int iRule = settings().aoe_vertical.load();
    const std::string rule = iRule == AOE_BAND
        ? fmt::format("band {} m + {}%", settings().aoe_band_base_cm.load() / 100.f, settings().aoe_band_slope_pct.load())
        : std::string(iRule >= 0 && iRule <= 3 ? s_szRule[iRule] : "?");

    std::vector<CObjCHAR*> found;
    user.AI_CollectOBJs((int)fRadius, found);
    const float fMyZ = user.Nav_Z();
    struct Row {
        float d, dz;
        bool in;
        CObjCHAR* p;
    };
    std::vector<Row> rows;
    for (CObjCHAR* p: found) {
        if (p == &user || !p->IsA(OBJ_MOB))
            continue;
        const float dx = p->m_PosCUR.x - user.m_PosCUR.x, dy = p->m_PosCUR.y - user.m_PosCUR.y;
        const float d = sqrtf(dx * dx + dy * dy);
        const float tz = p->Nav_Z();
        rows.push_back({d, (NO_Z == tz || NO_Z == fMyZ) ? 0.f : tz - fMyZ, InVerticalReach(fMyZ, tz, d, fRadius), p});
    }
    std::sort(rows.begin(), rows.end(), [](const Row& a, const Row& b) { return a.d < b.d; });
    const int iIn = (int)std::count_if(rows.begin(), rows.end(), [](const Row& r) { return r.in; });
    user.send_server_whisper(fmt::format("An area of {:.0f} m around you ({}): {} monsters inside it on the map, {} would be hit, {} left out by height.",
        fRadius / 100.f, rule, rows.size(), iIn, (int)rows.size() - iIn));
    for (size_t i = 0; i < rows.size() && i < 8; ++i) {
        const Row& r = rows[i];
        user.send_server_whisper(fmt::format("  {} {:.1f} m away, {:.1f} m {}: {}", r.p->Get_NAME(), r.d / 100.f,
            fabsf(r.dz) / 100.f, r.dz >= 0 ? "above you" : "below you", r.in ? "HIT" : "left out"));
    }
}

// The nearest regen point's spawn square, sampled with the spawn rules (Phases 3 and 4):
// how many random spots each rule would send back for another draw.
void
cmd_spawns(classUSER& user) {
    CZoneTHREAD* pZone = user.GetZONE();
    Grid* pGrid = pZone ? pZone->NavGrid() : nullptr;
    CRegenPOINT* pRegen = pZone ? pZone->GetRegenPOINT(pZone->GetNearstRegenPOINT(user.m_PosCUR)) : nullptr;
    if (!pGrid || !pRegen) {
        user.send_server_whisper("No walk grid or no regen point here.");
        return;
    }
    const float fAnchor = pGrid->AnchorZ(pRegen->m_fXPos, pRegen->m_fYPos);
    if (NO_Z == fAnchor) {
        user.send_server_whisper("This regen point has no baked floor (re-run scripts/nav-bake.py).");
        return;
    }
    if (pRegen->m_iRange <= 0) {
        user.send_server_whisper("This regen point spawns on its centre only.");
        return;
    }
    const int N = 200;
    int iOff = 0, iWall = 0, iRoof = 0;
    for (int i = 0; i < N; ++i) {
        // drawn as RegenCharacter draws them
        const float x = pRegen->m_fXPos - pRegen->m_iRange + RANDOM(pRegen->m_iRange * 2);
        const float y = pRegen->m_fYPos - pRegen->m_iRange + RANDOM(pRegen->m_iRange * 2);
        Span s;
        if (!pGrid->NearestSpan(x, y, fAnchor, 1.0e6f, s, SPAN_WALK | SPAN_REACHED)) {
            ++iOff;
        } else if (!pGrid->LineWalk(pRegen->m_fXPos, pRegen->m_fYPos, fAnchor, x, y)) {
            ++iWall;
        } else {
            Span any;
            const float fTop = pGrid->VisualTopZ(x, y);
            if (pGrid->NearestSpan(x, y, fAnchor, 1.0e6f, any) && NO_Z != fTop && fTop - any.z > 300.f)
                ++iRoof;
        }
    }
    user.send_server_whisper(fmt::format("Nearest regen point ({:.0f}, {:.0f}) m, spawn square +/-{:.0f} m: of {} random spots, "
                                         "{} in rock or off the walkable ground, {} behind a wall, {} under a roof.",
        pRegen->m_fXPos / 100.f, pRegen->m_fYPos / 100.f, pRegen->m_iRange / 100.f, N, iOff, iWall, iRoof));
    user.send_server_whisper(fmt::format("Those are drawn again now (reach {}, roofs {}); before Phase 3/4 they spawned there.",
        settings().spawn_reach.load(), settings().spawn_roofs.load()));
}

// Whether your target could walk straight to you on the grid, or where a wall stops it.
void
cmd_walk(classUSER& user) {
    CZoneTHREAD* pZone = user.GetZONE();
    Grid* pGrid = pZone ? pZone->NavGrid() : nullptr;
    CObjCHAR* pTarget = (CObjCHAR*)user.Get_TARGET(true);
    if (!pGrid || !pTarget || pTarget == &user || pTarget->GetZONE() != pZone) {
        user.send_server_whisper("Target a monster first (click it), then /nav walk.");
        return;
    }
    float fLX, fLY;
    const bool bOpen = pGrid->LineWalk(pTarget->m_PosCUR.x, pTarget->m_PosCUR.y, pTarget->Nav_WalkZ(),
        user.m_PosCUR.x, user.m_PosCUR.y, &fLX, &fLY);
    const float dx = user.m_PosCUR.x - pTarget->m_PosCUR.x, dy = user.m_PosCUR.y - pTarget->m_PosCUR.y;
    const float fx = fLX - pTarget->m_PosCUR.x, fy = fLY - pTarget->m_PosCUR.y;
    if (bOpen) {
        user.send_server_whisper(fmt::format("{} could walk straight to you ({:.1f} m): nothing in the way.",
            pTarget->Get_NAME(), sqrtf(dx * dx + dy * dy) / 100.f));
    } else {
        user.send_server_whisper(fmt::format("{} could not walk straight to you ({:.1f} m): blocked after {:.1f} m, at ({:.1f}, {:.1f}).",
            pTarget->Get_NAME(), sqrtf(dx * dx + dy * dy) / 100.f, sqrtf(fx * fx + fy * fy) / 100.f, fLX / 100.f, fLY / 100.f));
    }
}

void
cmd_set(classUSER& user, const std::vector<std::string>& args) {
    Settings& s = settings();
    const struct {
        const char* name;
        std::atomic<int>* value;
        const char* help;
    } knobs[] = {
        {"aoe", &s.aoe_vertical, "0 off (2D), 1 band, 2 sphere, 3 cylinder"},
        {"base", &s.aoe_band_base_cm, "band height at the centre, cm"},
        {"slope", &s.aoe_band_slope_pct, "band growth, % of the horizontal distance"},
        {"aggro", &s.mob_layer_aggro, "monster scans use the rule: 0 / 1"},
        {"roofs", &s.spawn_roofs, "re-roll spawns drawn on a roof: 0 / 1"},
        {"walls", &s.ai_walls, "idle walks (wander, flee, leash, follow) avoid walls: 0 / 1"},
        {"reach", &s.spawn_reach, "re-roll spawns behind walls or off the ground: 0 / 1"},
    };
    if (args.size() >= 4) {
        for (const auto& k: knobs) {
            if (args[2] == k.name) {
                k.value->store(std::atoi(args[3].c_str()), std::memory_order_relaxed);
                user.send_server_whisper(fmt::format("nav: {} = {} (whole server, until restart or reloadconfig)",
                    k.name, k.value->load()));
                return;
            }
        }
    }
    for (const auto& k: knobs) {
        user.send_server_whisper(fmt::format("nav set {} {}  ({})", k.name, k.value->load(), k.help));
    }
}

} // namespace

void
OnUserMove(classUSER& user) {
    if (0 == g_iRecording.load(std::memory_order_relaxed)) {
        return;
    }

    std::lock_guard<std::mutex> lock(g_TrailMutex);
    auto it = g_Trails.find(user.Get_NAME());
    if (it != g_Trails.end() && it->second.bRecording) {
        add_corner(it->second, user.m_PosCUR);
    }
}

bool
Command(classUSER& user, const char* szUsage, const std::vector<std::string>& args) {
    const std::string action = args.size() >= 2 ? args[1] : "";

    if (action == "rec") {
        std::lock_guard<std::mutex> lock(g_TrailMutex);
        Trail& trail = g_Trails[user.Get_NAME()];
        stop_recording(trail);
        trail.points.clear();
        trail.bRecording = true;
        g_iRecording.fetch_add(1, std::memory_order_relaxed);
        add_corner(trail, user.m_PosCUR);
        user.send_server_whisper(
            "Recording: walk the route (each click is a corner), then /nav trail near a monster.");
        return true;
    }

    if (action == "mark") {
        std::lock_guard<std::mutex> lock(g_TrailMutex);
        Trail& trail = g_Trails[user.Get_NAME()];
        add_corner(trail, user.m_PosCUR);
        user.send_server_whisper(fmt::format("Trail: {} corners.", trail.points.size()));
        return true;
    }

    if (action == "trail") {
        return cmd_trail(user, args);
    }

    if (action.empty() || action == "here") {
        cmd_here(user);
        return true;
    }

    if (action == "spawns") {
        cmd_spawns(user);
        return true;
    }

    if (action == "walk") {
        cmd_walk(user);
        return true;
    }

    if (action == "aoe") {
        cmd_aoe(user, args);
        return true;
    }

    if (action == "set") {
        cmd_set(user, args);
        return true;
    }

    if (action == "stats") {
        CZoneTHREAD* pZone = user.GetZONE();
        if (pZone) {
            const std::string text = pZone->m_NavMeter.LastWindow();
            user.send_server_whisper(text.empty() ? "This zone has no full minute yet." : text);
        }
        user.send_server_whisper(ServerSummaryText());
        return true;
    }

    user.send_server_whisper(szUsage);
    return false;
}

} // namespace Nav::Probe
