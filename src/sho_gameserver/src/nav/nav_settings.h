#pragma once

#include <atomic>
#include <cstdint>
#include <string>

namespace Nav {

/// How AoE and aggro treat height (doc/pathfinding-and-z-plan.md, section 3.4).
enum AoeRule : int {
    AOE_OFF = 0, ///< 2D, as before
    AOE_BAND = 1, ///< |dz| <= base + slope * horizontal distance (the default)
    AOE_SPHERE = 2, ///< horizontal^2 + dz^2 <= radius^2
    AOE_CYLINDER = 3, ///< |dz| <= max(4 m, radius)
};

/// The vertical rules. server.toml [nav] sets them at start and on reloadconfig; /nav set
/// changes them live for the whole server. Read from every zone thread.
struct Settings {
    std::atomic<int> aoe_vertical{AOE_BAND};
    std::atomic<int> aoe_band_base_cm{500};
    std::atomic<int> aoe_band_slope_pct{70};
    std::atomic<int> mob_layer_aggro{1}; ///< monster scans (aggro, help calls) use the rule
    std::atomic<int> spawn_roofs{1}; ///< re-roll a spawn the client would draw on a roof
    std::atomic<int> ai_walls{1}; ///< AI walks (wander, flee, leash, follow) must walk their line
    std::atomic<int> spawn_reach{1}; ///< re-roll a spawn behind a wall or off the walkable ground

    // Pathfinding (Phase 5)
    std::atomic<int> pathing{1}; ///< chases, leashes, summon follow and CTRL+click orders use A*
    std::atomic<int> path_expansions{4000}; ///< cells one search may expand
    std::atomic<int> path_tick_searches{6}; ///< searches a zone tick may run
    std::atomic<int> path_tick_expansions{8000}; ///< cells a zone tick may expand
    std::atomic<int> path_tick_us{3000}; ///< nav time a zone tick may spend (QPC, microseconds)
    std::atomic<int> path_lead_ms{100}; ///< send the next leg this long before a corner
    /// Stage B (Phase 6): monsters, summons and NPCs walk their own floor, which the server
    /// sends (spawn, move and stop packets) and its vertical rule uses. 0: the client draws them
    /// on GetHeightTop and the rule uses that height, as before.
    std::atomic<int> send_z{1};
    /// Phase 7: attacks and targeted skills reach only within the vertical band (the AoE band,
    /// plus 1 m of slack). A player is refused with "another level"; a monster paths to the
    /// target's floor, and gives up after vertical_giveup_ms when it cannot.
    std::atomic<int> vertical_range{1};
    std::atomic<int> vertical_giveup_ms{3000};
    /// Zones whose characters path (path_zones in server.toml: "all", or a list of zone
    /// numbers). One bit per zone number below 512.
    std::atomic<uint32_t> path_zone_bits[16];
    std::atomic<int> path_all_zones{1};

    Settings();
};

/// Whether characters in zone iZoneNo path (pathing on, and the zone in path_zones).
bool PathingIn(int iZoneNo);
/// Set path_zones from text: "all", "none", or zone numbers separated by commas or spaces.
/// False (unchanged) if it does not parse.
bool SetPathZones(const std::string& text);
/// path_zones as text.
std::string PathZonesText();

Settings& settings();

/// Read the [nav] table of server.toml; a missing key keeps its value.
void LoadSettings(const std::string& tomlPath);

/// Whether a target dz away vertically and d away horizontally is inside an area of the
/// given radius under the current rule. A height that is not known (NO_Z) never excludes.
bool InVerticalReach(float centreZ, float targetZ, float horizontal, float radius);

/// Phase 7: whether an attack, a targeted skill or a ground skill's aim at height targetZ, d away
/// horizontally, is within reach of an attacker at attackerZ: the band (aoe_band_base_cm +
/// aoe_band_slope_pct of d, plus 1 m of slack). True with vertical_range off or a height unknown.
bool InAttackBand(float attackerZ, float targetZ, float horizontal);

} // namespace Nav
