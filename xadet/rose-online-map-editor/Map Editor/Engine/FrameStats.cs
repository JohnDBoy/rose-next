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
    /// placement ghost, bounding boxes), how many boxes were drawn, how many
    /// thumbnails are still queued and how many full garbage collections ran.
    /// Everything is on the UI thread; when disabled nothing is measured.
    /// </summary>
    public static class FrameStats
    {
        public static bool Enabled;

        private const double REPORT_SECONDS = 2.0;

        private static readonly Dictionary<string, long> ticks = new Dictionary<string, long>();
        private static readonly Dictionary<string, int> counts = new Dictionary<string, int>();
        private static readonly string[] order = new string[] { "update", "draw", "pick", "ghost", "boxes" };
        private static long frameStart;
        private static long reportStart;
        private static long worstFrame;
        private static int frames;
        private static int gen2;
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
        /// frame time includes the present) and opens the next.
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
                frameStart = reportStart = now;
                worstFrame = 0;
                frames = 0;
                ticks.Clear();
                counts.Clear();
                gen2 = GC.CollectionCount(2);
                frameOpen = true;
                return;
            }

            long frame = now - frameStart;
            frameStart = now;
            frames++;
            if (frame > worstFrame)
                worstFrame = frame;

            double elapsed = (now - reportStart) / (double)Stopwatch.Frequency;
            if (elapsed < REPORT_SECONDS)
                return;

            Report(elapsed);

            reportStart = now;
            worstFrame = 0;
            frames = 0;
            ticks.Clear();
            counts.Clear();
            gen2 = GC.CollectionCount(2);
        }

        private static void Report(double elapsed)
        {
            double ms = 1000.0 / Stopwatch.Frequency;
            System.Text.StringBuilder sb = new System.Text.StringBuilder();
            sb.AppendFormat("[frame] avg {0:0.0} ms, worst {1:0.0} ms, {2} frames in {3:0.0} s", elapsed * 1000.0 / Math.Max(1, frames), worstFrame * ms, frames, elapsed);
            foreach (string key in order)
            {
                long t;
                if (!ticks.TryGetValue(key, out t))
                    continue;
                int n;
                counts.TryGetValue(key, out n);
                sb.AppendFormat(" | {0} {1:0.00} ms/frame", key, t * ms / Math.Max(1, frames));
                if (n > 0)
                    sb.AppendFormat(" ({0}/frame)", n / Math.Max(1, frames));
            }
            foreach (KeyValuePair<string, long> kv in ticks)
            {
                if (Array.IndexOf(order, kv.Key) >= 0)
                    continue;
                sb.AppendFormat(" | {0} {1:0.00} ms/frame", kv.Key, kv.Value * ms / Math.Max(1, frames));
            }
            sb.AppendFormat(" | thumbnails pending {0}", RenderManager.ObjectThumbnails.Pending);
            sb.AppendFormat(" | gen2 GCs {0}", GC.CollectionCount(2) - gen2);
            Output.WriteLine(Output.MessageType.Normal, sb.ToString());
        }
    }
}
