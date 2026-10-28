#include "stdafx.h"

#include "nav/nav_probe.h"

#include "nav/nav_agent.h"
#include "nav/nav_stats.h"

#include "GS_ThreadZONE.h"
#include "GS_USER.h"

#include <atomic>
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
