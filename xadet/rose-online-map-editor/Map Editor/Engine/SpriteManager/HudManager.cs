using System;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;

namespace Map_Editor.Engine.SpriteManager
{
    /// <summary>
    /// One line of text at the top left of the 3D view saying what the active
    /// tool is doing and what the next click will do ("PLACING tree011 ...",
    /// "SELECTED ..."), plus a short-lived second line for what just happened
    /// ("Placed tree011 as object 412"). Set every frame by the tool; nothing is
    /// drawn when nothing was set.
    /// </summary>
    public static class HudManager
    {
        private static GraphicsDevice device;
        private static SpriteBatch spriteBatch;
        private static Texture2D pixel;
        private static string statusText;
        private static Color statusColour;
        private static string noticeText;
        private static DateTime noticeUntil;

        private static SpriteFont font
        {
            get { return FontManager.GetFont(FontManager.FontType.Verdana12); }
        }

        public static void Initialize(GraphicsDevice device)
        {
            HudManager.device = device;
            spriteBatch = new SpriteBatch(device);
            pixel = new Texture2D(device, 1, 1, 1, TextureUsage.None, SurfaceFormat.Color);
            pixel.SetData<Color>(new Color[] { Color.White });
        }

        /// <summary>The mode line for this frame.</summary>
        public static void SetStatus(string text, Color colour)
        {
            statusText = text;
            statusColour = colour;
        }

        /// <summary>A line under the mode line, shown for <paramref name="seconds"/>.</summary>
        public static void Notice(string text, float seconds)
        {
            noticeText = text;
            noticeUntil = DateTime.Now.AddSeconds(seconds);
        }

        public static void Draw()
        {
            Draw(true);
        }

        /// <summary>
        /// Fullscreen: the short-lived line only (a camera speed change), never
        /// the tool's mode line.
        /// </summary>
        public static void DrawNotice()
        {
            Draw(false);
        }

        private static void Draw(bool withStatus)
        {
            if (spriteBatch == null)
                return;

            if (!withStatus)
                statusText = null;

            bool notice = noticeText != null && DateTime.Now < noticeUntil;
            if (string.IsNullOrEmpty(statusText) && !notice)
                return;

            spriteBatch.Begin(SpriteBlendMode.AlphaBlend, SpriteSortMode.Deferred, SaveStateMode.SaveState);

            float y = 8.0f;
            if (!string.IsNullOrEmpty(statusText))
            {
                DrawLine(statusText, ref y, statusColour, new Color(20, 28, 42, 190));
            }
            if (notice)
            {
                DrawLine(noticeText, ref y, new Color(190, 255, 190), new Color(20, 60, 30, 190));
            }

            spriteBatch.End();

            statusText = null;
        }

        private static void DrawLine(string text, ref float y, Color colour, Color back)
        {
            int maxWidth = Math.Max(100, device.Viewport.Width - 16);
            string shown = Fit(text, maxWidth);
            Vector2 size = font.MeasureString(shown);
            Rectangle box = new Rectangle(8, (int)y, (int)size.X + 16, (int)size.Y + 8);
            spriteBatch.Draw(pixel, box, back);
            spriteBatch.DrawString(font, shown, new Vector2(16.0f, y + 4.0f), colour);
            y += box.Height + 4;
        }

        /// <summary>Shortens a line with "..." so it fits the view.</summary>
        private static string Fit(string text, int width)
        {
            if (font.MeasureString(text).X + 16 <= width)
                return text;
            string cut = text;
            while (cut.Length > 4 && font.MeasureString(cut + "...").X + 16 > width)
                cut = cut.Substring(0, cut.Length - 1);
            return cut + "...";
        }
    }
}
