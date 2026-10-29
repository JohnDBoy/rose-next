#include "stdafx.h"

#include "nav/nav_settings.h"

#include "nav/nav_grid.h"
#include "rose/common/common_interface.h"

#include <cctype>
#include <cmath>
#include <vector>

namespace Nav {

namespace {
// A cylinder never gets shorter than this: a 2 m radius would otherwise miss a target on a
// small step (doc/pathfinding-and-z-plan.md, the AoE table).
constexpr float CYLINDER_MIN_CM = 400.f;
} // namespace

Settings::Settings() {
    for (auto& w: path_zone_bits) {
        w.store(0, std::memory_order_relaxed);
    }
}

Settings&
settings() {
    static Settings s_Settings;
    return s_Settings;
}

bool
PathingIn(int iZoneNo) {
    const Settings& s = settings();
    if (!s.pathing.load(std::memory_order_relaxed)) {
        return false;
    }
    if (s.path_all_zones.load(std::memory_order_relaxed)) {
        return true;
    }
    if (iZoneNo < 0 || iZoneNo >= 512) {
        return false;
    }
    return (s.path_zone_bits[iZoneNo >> 5].load(std::memory_order_relaxed) >> (iZoneNo & 31)) & 1;
}

bool
SetPathZones(const std::string& text) {
    std::string t;
    for (char c: text) {
        t += (char)tolower((unsigned char)c);
    }
    Settings& s = settings();
    if (t.find("all") != std::string::npos) {
        s.path_all_zones.store(1, std::memory_order_relaxed);
        return true;
    }
    uint32_t bits[16] = {};
    bool bNone = t.find("none") != std::string::npos;
    int v = -1;
    for (size_t i = 0; i <= t.size(); ++i) {
        const char c = i < t.size() ? t[i] : ' ';
        if (isdigit((unsigned char)c)) {
            v = (v < 0 ? 0 : v * 10) + (c - '0');
            if (v >= 512) {
                return false;
            }
        } else if (c == ',' || c == ' ' || c == ';' || c == '\t') {
            if (v >= 0) {
                bits[v >> 5] |= 1u << (v & 31);
                v = -1;
            }
        } else if (!bNone) {
            return false;
        }
    }
    for (int i = 0; i < 16; ++i) {
        s.path_zone_bits[i].store(bits[i], std::memory_order_relaxed);
    }
    s.path_all_zones.store(0, std::memory_order_relaxed);
    return true;
}

std::string
PathZonesText() {
    const Settings& s = settings();
    if (s.path_all_zones.load(std::memory_order_relaxed)) {
        return "all";
    }
    std::string out;
    for (int z = 0; z < 512; ++z) {
        if ((s.path_zone_bits[z >> 5].load(std::memory_order_relaxed) >> (z & 31)) & 1) {
            out += (out.empty() ? "" : ",") + std::to_string(z);
        }
    }
    return out.empty() ? "none" : out;
}

void
LoadSettings(const std::string& tomlPath) {
    Toml* t = toml_load(tomlPath.c_str());
    if (!t) {
        return;
    }
    Settings& s = settings();
    const struct {
        const char* key;
        std::atomic<int>* value;
    } keys[] = {
        {"aoe_vertical", &s.aoe_vertical},
        {"aoe_band_base_cm", &s.aoe_band_base_cm},
        {"aoe_band_slope_pct", &s.aoe_band_slope_pct},
        {"mob_layer_aggro", &s.mob_layer_aggro},
        {"spawn_roofs", &s.spawn_roofs},
        {"ai_walls", &s.ai_walls},
        {"spawn_reach", &s.spawn_reach},
        {"pathing", &s.pathing},
        {"path_expansions", &s.path_expansions},
        {"path_tick_searches", &s.path_tick_searches},
        {"path_tick_expansions", &s.path_tick_expansions},
        {"path_tick_us", &s.path_tick_us},
        {"path_lead_ms", &s.path_lead_ms},
    };
    for (const auto& k: keys) {
        int64_t v = 0;
        if (toml_get_int(t, "nav", k.key, &v)) {
            k.value->store((int)v, std::memory_order_relaxed);
        }
    }
    // Free the string only once toml_get_str has filled it: FfiString's Rust drop hands its
    // pointer to CString::from_raw unchecked, so freeing an unset one (a missing key) crashes
    // the server. ServerConfig::get_str leaks it on that path for the same reason.
    FfiString* str = ffi_string_new();
    if (toml_get_str(t, "nav", "path_zones", str)) {
        const std::string zones(str->chars, str->len);
        ffi_string_free(str);
        if (!SetPathZones(zones)) {
            LOG_WARN("nav: path_zones \"{}\" does not parse (\"all\", \"none\" or zone numbers); kept {}",
                zones, PathZonesText());
        }
    }
    toml_free(t);
    LOG_INFO("nav: aoe_vertical {} (band {} cm + {}%), mob_layer_aggro {}, spawn_roofs {}, ai_walls {}, "
             "spawn_reach {}, pathing {} in zones {} ({} cells a search, {} searches / {} cells / {} us a tick)",
        s.aoe_vertical.load(), s.aoe_band_base_cm.load(), s.aoe_band_slope_pct.load(),
        s.mob_layer_aggro.load(), s.spawn_roofs.load(), s.ai_walls.load(), s.spawn_reach.load(),
        s.pathing.load(), PathZonesText(), s.path_expansions.load(), s.path_tick_searches.load(),
        s.path_tick_expansions.load(), s.path_tick_us.load());
}

bool
InVerticalReach(float centreZ, float targetZ, float horizontal, float radius) {
    if (NO_Z == centreZ || NO_Z == targetZ) {
        return true;
    }
    const float dz = fabsf(targetZ - centreZ);
    const Settings& s = settings();
    switch (s.aoe_vertical.load(std::memory_order_relaxed)) {
        case AOE_BAND:
            return dz <= s.aoe_band_base_cm.load(std::memory_order_relaxed)
                + s.aoe_band_slope_pct.load(std::memory_order_relaxed) * 0.01f * horizontal;
        case AOE_SPHERE:
            return horizontal * horizontal + dz * dz <= radius * radius;
        case AOE_CYLINDER:
            return dz <= (radius > CYLINDER_MIN_CM ? radius : CYLINDER_MIN_CM);
        default:
            return true;
    }
}

} // namespace Nav
