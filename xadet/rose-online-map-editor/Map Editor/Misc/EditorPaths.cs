using System;
using System.IO;

namespace Map_Editor.Misc
{
    /// <summary>
    /// Where the editor keeps files that are not game data: the thumbnail cache
    /// and ZSC backups. They live under %LOCALAPPDATA% rather than beside the
    /// editor, because the editor runs from the game's data folder and anything
    /// left there would be baked into the client's .vfs.
    /// </summary>
    public static class EditorPaths
    {
        public static string Root
        {
            get
            {
                string root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "RoseNextMapEditor");
                Directory.CreateDirectory(root);
                return root;
            }
        }

        public static string Thumbnails
        {
            get
            {
                string folder = Path.Combine(Root, "thumbnails");
                Directory.CreateDirectory(folder);
                return folder;
            }
        }
    }
}
