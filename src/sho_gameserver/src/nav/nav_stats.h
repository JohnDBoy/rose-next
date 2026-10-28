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
    void CountScanClobber() { m_ScanClobbers.fetch_add(1, std::memory_order_relaxed); }

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

    std::mutex m_TextMutex;
    std::string m_LastText;
};

/// Server-wide line: zones, monsters, worst p99, process memory. Any zone thread
/// may call it; one of them logs every few minutes.
void ServerSummaryTick();
std::string ServerSummaryText();

} // namespace Nav
