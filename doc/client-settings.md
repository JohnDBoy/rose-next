# Client settings, framerate and streaming diagnostics

The client reads `rose-next.ini` from its **working directory** (not necessarily
the exe's folder — if you launch via a shortcut, check its "Start in"). Most of
it is written by the in-game options screen; the keys below are the ones that are
only settable by hand, or that matter when developing or diagnosing. The short
table in the [README](../README.md) is the summary; this file is the detail.

> Whichever way you set these, **confirm the result in the logs** — every one of
> these paths logs which branch is live (`error.txt` for the renderer and screen
> mode, `client.log` for the client-side ones). A toggle that silently does
> nothing is indistinguishable from one that works, and that has cost real
> debugging time here more than once.

## Fullscreen: borderless vs exclusive

`[VIDEO] FULLSCREEN=1` gives you a **borderless** window by default — a normal
windowed Direct3D device sized to fill the monitor. Nothing ever takes ownership
of the display mode, so alt-tabbing is instant and there is no mode switch to
blank the screen. Two consequences worth knowing:

- `[RESOLUTION] WIDTH`/`HEIGHT` are ignored; the render target always matches the
  monitor. A mismatched backbuffer would be stretched by D3D and would drift the
  UI hit-testing away from what is drawn.
- The window is not topmost, so overlays and other windows behave normally.

`[VIDEO] EXCLUSIVE_FULLSCREEN=1` restores the classic exclusive device, which
does own the display mode and does honour `[RESOLUTION]`. It is kept mainly as
an A/B switch: exclusive fullscreen has been observed producing brief
full-screen black flashes mid-session (Windows minimises an exclusive-fullscreen
window when the app is deactivated, and each minimise/restore round trip is a
display mode switch). Borderless has no such mechanism. Details and the current
state of that investigation are in [d3d9ex-migration.md](d3d9ex-migration.md).

Confirm which one you actually got from `error.txt`:

```
screen: mode=borderless size=1920x1080 (ini FULLSCREEN=1, EXCLUSIVE_FULLSCREEN=0)
```

## Framerate: vsync, `MAX_FPS`, and a claim that did not survive testing

**Vsync on (`[VIDEO] VSYNC=1`, the default) is the recommended setting for
playing.** It is the smoothest frame pacing the client has, and nothing below
changes that. `VSYNC=0` exists for measurement: with vsync on, the wait is paid
in the `present` phase and masks every other phase's real cost.

`[VIDEO] MAX_FPS` exists because vsync used to be the only way to limit the
framerate — the engine has its own limiter, but `data/SCRIPTS/INIT.LUA` asks for
a maximum of 1000, which disables it in practice. It is for the cases where you
run without vsync anyway: a cap without vsync's added latency, or a VRR display
where the usual advice is to cap a few Hz below refresh.

**It does not appear to affect streaming, contrary to what the README first
claimed.** The theory was that the resource amortiser loads ahead in wall-clock
time, so a higher framerate would leave it less room and force more loading onto
the render path. Measured on the same route, at the same chunk arrival
(`[mesh=7 tex=9]`), warm cache, same log threshold:

| config | frame budget | `flush` (work forced at render) |
| --- | --- | --- |
| uncapped, ~300 fps | 3.3 ms | 3.8 / 4.1 / 5.0 ms |
| capped, 144 fps | 6.9 ms | 4.0 ms |

No difference. The earlier claim rested on a 60 Hz run that appeared to show
`flush` of 0.0–1.5 ms, but **that run used `FRAME_SPIKE_LOG_MS=20` while the
others used 15** — and at 60 Hz a frame carrying 4 ms of flush totals only ~17 ms,
so it was never logged. The comparison was selection bias, not a result.

If you want to settle it, compare with **`STREAM_SPIKE_LOG_MS`** instead: it
triggers on flush time rather than total frame time, so it is independent of
framerate and of whether vsync pins every frame to the refresh interval. A
total-frame-time threshold cannot compare streaming across framerates, which is
the trap above.

The limiter is `::Sleep()`-based (`zz_system::sleep`), so the cap is approximate
and lands slightly *under* the target, and it can only ever add delay — it cannot
rescue a frame that is already late. Confirm it took effect in `client.log`:
`Framerate cap: 144 fps ([VIDEO] MAX_FPS)`.

## View distance and terrain batching

How far you see depends on two things: how much of the world is loaded, and
where the terrain fades into the sky.

**`TERRAIN_RADIUS`** (default `2`) is how many 160 m map chunks are kept loaded
around you, as a radius: `2` is a 5x5 square, so the ground reaches at least
320 m in every direction; `1` is the original 3x3 (160 m). Objects belong to the
chunk holding their centre, so a bigger window also stops large cliffs and walls
from popping in close by.

**The fade** comes from the Options view distance (`[VIDEO] Camera`): Near,
Normal or Far. With the data from `scripts/set-camera-fog.py`, Normal fades the
terrain out between 200 and 320 m, which is seamless with the 5x5 window, and
Far between 260 and 450 m, where you can occasionally see the window's edge in
the last stretch. Without that data the old fades apply (220 m on Normal), and
the bigger window shows little difference.

**`TERRAIN_BATCH`** (default `1`) is what makes 5x5 affordable. The original
client draws every 10 m terrain tile separately: 256 draw calls per chunk, which
on the Far view was ~5,600 draws and 7–9 ms of every frame, plus 256 small
buffers to build for each chunk that streamed in. With batching each chunk's
terrain is one buffer and a few dozen draws (one per texture), measured at a few
hundred draws and 0.1–0.2 ms in total, and the border-crossing dips are gone.
The ground looks the same. `0` restores the per-tile path for comparison; the
value is read once at startup.

**`TERRAIN_EVICT_BUDGET_US`** (default `2000`) caps how long a frame may spend
removing tiles that left the view. After a camera swing they all used to go in
one frame (17–51 ms on the Far view). Tiles waiting their turn cost nothing.
`0` removes the cap.

## Streaming and hitch tuning

The world is streamed in *chunks* (a 160 m square of terrain, 16×16 tiles). When
you cross a boundary the client loads the next chunk from disk and, shortly
after, has to build and upload its geometry and textures to the GPU. Both used to
stall the frame. The defaults below are the measured-good values; you should only
need to touch them if you are on unusual hardware or chasing a stutter.

**`TERRAIN_INSERTS_PER_FRAME`** (default `24`) is the one worth experimenting
with. It caps how many *distant* terrain tiles are allowed to appear in a single
frame — tiles near you are never delayed, so this can't leave a hole under your
feet. Previously all 256 tiles of an arriving chunk appeared at once, and the
frame that rendered them paid for all of it (12–46 ms).

- **Lower it** (12, 8) for a smaller hitch, at the cost of distant terrain
  filling in more gradually. If you can see terrain popping in at the horizon,
  you have gone too low.
- **`0`** disables the cap entirely, restoring the old behaviour.

What actually costs the time is the *textures* a batch of tiles pulls in (~3 ms
each) rather than the tiles themselves (~0.1 ms each), so this dial has more
effect than its name suggests. With `TERRAIN_BATCH=1` the ground of an arriving
chunk is drawn by its batch at once, so this cap only paces the objects on the
distant tiles.

**`LOAD_BUDGET_US`** (default `2000`) is how long per frame the engine may spend
loading resources *ahead* of needing them. The engine estimates load cost with a
rule from 2003 — one millisecond per kilobyte — which badly overestimates modern
hardware, so a 350 KB texture was assumed to need 350 ms and got postponed for
~70 frames, then loaded urgently at the worst possible moment. This paces that
work on actual measured time instead. `0` restores the old behaviour.

**`CACHE_WARM_MB`** (default `300`) is a different trade from the two above: it
spends time you are *already* waiting through. While a loading screen is up, a
background thread reads that zone's asset groups end to end — the zone's own map
directory first, then its terrain tiles, then the shared NPC and motion trees —
so the first in-game access to any of them costs no disk read. Map-chunk requests
always take priority, and the budget is per zone, not per session.

Measured on a cold cache, same five-zone route, warming on versus off:

| | in-game texture read | frames > 20 ms |
| --- | --- | --- |
| on | **0.135–0.142 ms** each | 6 |
| off | 0.503 ms each | 10 |

Two things worth knowing before you tune it. The gain is **entirely in the
streaming that happens while you walk around** — it does nothing for the zone
transition itself (0.475 vs 0.445 ms), because the warm starts at the same moment
that zone's own texture burst does and can never get ahead of it. And measuring
any of this needs a genuinely cold cache: a second run reads from RAM either way,
so an A/B without an eviction step reports "no difference" however well it works.
`just purge-cache` drops the standby list in about a second, which is the part of
a reboot that matters here.

## Diagnosing a hitch

There are two spike logs, and they answer different questions. Start with the
frame one, because it tells you whether streaming is even involved.

**`FRAME_SPIKE_LOG_MS`** triggers on *total frame time* and reports where the
milliseconds went. Set it to `20` (a doubled frame at 60 fps) and play; every
frame over the threshold writes one line to `client.log`:

```
Frame spike: 47.3 ms (avg 8.1) | netin=0.3 logic=2.1 scnupd=1.2 shadow=31.9
render=8.4 ui=1.1 present=1.9 oth=0.4 | logic[obj=1.4 terr=0.2 fx=0.3 uiupd=0.1]
| flush=30.2ms/258n [terrain=255 mesh=0 tex=3 mat=0 other=0] | others=0
```

Read it in this order:

1. **Which phase is large?** That is the answer. `netin` = packet drain (a spawn
   burst lands here), `logic` = game logic (split further by the `logic[...]`
   group), `scnupd` = engine transforms/culling/animation, `shadow` =
   `beginScene()` and the shadow-map pass, `render` = draw submission, `present`
   = waiting for the GPU, `oth` = inside the frame but outside every bracket.
2. **Is `flush=` large?** Then it is the streaming path and the two dials above
   apply. If it is small while a phase is large, the hitch is *not* streaming and
   no amount of `TERRAIN_INSERTS_PER_FRAME` tuning will move it. Note `flush=` is
   a whole-frame total spread across `scnupd`, `shadow` and `render`, so it tells
   you streaming was involved without telling you which phase paid for it.
3. **Compare with `avg=`**, the recent frame-time mean. 40 ms against an 8 ms
   average is a hitch; 40 ms against a 35 ms average is just a slow scene, and
   the fix is throughput rather than spike-hunting.

`present` is expected to be large with `VSYNC=1` — that is where the frame cap is
paid — so run with `VSYNC=0` while hunting, otherwise every phase's real cost is
masked by the wait. `others=N` reports spikes folded into the line by the 250 ms
rate limit, so a burst still tells you its true size.

A run of frames that are each only a little late — what you feel as the frame
rate dipping for a second — shows up as a handful of spike lines with large
`others=` counts. The same setting therefore also writes one line per run:

```
Frame dip: 0.97 s, 26 of 48 frames >= 20 ms (avg 20.5, max 25.9) | avg netin=0.1
logic=3.2 ... render=8.5 ... | avg terr[ins=0.3 del=0.9 mapload=0.1] flush=1.0ms/10
terrain | avg draws oter=1.9ms/1905 bter=5.5ms/3620 | map loads 5 crossings 0
```

The phases are averaged over the run, so they read like one frame of it.
`map loads` and `crossings` say whether the run followed a chunk boundary. The
`oter`/`bter` draws are the per-tile terrain; with `TERRAIN_BATCH=1` the batched
terrain is the `rter` entry of the spike line instead. `flush=unsampled` means the
frame never reached the sample point (lost focus, or the scene did not begin) —
it does not mean flushing was free.

**`STREAM_SPIKE_LOG_MS`** is the narrower one: it triggers only on time spent
force-loading resources, so it is silent for any hitch streaming did not cause.
Set it to `4` and it writes:

```
Flush spike: 25.3 ms over 259 nodes [terrain=255 mesh=0 tex=4 ...] leadavg=1 ...
```

`terrain`/`mesh`/`tex` say *what* was loaded, and `leadavg` — how many frames the
work sat waiting before it was needed — says which knob applies: **~1 frame**
means it was needed immediately, so lower `TERRAIN_INSERTS_PER_FRAME`;
**hundreds of frames** means the pre-loader had time and wasted it, so raise
`LOAD_BUDGET_US`.

Turn both back off (`0`) afterwards — they are chatty. Zone-in and the first
frames after a warp are legitimately enormous, so expect a cluster there and
judge steady-state play instead.

The in-game debug HUD (`D` with GM rights) also carries `MapIO:`, `Flush:` and
`Time:` rows for live values, and `/perfreset` re-zeroes the peak counters, which
otherwise saturate during zone-in and then tell you nothing. The HUD's `Time:`
row is a 30-frame average with a `max` column — the frame spike log exists
because a single bad frame survives one window there and is then gone.

The UI2 layer has its own measurement: `/uistats` samples the next three seconds
of UI update and render time, draw calls and open documents, and writes one line
to `client.log`. Measure with `VSYNC=0`.
