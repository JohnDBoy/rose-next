#include "stdafx.h"

#include "FrameProfiler.h"

#include <windows.h>

namespace FrameProfiler {

namespace {

/// Frames averaged before publishing. Long enough to be stable, short enough that the
/// display still tracks a camera turn.
const int kWindowFrames = 30;

LONGLONG s_freq = 0;

LONGLONG s_slot_start[SLOT_COUNT];
double s_slot_accum[SLOT_COUNT];  // summed over the current window
double s_slot_frame[SLOT_COUNT];  // this frame only -- what the spike log reports
bool s_slot_open[SLOT_COUNT];

/// Spike log state. Threshold 0 means the whole feature is inert.
unsigned int s_spike_log_ms = 0;

/// Mirrors zz_manager::FLUSH_KIND_COUNT (terrain, mesh, texture, material, other).
/// Deliberately a local copy rather than a shared constant: the engine's enum is
/// the authority, and getImmediateFlushKind() bounds-checks its argument, so a
/// kind added there goes unreported here instead of reading past the array.
const int kFlushKindCount = 5;

/// Mirrors io_terrain.h's MAP_LUMP_TYPE (LUMP_MAP_MAX = 13), local for the same
/// reason as kFlushKindCount; NoteCellLump bounds-checks against it.
const int kCellLumpCount = 13;

/// Mirrors the engine's zz_render_pass_slot (zz_scene_octree.h), ZZ_RPASS_COUNT = 15.
/// The engine's getters bounds-check, so a pass added there just goes unreported.
const int kRenderPassCount = 15;

/// The held candidate for the current rate-limit window.
///
/// The limiter keeps the **worst** frame of a window, not the first. Keeping the
/// first is the obvious implementation and it is actively misleading: the first
/// capture with this tool reported a 24 ms frame and discarded a >=104 ms one that
/// arrived 250 ms later, so the log's headline number was the *least* interesting
/// frame in the burst. Emission is therefore deferred to the end of the window.
struct SpikeSnapshot {
    double frame_ms;
    double accounted;
    double slot[SLOT_COUNT];
    float avg_ms;
    bool flush_sampled;
    float flush_ms;
    int flush_count;
    int flush_kind[kFlushKindCount];
    float mgr_update_ms;
    float frame_sleep_ms;
    float tex_read_ms;
    float tex_create_ms;
    int tex_count;
    int pkt_count;
    double pkt_worst_ms;
    unsigned short pkt_worst_type;
    int spawn_count;
    double spawn_step[SPAWN_STEP_COUNT];
    double terrain_step[TERRAIN_STEP_COUNT];
    int fx_count;
    double fx_step[FX_STEP_COUNT];
    int ptl_count;
    float ptl_open_ms;
    float ptl_parse_ms;
    float ptl_restore_ms;
    double obj_step[OBJ_STEP_COUNT];
    int obj_proc_count;
    int obj_delete_count;
    double obj_worst_ms;
    int obj_worst_type;
    int obj_worst_char;
    int obj_worst_cmd;
    double cell_step[CELL_STEP_COUNT];
    double cell_lump[kCellLumpCount];
    int lit_parts;
    double lit_step[LIT_STEP_COUNT];
    float rpass_ms[kRenderPassCount];
    int rpass_nodes[kRenderPassCount];
};
SpikeSnapshot s_worst;
bool s_worst_valid = false;
int s_window_spikes = 0;
DWORD s_window_start = 0;

/// Per-frame packet-drain detail: how many packets were handled, and the single
/// worst one. Fed by NotePacket() from CNetwork::Proc.
int s_pkt_count = 0;
double s_pkt_worst_ms = 0.0;
unsigned short s_pkt_worst_type = 0;

/// Per-frame character-spawn detail: how many CreateCHAR calls ran and where
/// their time went. Fed by NoteSpawn/NoteSpawnStep from CObjCHAR::CreateCHAR.
int s_spawn_count = 0;
double s_spawn_step[SPAWN_STEP_COUNT];

/// Per-frame terrain sub-pass detail. Fed from CPatchManager.
double s_terrain_step[TERRAIN_STEP_COUNT];

/// Per-frame effect-construction detail. Fed from CEffect::Create.
int s_fx_count = 0;
double s_fx_step[FX_STEP_COUNT];

/// Per-frame ProcOBJECT detail, and the single most expensive Proc().
double s_obj_step[OBJ_STEP_COUNT];
int s_obj_proc_count = 0;
int s_obj_delete_count = 0;
double s_obj_worst_ms = 0.0;
int s_obj_worst_type = 0;
int s_obj_worst_char = 0;
int s_obj_worst_cmd = 0;

/// Per-frame map-cell load detail. Fed from CMAP::Load / CObjFIXED::SetLightMap.
double s_cell_step[CELL_STEP_COUNT];
double s_cell_lump[kCellLumpCount];
int s_lit_parts = 0;
double s_lit_step[LIT_STEP_COUNT];

/// Engine immediate-flush counters, sampled by CaptureFlushStats() while they are
/// still valid. See the header for why EndFrame() cannot read them itself.
bool s_flush_sampled = false;
float s_flush_ms = 0.0f;
int s_flush_count = 0;
int s_flush_kind[kFlushKindCount];
float s_tex_read_ms = 0.0f;
float s_tex_create_ms = 0.0f;
int s_tex_count = 0;

/// Emitting a line costs a formatted log record and an FFI crossing, which is
/// itself long enough to matter on a frame that is already late. A hitch worth
/// investigating is not a 130 Hz event, so one line per 250 ms is plenty. The
/// window's other spikes are reported as a count, so a burst still states its
/// true size rather than looking like a single event.
const DWORD kSpikeLogWindowMs = 250;

/// Frame dips: a run of slow frames, reported as one line (2026-10-25).
///
/// The spike line answers "what was the worst frame"; it cannot show a run of
/// frames that are each only a little late, which is what a map-cell crossing does
/// with the 5x5 window (~1 s at ~45 fps). The limiter folds those into `others=N`,
/// so the log read as a few 22 ms frames while the player saw the frame rate drop.
/// A dip starts on a frame >= the spike threshold and ends after kDipGapMs with
/// none; it is logged only with at least kDipMinSlowFrames slow frames (a lone one
/// is already a spike line). Fast frames inside the run count towards its length
/// and frame total; the trailing gap that closes it does not.
const DWORD kDipGapMs = 300;
const int kDipMinSlowFrames = 4;

struct DipAccum {
    int frames;
    int slow;
    double sum_ms;
    double max_ms;
    double slot[SLOT_COUNT];
    double terrain_step[TERRAIN_STEP_COUNT];
    double flush_ms;
    int flush_terrain;
    double oter_ms;
    double bter_ms;
    double oter_n;
    double bter_n;
    int mapload_frames;
    int crossing_frames;

