#include "stdafx.h"

#include "nav/nav_settings.h"

#include "nav/nav_grid.h"
#include "rose/common/common_interface.h"

#include <cmath>

namespace Nav {

namespace {
// A cylinder never gets shorter than this: a 2 m radius would otherwise miss a target on a
// small step (doc/pathfinding-and-z-plan.md, the AoE table).
constexpr float CYLINDER_MIN_CM = 400.f;
} // namespace

Settings&
settings() {
    static Settings s_Settings;
    return s_Settings;
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
    };
    for (const auto& k: keys) {
        int64_t v = 0;
        if (toml_get_int(t, "nav", k.key, &v)) {
            k.value->store((int)v, std::memory_order_relaxed);
        }
    }
    toml_free(t);
    LOG_INFO("nav: aoe_vertical {} (band {} cm + {}%), mob_layer_aggro {}, spawn_roofs {}",
        s.aoe_vertical.load(), s.aoe_band_base_cm.load(), s.aoe_band_slope_pct.load(),
        s.mob_layer_aggro.load(), s.spawn_roofs.load());
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
