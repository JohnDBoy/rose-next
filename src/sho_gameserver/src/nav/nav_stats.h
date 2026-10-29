#pragma once

#include <atomic>
#include <mutex>
#include <string>
#include <vector>

class CZoneTHREAD;

namespace Nav {

/// Per-zone tick meter: how long each tick's object work takes, plus counters
/// for the movement and scan problems the pathfinding plan has to fix
/// (doc/pathfinding-and-z-plan.md, Phase 0). The zone thread feeds it; the
/// published last-minute text is read by /nav stats from any thread.
///
/// Logs one line per zone per minute while the zone has players (or when its
/// p99 is high), and a server line every few minutes with the population and
/// the process memory.
class ZoneMeter {
public:
    void BeginProc();
    void EndProc(CZoneTHREAD& zone, int iMobs);

    void CountMoveReject() { m_MoveRejects.fetch_add(1, std::memory_order_relaxed); }
    void CountLeashFail() { m_LeashFails.fetch_add(1, std::memory_order_relaxed); }
    // An AoE cast during which a victim's AI ran a scan of its own. That broke the
    // AoE until it collected its targets first (Phase 1); now it only counts.
    void CountScanClobber() { m_ScanClobbers.fetch_add(1, std::memory_order_relaxed); }
    // Characters the vertical rule kept out of an area effect, or out of a monster's scan.
    void CountVerticalMiss() { m_VerticalMisses.fetch_add(1, std::memory_order_relaxed); }
    void CountAggroMiss() { m_AggroMisses.fetch_add(1, std::memory_order_relaxed); }
    // A regen spawn drawn again because the client would draw it on a roof, and one that
    // fell back to its point's centre.
    void CountSpawnReroll() { m_SpawnRerolls.fetch_add(1, std::memory_order_relaxed); }
    void CountSpawnFallback() { m_SpawnFallbacks.fetch_add(1, std::memory_order_relaxed); }
    // A leash or a summon follow whose line was blocked, walked straight anyway (until A*).
    void CountStraightFallback() { m_StraightFallbacks.fetch_add(1, std::memory_order_relaxed); }
    // Path searches (Phase 5): each one's outcome (PathResult), cells and time; a search the
    // tick's budget refused; a character that began walking a path; a chase that went back
    // to running straight because its line cleared; a chase path planned again because its
    // target moved away from the goal.
    void CountPathSearch(int iResult, int iExpansions, double dMS);
    void CountPathDeferred() { m_PathDeferred.fetch_add(1, std::memory_order_relaxed); }
    void CountPathStarted() { m_PathStarted.fetch_add(1, std::memory_order_relaxed); }
    void CountPathLineClear() { m_PathLineClear.fetch_add(1, std::memory_order_relaxed); }
    void CountPathReplan() { m_PathReplans.fetch_add(1, std::memory_order_relaxed); }
    // A client height report, and whether it was more than 1 m from every floor.
    void CountZHint(bool bMiss) {
        m_ZHints.fetch_add(1, std::memory_order_relaxed);
        if (bMiss)
            m_ZMisses.fetch_add(1, std::memory_order_relaxed);
    }

    /// The last finished minute, as text (empty before the first one).
    std::string LastWindow();

    // Published at the end of each window, for the server summary.
    std::atomic<uint32_t> m_LastP99x10{0}; ///< proc p99, tenths of a ms
    std::atomic<uint32_t> m_LastMobs{0};

private:
    void Publish(CZoneTHREAD& zone);

    LARGE_INTEGER m_liStart = {};
    LARGE_INTEGER m_liLastEnd = {};
    DWORD m_dwWindowStart = 0;
    std::vector<float> m_ProcMS; ///< every tick of the current window
    float m_fMaxPeriodMS = 0.f; ///< longest gap between two ticks
    int m_iMobs = 0;
    int m_iMaxUsers = 0;

    std::atomic<uint32_t> m_MoveRejects{0};
    std::atomic<uint32_t> m_LeashFails{0};
    std::atomic<uint32_t> m_ScanClobbers{0};
    std::atomic<uint32_t> m_ZHints{0};
    std::atomic<uint32_t> m_VerticalMisses{0};
    std::atomic<uint32_t> m_AggroMisses{0};
    std::atomic<uint32_t> m_SpawnRerolls{0};
    std::atomic<uint32_t> m_SpawnFallbacks{0};
    std::atomic<uint32_t> m_StraightFallbacks{0};
    std::atomic<uint32_t> m_ZMisses{0};
    std::atomic<uint32_t> m_PathResults[6] = {};
    std::atomic<uint32_t> m_PathDeferred{0};
    std::atomic<uint32_t> m_PathStarted{0};
    std::atomic<uint32_t> m_PathLineClear{0};
    std::atomic<uint32_t> m_PathReplans{0};
    std::atomic<uint64_t> m_PathExpansions{0};
    std::atomic<uint64_t> m_PathMicros{0};
    std::atomic<uint32_t> m_PathMaxMicros{0};

    std::mutex m_TextMutex;
    std::string m_LastText;
};

/// Count a zone's walk grid in the server line (zone load).
void AddGridBytes(size_t bytes);

/// Server-wide line: zones, monsters, worst p99, process memory. Any zone thread
/// may call it; one of them logs every few minutes.
void ServerSummaryTick();
std::string ServerSummaryText();

} // namespace Nav