    void Clear() { memset(this, 0, sizeof(*this)); }
    void Add(const DipAccum& o) {
        frames += o.frames;
        slow += o.slow;
        sum_ms += o.sum_ms;
        if (o.max_ms > max_ms)
            max_ms = o.max_ms;
        for (int i = 0; i < SLOT_COUNT; ++i)
            slot[i] += o.slot[i];
        for (int i = 0; i < TERRAIN_STEP_COUNT; ++i)
            terrain_step[i] += o.terrain_step[i];
        flush_ms += o.flush_ms;
        flush_terrain += o.flush_terrain;
        oter_ms += o.oter_ms;
        bter_ms += o.bter_ms;
        oter_n += o.oter_n;
        bter_n += o.bter_n;
        mapload_frames += o.mapload_frames;
        crossing_frames += o.crossing_frames;
    }
};
DipAccum s_dip;  // the run so far, up to its last slow frame
DipAccum s_dip_tail; // fast frames since then: folded in only if another slow one comes
bool s_dip_active = false;
DWORD s_dip_start = 0;
DWORD s_dip_last_slow = 0;

LONGLONG s_frame_start = 0;
double s_frame_accum = 0.0;
double s_frame_worst = 0.0;
int s_frames = 0;

float s_published[SLOT_COUNT];
float s_published_total = 0.0f;
float s_published_max = 0.0f;
float s_published_accounted = 0.0f;

inline LONGLONG Now() {
    LARGE_INTEGER t;
    ::QueryPerformanceCounter(&t);
    return t.QuadPart;
}

inline double ToMs(LONGLONG ticks) {
    if (s_freq == 0)
        return 0.0;
    return (double)ticks * 1000.0 / (double)s_freq;
}

///
/// One line per hitch, carrying that frame's own phase split.
///
/// Read it in three steps:
///
///   1. Which phase is large? That is the answer, and the rest is detail.
///        netin   - window messages, packet drain, input. Split further by the
///                  netin[...] group: msg = the Win32 pump, gdat = g_GameDATA.Update,
///                  pkt = g_pNet->Proc draining the queue (packet handlers run
///                  synchronously in here, so a zone change is charged to it),
///                  inp = ProcInput.
///        logic   - client game logic; split further by the logic[...] group.
///        scnupd  - engine scene update: transforms, culling, skeletal animation.
///                  Scales with visible object count; no rendering change touches it.
///        shadow  - beginScene(), which runs the whole shadow-map pass, and is also
///                  where much of the immediate resource flush happens -- so check
///                  flush= before blaming the shadow pass itself.
///        render  - draw submission. High means CPU-bound on draw calls, unless
///                  flush= accounts for it: flushes land here too.
///        present - endScene() + swapBuffers(). This is where waiting for the GPU
///                  surfaces, because D3D9 buffers commands. With VSYNC=1 it is also
///                  where the frame-rate cap is paid, so it is expected to be large
///                  and is only interesting when a *spike* lands in it.
///        oth     - inside the frame but outside every bracket. Large in states other
///                  than CGameStateMain (nothing fills slots there), which is why
///                  zone-load frames report almost everything in oth. In-game it is a
///                  real finding: work no bracket covers.
///
///   2. Is flush= large? Then it is the streaming path, already covered by
///      [VIDEO] STREAM_SPIKE_LOG_MS and tuned with TERRAIN_INSERTS_PER_FRAME /
///      LOAD_BUDGET_US. It is a whole-frame total spread across scnupd, shadow and
///      render, so it says streaming was involved without saying which phase carried
///      it -- and it can legitimately exceed any single phase. `flush=unsampled`
///      means the frame never reached the sample point (lost focus, or the scene did
///      not begin) -- not that flushing was free.
///
///   3. Compare against avg=, the last published window mean. A 40 ms frame against
///      an 8 ms average is a hitch; against a 35 ms average it is just a slow scene,
///      and the fix is throughput, not spike-hunting. It reads 0.0 until the first
///      30-frame window has completed, which only affects the opening frames.
///
/// `others=N` is how many further frames crossed the threshold inside the same 250 ms
/// window. This line is the worst of them, not the first -- see SpikeSnapshot.
///
/// Zone-in and the first frames after a warp are legitimately enormous. Expect a
/// cluster there and judge steady-state play instead.
///
void EmitSpike(const SpikeSnapshot& s, int others) {
    LOG_INFO("Frame spike: {:.1f} ms (avg {:.1f}) | "
             "netin={:.1f} logic={:.1f} scnupd={:.1f} shadow={:.1f} render={:.1f} "
             "ui={:.1f} present={:.1f} oth={:.1f} | "
             "netin[msg={:.1f} gdat={:.1f} pkt={:.1f} inp={:.1f}] | "
             "pkt[n={} worst=0x{:04x}/{:.1f}ms] | "
             "spawn[n={} skel={:.1f} mot={:.1f} load={:.1f} parts={:.1f} "
             "bone={:.1f} rest={:.1f}] | "
             "logic[obj={:.1f} terr={:.1f} fx={:.1f} uiupd={:.1f}] | "
             "terr[cull={:.1f} ins={:.1f} prox={:.1f} type={:.1f} del={:.1f} "
             "mapload={:.1f} addmap={:.1f} reorg={:.1f}] | "
             "present[end={:.1f} swap={:.1f} mgr={:.1f} slp={:.1f}] | "
             "flush={} | tex[n={} read={:.1f} create={:.1f}] | "
             "fx[n={} roots={:.1f} emitters={:.1f} (exists={:.1f} ptl={:.1f}) mesh={:.1f}] | "
             "ptl[n={} open={:.1f} parse={:.1f} restore={:.1f}] | "
             "obj[mgr={:.1f} proc={:.1f}/{} del={:.1f}/{} worst={:.1f}ms type={} char={} cmd={}] | "
             "cell[him={:.1f} til={:.1f} ifo={:.1f} lit={:.1f} quad={:.1f}] | "
             "ifo[obj={:.1f} cnst={:.1f} eff={:.1f} snd={:.1f} morph={:.1f} water={:.1f} "
             "evt={:.1f} other={:.1f}] | "
             "lit[n={} addmat={:.1f} build={:.1f} lmap={:.1f} bind={:.1f}] | "
             "rpass[clear={:.1f} view={:.1f} (sky={:.1f} oter={:.1f}/{} bter={:.1f}/{} "
             "rter={:.1f}/{} ovl={:.1f} opq={:.1f}/{} trn={:.1f}/{} glow={:.1f}/{} "
             "ocean={:.1f}/{} part={:.1f}/{} [lock={:.1f}/{} discard={:.1f}/{}]) post={:.1f}] | "
             "others={}",
        s.frame_ms,
        s.avg_ms,
        s.slot[SLOT_NETINPUT],
        s.slot[SLOT_LOGIC],
        s.slot[SLOT_SCENE_UPDATE],
        s.slot[SLOT_SHADOW],
        s.slot[SLOT_RENDER],
        s.slot[SLOT_UI],
        s.slot[SLOT_PRESENT],
        s.frame_ms - s.accounted,
        s.slot[SLOT_NETIN_MSG],
        s.slot[SLOT_NETIN_GAMEDATA],
        s.slot[SLOT_NETIN_PACKET],
        s.slot[SLOT_NETIN_INPUT],
        s.pkt_count,
        s.pkt_worst_type,
        s.pkt_worst_ms,
        s.spawn_count,
        s.spawn_step[SPAWN_SKEL],
        s.spawn_step[SPAWN_MOTION],
        s.spawn_step[SPAWN_LOADMODEL],
        s.spawn_step[SPAWN_PARTS],
        s.spawn_step[SPAWN_BONEFX],
        s.spawn_step[SPAWN_REST],
        s.slot[SLOT_LOGIC_OBJPROC],
        s.slot[SLOT_LOGIC_TERRAIN],
        s.slot[SLOT_LOGIC_EFFECTS],
        s.slot[SLOT_LOGIC_UIUPD],
        s.terrain_step[TERRAIN_CULL],
        s.terrain_step[TERRAIN_INSERT],
        s.terrain_step[TERRAIN_PROXIMITY],
        s.terrain_step[TERRAIN_TYPE],
        s.terrain_step[TERRAIN_DELETE],
        s.terrain_step[TERRAIN_MAPLOAD],
        s.terrain_step[TERRAIN_ADDMAP],
        s.terrain_step[TERRAIN_REORG],
        s.slot[SLOT_PRESENT_ENDSCENE],
        s.slot[SLOT_PRESENT_SWAP],
        s.mgr_update_ms,
        s.frame_sleep_ms,
        s.flush_sampled
            ? fmt::format("{:.1f}ms/{}n [terrain={} mesh={} tex={} mat={} other={}]",
                  s.flush_ms,
                  s.flush_count,
                  s.flush_kind[0],
                  s.flush_kind[1],
                  s.flush_kind[2],
                  s.flush_kind[3],
                  s.flush_kind[4])
            : std::string("unsampled"),
        s.tex_count,
        s.tex_read_ms,
        s.tex_create_ms,
        s.fx_count,
        s.fx_step[FX_ROOTS],
        s.fx_step[FX_EMITTERS],
        s.fx_step[FX_EXISTS],
        s.fx_step[FX_PTL],
        s.fx_step[FX_MESH],
        s.ptl_count,
        s.ptl_open_ms,
        s.ptl_parse_ms,
        s.ptl_restore_ms,
        s.obj_step[OBJ_MANAGERS],
        s.obj_step[OBJ_PROC],
        s.obj_proc_count,
        s.obj_step[OBJ_DELETE],
        s.obj_delete_count,
        s.obj_worst_ms,
        s.obj_worst_type,
        s.obj_worst_char,
        s.obj_worst_cmd,
        s.cell_step[CELL_HIM],
        s.cell_step[CELL_TIL],
        s.cell_step[CELL_IFO],
        s.cell_step[CELL_LIT],
        s.cell_step[CELL_QUAD],
        // MAP_LUMP_TYPE: 1 object, 2 mob, 3 cnst, 4 sound, 5 effect, 6 morph,
        // 7 water, 8 regen, 10 warp, 11 collision, 12 event object
        s.cell_lump[1],
        s.cell_lump[3],
        s.cell_lump[5],
        s.cell_lump[4],
        s.cell_lump[6],
        s.cell_lump[7],
        s.cell_lump[12],
        s.cell_lump[0] + s.cell_lump[2] + s.cell_lump[8] + s.cell_lump[9] + s.cell_lump[10]
            + s.cell_lump[11],
        s.lit_parts,
        s.lit_step[LIT_ADDMAT],
        s.lit_step[LIT_BUILD],
        s.lit_step[LIT_LIGHTMAP],
        s.lit_step[LIT_BIND],
        // zz_render_pass_slot: 0 sky, 1-3 terrain (opaque/blend/rough), 4 overlay,
        // 5 opaque, 6 transparent, 7 glow, 8 ocean, 9 particle, 10 clear, 11 view, 12 post,
        // 13 particle locks, 14 the locks that wrapped (DISCARD)
        s.rpass_ms[10],
        s.rpass_ms[11],
        s.rpass_ms[0],
        s.rpass_ms[1],
        s.rpass_nodes[1],
        s.rpass_ms[2],
        s.rpass_nodes[2],
        s.rpass_ms[3],
        s.rpass_nodes[3],
        s.rpass_ms[4],
        s.rpass_ms[5],
        s.rpass_nodes[5],
        s.rpass_ms[6],
        s.rpass_nodes[6],
        s.rpass_ms[7],
        s.rpass_nodes[7],
        s.rpass_ms[8],
        s.rpass_nodes[8],
        s.rpass_ms[9],
        s.rpass_nodes[9],
        // 13/14: particle vertex-buffer locks inside the particle pass (nodes = count)
        s.rpass_ms[13],
        s.rpass_nodes[13],
        s.rpass_ms[14],
        s.rpass_nodes[14],
        s.rpass_ms[12],
        others);
}

/// One line per frame dip (see kDipGapMs). Phases and terrain work are averaged over
/// the run's frames, so they read like a frame of the dip; `crossings` counts frames
/// that rotated the map-cell window and `map loads` frames that read a cell.
void EmitDip(DWORD duration_ms) {
    const DipAccum& d = s_dip;
    const double inv = d.frames > 0 ? 1.0 / (double)d.frames : 0.0;
    LOG_INFO("Frame dip: {:.2f} s, {} of {} frames >= {} ms (avg {:.1f}, max {:.1f}) | "
             "avg netin={:.1f} logic={:.1f} scnupd={:.1f} shadow={:.1f} render={:.1f} "
             "ui={:.1f} present={:.1f} | "
             "avg terr[ins={:.1f} del={:.1f} mapload={:.1f}] flush={:.1f}ms/{:.0f} terrain | "
             "avg draws oter={:.1f}ms/{:.0f} bter={:.1f}ms/{:.0f} | "
             "map loads {} crossings {}",
        duration_ms / 1000.0,
        d.slow,
        d.frames,
        s_spike_log_ms,
        d.sum_ms * inv,
        d.max_ms,
        d.slot[SLOT_NETINPUT] * inv,
        d.slot[SLOT_LOGIC] * inv,
        d.slot[SLOT_SCENE_UPDATE] * inv,
        d.slot[SLOT_SHADOW] * inv,
        d.slot[SLOT_RENDER] * inv,
        d.slot[SLOT_UI] * inv,
        d.slot[SLOT_PRESENT] * inv,
        d.terrain_step[TERRAIN_INSERT] * inv,
        d.terrain_step[TERRAIN_DELETE] * inv,
        d.terrain_step[TERRAIN_MAPLOAD] * inv,
        d.flush_ms * inv,
        d.flush_terrain * inv,
        d.oter_ms * inv,
        d.oter_n * inv,
        d.bter_ms * inv,
        d.bter_n * inv,
        d.mapload_frames,
        d.crossing_frames);
}

/// Feeds one finished frame to the dip tracker. Called from EndFrame while the
/// spike log is on, after the frame's buckets are final.
void NoteDipFrame(double frame_ms, DWORD now) {
    const bool slow = frame_ms >= (double)s_spike_log_ms;
    if (!s_dip_active) {
        if (!slow)
            return;
        s_dip.Clear();
        s_dip_tail.Clear();
        s_dip_active = true;
        s_dip_start = now;
    }

    DipAccum f;
    f.Clear();
    f.frames = 1;
    f.slow = slow ? 1 : 0;
    f.sum_ms = frame_ms;
    f.max_ms = frame_ms;
    for (int i = 0; i < SLOT_COUNT; ++i)
        f.slot[i] = s_slot_frame[i];
    for (int i = 0; i < TERRAIN_STEP_COUNT; ++i)
        f.terrain_step[i] = s_terrain_step[i];
    if (s_flush_sampled) {
        f.flush_ms = s_flush_ms;
        f.flush_terrain = s_flush_kind[0];
    }
    // zz_render_pass_slot 1/2: opaque (near) and alpha-faded (far) terrain.
    f.oter_ms = ::getRenderPassUsec(1) / 1000.0;
    f.oter_n = ::getRenderPassNodes(1);
    f.bter_ms = ::getRenderPassUsec(2) / 1000.0;
    f.bter_n = ::getRenderPassNodes(2);
    f.mapload_frames = s_terrain_step[TERRAIN_MAPLOAD] > 0.0 ? 1 : 0;
    f.crossing_frames = s_terrain_step[TERRAIN_ADDMAP] > 0.0 ? 1 : 0;

    if (slow) {
        s_dip.Add(s_dip_tail);
        s_dip.Add(f);
        s_dip_tail.Clear();
        s_dip_last_slow = now;
        return;
    }

    s_dip_tail.Add(f);
    if ((DWORD)(now - s_dip_last_slow) >= kDipGapMs) {
        if (s_dip.slow >= kDipMinSlowFrames)
            EmitDip(s_dip_last_slow - s_dip_start);
        s_dip_active = false;
    }
}

/// Hold this frame if it is the worst of the current window, opening a new window
/// when none is running.
void NoteSpike(double frame_ms, double frame_accounted, DWORD now) {
    if (!s_worst_valid) {
        s_window_start = now;
        s_window_spikes = 0;
    }
    ++s_window_spikes;

    if (s_worst_valid && frame_ms <= s_worst.frame_ms)
        return;

    s_worst.frame_ms = frame_ms;
    s_worst.accounted = frame_accounted;
    for (int i = 0; i < SLOT_COUNT; ++i)
        s_worst.slot[i] = s_slot_frame[i];
    s_worst.avg_ms = s_published_total;
    s_worst.flush_sampled = s_flush_sampled;
    s_worst.flush_ms = s_flush_ms;
    s_worst.flush_count = s_flush_count;
    for (int i = 0; i < kFlushKindCount; ++i)
        s_worst.flush_kind[i] = s_flush_kind[i];
    // Read straight from the engine: sleep() runs once per frame and has already
    // happened by EndFrame, so "last" is this frame's.
    s_worst.mgr_update_ms = ::getLastManagerUpdateUsec() / 1000.0f;
    s_worst.frame_sleep_ms = ::getLastFrameSleepUsec() / 1000.0f;
    s_worst.tex_read_ms = s_tex_read_ms;
    s_worst.tex_create_ms = s_tex_create_ms;
    s_worst.tex_count = s_tex_count;
    s_worst.pkt_count = s_pkt_count;
    s_worst.pkt_worst_ms = s_pkt_worst_ms;
    s_worst.pkt_worst_type = s_pkt_worst_type;
    s_worst.spawn_count = s_spawn_count;
    for (int i = 0; i < SPAWN_STEP_COUNT; ++i)
        s_worst.spawn_step[i] = s_spawn_step[i];
    for (int i = 0; i < TERRAIN_STEP_COUNT; ++i)
        s_worst.terrain_step[i] = s_terrain_step[i];
    s_worst.fx_count = s_fx_count;
    for (int i = 0; i < FX_STEP_COUNT; ++i)
        s_worst.fx_step[i] = s_fx_step[i];
    // Engine counters, reset by BeginFrame, so these are this frame's loads.
    s_worst.ptl_count = ::getParticleLoadCount();
    s_worst.ptl_open_ms = ::getParticleLoadUsec(0) / 1000.0f;
    s_worst.ptl_parse_ms = ::getParticleLoadUsec(1) / 1000.0f;
    s_worst.ptl_restore_ms = ::getParticleLoadUsec(2) / 1000.0f;
    for (int i = 0; i < OBJ_STEP_COUNT; ++i)
        s_worst.obj_step[i] = s_obj_step[i];
    s_worst.obj_proc_count = s_obj_proc_count;
    s_worst.obj_delete_count = s_obj_delete_count;
    s_worst.obj_worst_ms = s_obj_worst_ms;
    s_worst.obj_worst_type = s_obj_worst_type;
    s_worst.obj_worst_char = s_obj_worst_char;
    s_worst.obj_worst_cmd = s_obj_worst_cmd;
    for (int i = 0; i < CELL_STEP_COUNT; ++i)
        s_worst.cell_step[i] = s_cell_step[i];
    for (int i = 0; i < kCellLumpCount; ++i)
        s_worst.cell_lump[i] = s_cell_lump[i];
    s_worst.lit_parts = s_lit_parts;
    for (int i = 0; i < LIT_STEP_COUNT; ++i)
        s_worst.lit_step[i] = s_lit_step[i];
    // Engine counters, reset by BeginFrame, so these are this frame's passes.
    for (int i = 0; i < kRenderPassCount; ++i) {
        s_worst.rpass_ms[i] = ::getRenderPassUsec(i) / 1000.0f;
        s_worst.rpass_nodes[i] = ::getRenderPassNodes(i);
    }
    s_worst_valid = true;
}

} // namespace

void BeginFrame() {
    if (s_freq == 0) {
        LARGE_INTEGER f;
        ::QueryPerformanceFrequency(&f);
        s_freq = f.QuadPart;
        for (int i = 0; i < SLOT_COUNT; ++i) {
            s_slot_accum[i] = 0.0;
            s_slot_open[i] = false;
            s_published[i] = 0.0f;
        }
        for (int i = 0; i < kFlushKindCount; ++i)
            s_flush_kind[i] = 0;
    }
    for (int i = 0; i < SLOT_COUNT; ++i)
        s_slot_frame[i] = 0.0;
    s_flush_sampled = false;
    s_flush_ms = 0.0f;
    s_flush_count = 0;
    for (int i = 0; i < kFlushKindCount; ++i)
        s_flush_kind[i] = 0;
    s_tex_read_ms = 0.0f;
    s_tex_create_ms = 0.0f;
    s_tex_count = 0;
    s_pkt_count = 0;
    s_pkt_worst_ms = 0.0;
    s_pkt_worst_type = 0;
    s_spawn_count = 0;
    for (int i = 0; i < SPAWN_STEP_COUNT; ++i)
        s_spawn_step[i] = 0.0;
    for (int i = 0; i < TERRAIN_STEP_COUNT; ++i)
        s_terrain_step[i] = 0.0;
    // Detail fed only while the spike log is on (every feeder checks
    // IsSpikeLogEnabled), so there is nothing to clear when it is off.
    if (s_spike_log_ms > 0) {
        s_fx_count = 0;
        for (int i = 0; i < FX_STEP_COUNT; ++i)
            s_fx_step[i] = 0.0;
        for (int i = 0; i < OBJ_STEP_COUNT; ++i)
            s_obj_step[i] = 0.0;
        s_obj_proc_count = 0;
        s_obj_delete_count = 0;
        s_obj_worst_ms = 0.0;
        s_obj_worst_type = 0;
        s_obj_worst_char = 0;
        s_obj_worst_cmd = 0;
        for (int i = 0; i < CELL_STEP_COUNT; ++i)
            s_cell_step[i] = 0.0;
        for (int i = 0; i < kCellLumpCount; ++i)
            s_cell_lump[i] = 0.0;
        s_lit_parts = 0;
        for (int i = 0; i < LIT_STEP_COUNT; ++i)
            s_lit_step[i] = 0.0;
        ::resetParticleLoadStats();
        ::resetRenderPassStats();
    }
    s_frame_start = Now();
}

void Begin(Slot slot) {
    if (slot < 0 || slot >= SLOT_COUNT)
        return;
    s_slot_start[slot] = Now();
    s_slot_open[slot] = true;
}

void End(Slot slot) {
    if (slot < 0 || slot >= SLOT_COUNT)
        return;
    if (!s_slot_open[slot]) // End without a matching Begin
        return;
    // Into the per-frame bucket, which EndFrame() folds into the window total.
    // SLOT_LOGIC is bracketed several times per frame, hence '+=' rather than '='.
    s_slot_frame[slot] += ToMs(Now() - s_slot_start[slot]);
    s_slot_open[slot] = false;
}

void SetSpikeLogMs(unsigned int ms) {
    s_spike_log_ms = ms;
    // The engine's own frame statistics (render passes, particle locks and loads)
    // are off unless this log is on, so normal play reads no clocks for them.
    ::setFrameStatsEnabled(ms > 0 ? 1 : 0);
}

bool IsSpikeLogEnabled() {
    return s_spike_log_ms > 0;
}

void NoteSpawn() {
    ++s_spawn_count;
}

void NoteSpawnStep(SpawnStep step, double ms) {
    if (step < 0 || step >= SPAWN_STEP_COUNT)
        return;
    s_spawn_step[step] += ms;
}

void NoteEffect() {
    ++s_fx_count;
}

void NoteEffectStep(EffectStep step, double ms) {
    if (step < 0 || step >= FX_STEP_COUNT)
        return;
    s_fx_step[step] += ms;
}

void NoteObjStep(ObjStep step, double ms) {
    if (step < 0 || step >= OBJ_STEP_COUNT)
        return;
    s_obj_step[step] += ms;
}

void NoteObjDelete() {
    ++s_obj_delete_count;
}

void NoteObjProc(int objType, int charNo, int command, double ms) {
    ++s_obj_proc_count;
    if (ms > s_obj_worst_ms) {
        s_obj_worst_ms = ms;
        s_obj_worst_type = objType;
        s_obj_worst_char = charNo;
        s_obj_worst_cmd = command;
    }
}

void NoteCellStep(CellStep step, double ms) {
    if (s_spike_log_ms == 0 || step < 0 || step >= CELL_STEP_COUNT)
        return;
    s_cell_step[step] += ms;
}

void NoteCellLump(int lumpType, double ms) {
    if (lumpType < 0 || lumpType >= kCellLumpCount)
        return;
    s_cell_lump[lumpType] += ms;
}

void NoteLitStep(LitStep step, double ms) {
    if (step < 0 || step >= LIT_STEP_COUNT)
        return;
    s_lit_step[step] += ms;
}

void NoteLitPart() {
    ++s_lit_parts;
}

void NoteTerrainStep(TerrainStep step, double ms) {
    if (step < 0 || step >= TERRAIN_STEP_COUNT)
        return;
    s_terrain_step[step] += ms;
}

void NotePacket(unsigned short type, double ms) {
    ++s_pkt_count;
    if (ms > s_pkt_worst_ms) {
        s_pkt_worst_ms = ms;
        s_pkt_worst_type = type;
    }
}

void CaptureFlushStats() {
    if (s_spike_log_ms == 0) // inert unless the log is on
        return;
    s_flush_ms = ::getImmediateFlushMs();
    s_flush_count = ::getImmediateFlushCount();
    for (int i = 0; i < kFlushKindCount; ++i)
        s_flush_kind[i] = ::getImmediateFlushKind(i);
    s_tex_read_ms = ::getTextureLoadReadUsec() / 1000.0f;
    s_tex_create_ms = ::getTextureLoadCreateUsec() / 1000.0f;
    s_tex_count = ::getTextureLoadCount();
    s_flush_sampled = true;
}

void EndFrame() {
    if (s_freq == 0 || s_frame_start == 0)
        return;

    const double frame_ms = ToMs(Now() - s_frame_start);
    s_frame_accum += frame_ms;
    if (frame_ms > s_frame_worst)
        s_frame_worst = frame_ms;
    ++s_frames;

    // Per-frame buckets fold into the window totals here, then the spike check reads
    // them while they still hold this frame alone.
    double frame_accounted = 0.0;
    for (int i = 0; i < SLOT_COUNT; ++i) {
        s_slot_accum[i] += s_slot_frame[i];
        // Sub-slots break down SLOT_LOGIC rather than adding to it -- counting them
        // would double-count and drive `oth` negative.
        if (i < SLOT_FIRST_SUB)
            frame_accounted += s_slot_frame[i];
    }

    if (s_spike_log_ms > 0) {
        const DWORD now = ::GetTickCount();
        if (frame_ms >= (double)s_spike_log_ms)
            NoteSpike(frame_ms, frame_accounted, now);
        // Checked every frame, not only on spikes: the held candidate must still be
        // emitted once the window closes even if nothing further crosses the
        // threshold, which is the common case for an isolated hitch.
        if (s_worst_valid && (DWORD)(now - s_window_start) >= kSpikeLogWindowMs) {
            EmitSpike(s_worst, s_window_spikes - 1);
            s_worst_valid = false;
        }
        NoteDipFrame(frame_ms, now);
    }

    if (s_frames < kWindowFrames)
        return;

    const double inv = 1.0 / (double)s_frames;
    double window_accounted = 0.0;
    for (int i = 0; i < SLOT_COUNT; ++i) {
        s_published[i] = (float)(s_slot_accum[i] * inv);
        // Sub-slots are a breakdown *inside* SLOT_LOGIC, so counting them here would
        // double-count that time and make "oth" go negative.
        if (i < SLOT_FIRST_SUB)
            window_accounted += s_slot_accum[i];
        s_slot_accum[i] = 0.0;
    }
    s_published_accounted = (float)(window_accounted * inv);
    s_published_total = (float)(s_frame_accum * inv);
    s_published_max = (float)s_frame_worst;

    s_frame_accum = 0.0;
    s_frame_worst = 0.0;
    s_frames = 0;
}

float GetMs(Slot slot) {
    if (slot < 0 || slot >= SLOT_COUNT)
        return 0.0f;
    return s_published[slot];
}

float GetTotalMs() {
    return s_published_total;
}

float GetMaxTotalMs() {
    return s_published_max;
}

float GetAccountedMs() {
    return s_published_accounted;
}

} // namespace FrameProfiler
