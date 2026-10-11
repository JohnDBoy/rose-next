using System;
using System.Collections.Generic;
using System.Diagnostics;
using Map_Editor.Misc;

namespace Map_Editor.Engine
{
    /// <summary>
    /// A frame profiler for the editor's own loop: View > Frame statistics writes
    /// one line every two seconds to the Output panel (and the log) with the
    /// average and worst frame, where the time went (update, draw, terrain pick,
    /// placement ghost, bounding boxes, the browser's UI work) and what was
    /// outside the game loop altogether ("other": WPF layout and rendering,
    /// dispatcher callbacks, timers, the present wait), how many boxes were
    /// drawn, how many thumbnails were made and are still queued, and how many
    /// garbage collections ran. The worst frame gets its own breakdown.
    /// Everything is on the UI thread; when disabled nothing is measured.
    /// </summary>
    public static class FrameStats
    {
        public static bool Enabled;

        private const double REPORT_SECONDS = 2.0;

        private static readonly Dictionary<string, long> ticks = new Dictionary<string, long>();
        private static readonly Dictionary<string, long> frameTicks = new Dictionary<string, long>();
        private static readonly Dictionary<string, int> counts = new Dictionary<string, int>();
        private static readonly string[] order = new string[] { "update", "draw", "pick", "ghost", "boxes", "ui" };
        private static long frameStart;
        private static long reportStart;
        private static long worstFrame;
        private static string worstDetail = string.Empty;
        private static int frames;
        private static int gen0, gen1, gen2;
        private static int thumbnailsDone;
        private static bool frameOpen;

        /// <summary>The start of a timed section; pass the result to <see cref="Add"/>.</summary>
        public static long Start()
        {
            return Enabled ? Stopwatch.GetTimestamp() : 0;
        }

        /// <summary>Accounts the time since <paramref name="start"/> to <paramref name="key"/>.</summary>
        public static void Add(string key, long start)
        {
            if (!Enabled || start == 0)
                return;
            long now = Stopwatch.GetTimestamp();
            long have;
            ticks.TryGetValue(key, out have);
            ticks[key] = have + (now - start);
            frameTicks.TryGetValue(key, out have);
            frameTicks[key] = have + (now - start);
        }

        public static void Count(string key, int n)
        {
            if (!Enabled)
                return;
            int have;
            counts.TryGetValue(key, out have);
            counts[key] = have + n;
        }

        /// <summary>
        /// Called at the top of every Update: closes the previous frame (so the
        /// frame time includes the present and whatever the message pump ran
        /// between frames) and opens the next.
        /// </summary>
        public static void FrameBoundary()
        {
            if (!Enabled)
            {
                frameOpen = false;
                return;
            }

            long now = Stopwatch.GetTimestamp();
            if (!frameOpen)
            {
                Reset(now);
                frameOpen = true;
                return;
            }

            long frame = now - frameStart;
            frameStart = now;
            frames++;
            if (frame > worstFrame)
            {
                worstFrame = frame;
                worstDetail = Breakdown(frame);
            }
            frameTicks.Clear();

            double elapsed = (now - reportStart) / (double)Stopwatch.Frequency;
            if (elapsed < REPORT_SECONDS)
                return;

            Report(elapsed);
            Reset(now);
        }

        private static void Reset(long now)
        {
            frameStart = reportStart = now;
            worstFrame = 0;
            worstDetail = string.Empty;
            frames = 0;
            ticks.Clear();
            frameTicks.Clear();
            counts.Clear();
            gen0 = GC.CollectionCount(0);
            gen1 = GC.CollectionCount(1);
            gen2 = GC.CollectionCount(2);
            thumbnailsDone = RenderManager.ObjectThumbnails.Completed;
        }

        private static string Breakdown(long frame)
        {
            double ms = 1000.0 / Stopwatch.Frequency;
            long update, draw, ui;
            frameTicks.TryGetValue("update", out update);
            frameTicks.TryGetValue("draw", out draw);
            frameTicks.TryGetValue("ui", out ui);
            long other = frame - update - draw - ui;
            return string.Format("update {0:0.0}, draw {1:0.0}, ui {2:0.0}, other {3:0.0}", update * ms, draw * ms, ui * ms, other * ms);
        }

        private static void Report(double elapsed)
        {
            double ms = 1000.0 / Stopwatch.Frequency;
            int n = Math.Max(1, frames);
            long totalTicks = (long)(elapsed * Stopwatch.Frequency);
            long accounted = 0;

            System.Text.StringBuilder sb = new System.Text.StringBuilder();
            sb.AppendFormat("[frame] avg {0:0.0} ms, worst {1:0.0} ms ({2}), {3} frames in {4:0.0} s", elapsed * 1000.0 / n, worstFrame * ms, worstDetail, frames, elapsed);
            foreach (string key in order)
            {
                long t;
                if (!ticks.TryGetValue(key, out t))
                    continue;
                if (key == "update" || key == "draw" || key == "ui")
                    accounted += t;
                int c;
                counts.TryGetValue(key, out c);
                sb.AppendFormat(" | {0} {1:0.00} ms/frame", key, t * ms / n);
                if (c > 0)
                    sb.AppendFormat(" ({0}/frame)", c / n);
            }
            foreach (KeyValuePair<string, long> kv in ticks)
            {
                if (Array.IndexOf(order, kv.Key) >= 0)
                    continue;
                sb.AppendFormat(" | {0} {1:0.00} ms/frame", kv.Key, kv.Value * ms / n);
            }
            sb.AppendFormat(" | other {0:0.00} ms/frame", (totalTicks - accounted) * ms / n);
            sb.AppendFormat(" | thumbnails made {0}, pending {1}", RenderManager.ObjectThumbnails.Completed - thumbnailsDone, RenderManager.ObjectThumbnails.Pending);
            sb.AppendFormat(" | GCs gen0 {0} gen1 {1} gen2 {2}", GC.CollectionCount(0) - gen0, GC.CollectionCount(1) - gen1, GC.CollectionCount(2) - gen2);
            Output.WriteLine(Output.MessageType.Normal, sb.ToString());
        }
    }
}
