#pragma once

#include <atomic>
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
};

Settings& settings();

/// Read the [nav] table of server.toml; a missing key keeps its value.
void LoadSettings(const std::string& tomlPath);

/// Whether a target dz away vertically and d away horizontally is inside an area of the
/// given radius under the current rule. A height that is not known (NO_Z) never excludes.
bool InVerticalReach(float centreZ, float targetZ, float horizontal, float radius);

} // namespace Nav
