#pragma once

#include <string>
#include <vector>

class classUSER;

namespace Nav::Probe {

/// The GM's click-move just arrived (Recv_cli_MOUSECMD): while they are
/// recording, the spot it starts from is the next corner of their trail.
void OnUserMove(classUSER& user);

/// /nav: the probe of doc/pathfinding-and-z-plan.md.
///   (nothing) or here            the floors under you and your target, and every height the
///                                server and the client hold
///   rec                          record your move corners from now on
///   mark                         add where you stand as a corner
///   trail [lead_ms] [walk|run] [chase]
///                                the nearest monster (or your target) walks your
///                                corners leg by leg, then stops or chases you;
///                                replays the same trail until the next rec
///   stats                        this zone's last minute and the server line
///   set [name value]             the rules, live (aoe, base, slope, aggro, roofs, walls, reach)
///   aoe [radius m]               which monsters an area centred on you would hit or leave out
///   spawns                       the nearest regen point: random spots in rock, behind walls, on roofs
///   walk                         could your target walk straight to you, or where a wall stops it
bool Command(classUSER& user, const char* szUsage, const std::vector<std::string>& args);

} // namespace Nav::Probe
