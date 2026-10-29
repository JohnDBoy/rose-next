#include "stdafx.h"

#include "nav/nav_stats.h"

#include "GS_ListUSER.h"
#include "GS_ThreadZONE.h"
#include "ZoneLIST.h"

#include <algorithm>
#include <psapi.h>

#pragma comment(lib, "psapi.lib")

namespace Nav {

namespace {

constexpr DWORD WINDOW_MS = 60 * 1000;
// The server line comes after the first minute, then every five.
constexpr DWORD SUMMARY_FIRST_MS = 60 * 1000;
constexpr DWORD SUMMARY_EVERY_MS = 5 * 60 * 1000;
// A zone with nobody in it still logs when its object work gets this slow.
constexpr float LOG_P99_MS = 30.f;

double
qpc_ms(const LARGE_INTEGER& from, const LARGE_INTEGER& to) {
    static LARGE_INTEGER s_liFreq = [] {
        LARGE_INTEGER f;
        ::QueryPerformanceFrequency(&f);
        return f;
    }();
    return (double)(to.QuadPart - from.QuadPart) * 1000.0 / (double)s_liFreq.QuadPart;
}

const char*
zone_name(CZoneTHREAD& zone) {
    const char* szName = zone.Get_NAME();
    return szName ? szName : "?";
}

std::atomic<DWORD> g_dwServerStart{0};
std::atomic<size_t> g_GridBytes{0};
std::atomic<DWORD> g_dwLastSummary{0};

} // namespace

void
AddGridBytes(size_t bytes) {
    g_GridBytes.fetch_add(bytes, std::memory_order_relaxed);
}

void
ZoneMeter::CountPathSearch(int iResult, int iExpansions, double dMS) {
    if (iResult >= 0 && iResult < 6) {
        m_PathResults[iResult].fetch_add(1, std::memory_order_relaxed);
    }
    m_PathExpansions.fetch_add((uint64_t)iExpansions, std::memory_order_relaxed);
    const uint32_t us = (uint32_t)(dMS * 1000.0 + 0.5);
    m_PathMicros.fetch_add(us, std::memory_order_relaxed);
    uint32_t prev = m_PathMaxMicros.load(std::memory_order_relaxed);
    while (us > prev && !m_PathMaxMicros.compare_exchange_weak(prev, us, std::memory_order_relaxed)) {
    }
}

void
ZoneMeter::BeginProc() {
    ::QueryPerformanceCounter(&m_liStart);
}

void
ZoneMeter::EndProc(CZoneTHREAD& zone, int iMobs) {
    LARGE_INTEGER liEnd;
    ::QueryPerformanceCounter(&liEnd);

    m_ProcMS.push_back((float)qpc_ms(m_liStart, liEnd));
    if (m_liLastEnd.QuadPart) {
        m_fMaxPeriodMS = (std::max)(m_fMaxPeriodMS, (float)qpc_ms(m_liLastEnd, liEnd));
    }
    m_liLastEnd = liEnd;
    m_iMobs = iMobs;
    m_iMaxUsers = (std::max)(m_iMaxUsers, zone.Get_UserCNT());

    const DWORD dwNow = ::timeGetTime();
    if (!m_dwWindowStart) {
        m_dwWindowStart = dwNow;
    } else if (dwNow - m_dwWindowStart >= WINDOW_MS) {
        this->Publish(zone);
        m_dwWindowStart = dwNow;
    }

    ServerSummaryTick();
}

void
ZoneMeter::Publish(CZoneTHREAD& zone) {
    const size_t n = m_ProcMS.size();
    double dSum = 0.0;
    for (float f: m_ProcMS) {
        dSum += f;
    }
    // p99 is the tick that 1% of the window was slower than.
    const size_t iP99 = n ? (std::min)(n - 1, (n * 99) / 100) : 0;
    float fP99 = 0.f, fMax = 0.f;
    if (n) {
        std::nth_element(m_ProcMS.begin(), m_ProcMS.begin() + iP99, m_ProcMS.end());
        fP99 = m_ProcMS[iP99];
        fMax = *std::max_element(m_ProcMS.begin(), m_ProcMS.end());
    }

    const uint32_t nRejects = m_MoveRejects.exchange(0, std::memory_order_relaxed);
    const uint32_t nLeash = m_LeashFails.exchange(0, std::memory_order_relaxed);
    const uint32_t nClobbers = m_ScanClobbers.exchange(0, std::memory_order_relaxed);
    const uint32_t nZHints = m_ZHints.exchange(0, std::memory_order_relaxed);
    const uint32_t nZMisses = m_ZMisses.exchange(0, std::memory_order_relaxed);
    const uint32_t nVert = m_VerticalMisses.exchange(0, std::memory_order_relaxed);
    const uint32_t nAggro = m_AggroMisses.exchange(0, std::memory_order_relaxed);
    const uint32_t nReroll = m_SpawnRerolls.exchange(0, std::memory_order_relaxed);
    const uint32_t nFallback = m_SpawnFallbacks.exchange(0, std::memory_order_relaxed);
    const uint32_t nStraight = m_StraightFallbacks.exchange(0, std::memory_order_relaxed);
    uint32_t nPath[6];
    uint32_t nSearches = 0;
    for (int i = 0; i < 6; ++i) {
        nPath[i] = m_PathResults[i].exchange(0, std::memory_order_relaxed);
        nSearches += nPath[i];
    }
    const uint32_t nDeferred = m_PathDeferred.exchange(0, std::memory_order_relaxed);
    const uint32_t nStarted = m_PathStarted.exchange(0, std::memory_order_relaxed);
    const uint32_t nLineClear = m_PathLineClear.exchange(0, std::memory_order_relaxed);
    const uint32_t nReplans = m_PathReplans.exchange(0, std::memory_order_relaxed);
    const uint64_t nExp = m_PathExpansions.exchange(0, std::memory_order_relaxed);
    const uint64_t nMicros = m_PathMicros.exchange(0, std::memory_order_relaxed);
    const uint32_t nMaxMicros = m_PathMaxMicros.exchange(0, std::memory_order_relaxed);

    // PathResult order: found, partial, failed, unreachable, no floor (deferred is counted apart)
    const std::string pathText = nSearches || nDeferred
        ? fmt::format("; paths: {} searches (found {}, partial {}, failed {}, unreachable {}, no floor {}), "
                      "deferred {}, {} cells, nav {:.3f} ms a tick (search max {:.2f} ms); {} walks started, "
                      "{} chases back to straight, {} re-planned",
              nSearches, nPath[0], nPath[1], nPath[2], nPath[3], nPath[4], nDeferred, nExp,
              n ? (double)nMicros / 1000.0 / n : 0.0, nMaxMicros / 1000.0, nStarted, nLineClear, nReplans)
        : std::string();

    const std::string text = fmt::format(
        "zone {} {}: object work avg {:.2f} ms, p99 {:.2f} ms, max {:.2f} ms over {} ticks; "
        "longest tick {:.0f} ms; {} monsters, {} objects, up to {} players; "
        "AI moves refused {} (leash {}), AoE casts a victim's AI scanned in {}, "
        "client heights off the walk grid {} of {}; out of vertical reach: {} in areas, {} in "
        "monster scans; spawns re-rolled (roof, wall or off the ground) {}, at the centre {}; "
        "blocked leash/follow walked straight {}",
        zone.Get_ZoneNO(),
        zone_name(zone),
        n ? dSum / n : 0.0,
        fP99,
        fMax,
        n,
        m_fMaxPeriodMS,
        m_iMobs,
        zone.GetGameObjCNT(),
        m_iMaxUsers,
        nRejects,
        nLeash,
        nClobbers,
        nZMisses,
        nZHints,
        nVert,
        nAggro,
        nReroll,
        nFallback,
        nStraight) + pathText;

    if (m_iMaxUsers > 0 || fP99 >= LOG_P99_MS) {
        LOG_INFO("nav: {}", text);
    }

    {
        std::lock_guard<std::mutex> lock(m_TextMutex);
        m_LastText = text;
    }
    m_LastP99x10.store((uint32_t)(fP99 * 10.f + 0.5f), std::memory_order_relaxed);
    m_LastMobs.store((uint32_t)m_iMobs, std::memory_order_relaxed);

    m_ProcMS.clear();
    m_fMaxPeriodMS = 0.f;
    m_iMaxUsers = 0;
}

std::string
ZoneMeter::LastWindow() {
    std::lock_guard<std::mutex> lock(m_TextMutex);
    return m_LastText;
}

std::string
ServerSummaryText() {
    int iZones = 0;
    uint32_t nMobs = 0, nWorstP99x10 = 0;
    int iWorstZone = 0;
    const char* szWorst = "-";
    for (short nZ = 1; nZ < g_pZoneLIST->GetZoneCNT(); ++nZ) {
        if (!g_pZoneLIST->IsValidZONE(nZ)) {
            continue;
        }
        CZoneTHREAD* pZone = g_pZoneLIST->GetZONE(nZ);
        if (!pZone) {
            continue;
        }
        ++iZones;
        nMobs += pZone->m_NavMeter.m_LastMobs.load(std::memory_order_relaxed);
        const uint32_t nP99 = pZone->m_NavMeter.m_LastP99x10.load(std::memory_order_relaxed);
        if (nP99 >= nWorstP99x10) {
            nWorstP99x10 = nP99;
            iWorstZone = nZ;
            szWorst = zone_name(*pZone);
        }
    }

    PROCESS_MEMORY_COUNTERS_EX pmc = {};
    pmc.cb = sizeof(pmc);
    ::GetProcessMemoryInfo(::GetCurrentProcess(), (PROCESS_MEMORY_COUNTERS*)&pmc, sizeof(pmc));

    // Address space is the real limit: the server is not large-address-aware,
    // so it has 2 GB of it however much RAM the machine has.
    MEMORYSTATUSEX ms = {};
    ms.dwLength = sizeof(ms);
    ::GlobalMemoryStatusEx(&ms);
    const unsigned long long ullUsedVA = ms.ullTotalVirtual - ms.ullAvailVirtual;

    return fmt::format(
        "{} zones, {} monsters, {} players; worst object-work p99 {:.1f} ms (zone {} {}); "
        "walk grids {:.1f} MB; private {} MB, address space used {} of {} MB",
        iZones,
        nMobs,
        g_pUserLIST ? g_pUserLIST->Get_AccountCNT() : 0,
        nWorstP99x10 / 10.f,
        iWorstZone,
        szWorst,
        g_GridBytes.load(std::memory_order_relaxed) / (1024.0 * 1024.0),
        pmc.PrivateUsage / (1024 * 1024),
        ullUsedVA / (1024 * 1024),
        ms.ullTotalVirtual / (1024 * 1024));
}

void
ServerSummaryTick() {
    const DWORD dwNow = ::timeGetTime();
    DWORD dwStart = g_dwServerStart.load(std::memory_order_relaxed);
    if (!dwStart) {
        g_dwServerStart.compare_exchange_strong(dwStart, dwNow);
        return;
    }

    DWORD dwLast = g_dwLastSummary.load(std::memory_order_relaxed);
    const DWORD dwDue = dwLast ? dwLast + SUMMARY_EVERY_MS : dwStart + SUMMARY_FIRST_MS;
    if ((int)(dwNow - dwDue) < 0) {
        return;
    }
    // One zone thread wins the slot and logs; the others see the new time.
    if (!g_dwLastSummary.compare_exchange_strong(dwLast, dwNow)) {
        return;
    }

    LOG_INFO("nav: server: {}", ServerSummaryText());
}

} // namespace Nav
