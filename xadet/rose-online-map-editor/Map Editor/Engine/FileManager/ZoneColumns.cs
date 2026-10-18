using System;
using System.Collections.Generic;
using Map_Editor.Engine.Data;
using Map_Editor.Misc;

namespace Map_Editor.Engine
{
    /// <summary>
    /// The LIST_ZONE columns the editor reads, as editor columns (game column + 1).
    /// </summary>
    /// <remarks>
    /// Rednim's client (the 668 dump) inserted a "WorldMap Visible" column at game
    /// column 11, so every column from the object table on sits one further right:
    /// decoration 12 -> 13, construction 13 -> 14, planet 20 -> 21, name key 27 -> 28.
    /// Read classically, the Open list showed the area size ("12000") as each map's
    /// name and the object tables were never found. <see cref="Detect"/> looks at where
    /// the object table paths actually are, so no setting is needed; the columns before
    /// game column 11 (zone file, sky, minimap, start position) did not move.
    /// </remarks>
    public static class ZoneColumns
    {
        public const int ZoneFile = 2;
        public const int StartPosition = 3;
        public const int RestorePosition = 4;
        public const int Sky = 8;
        public const int Minimap = 9;
        public const int StartX = 10;
        public const int StartY = 11;

        /// <summary>
        /// Gets how far the columns from game column 11 on are shifted: 0 for the
        /// classic layout, 1 for Rednim's (668).
        /// </summary>
        public static int Shift { get; private set; }

        /// <summary>
        /// Gets whether LIST_ZONE has Rednim's 668 layout.
        /// </summary>
        public static bool IsRednim
        {
            get { return Shift != 0; }
        }

        public static int Decoration
        {
            get { return 12 + Shift; }
        }

        public static int Construction
        {
            get { return 13 + Shift; }
        }

        public static int Planet
        {
            get { return 20 + Shift; }
        }

        public static int NameKey
        {
            get { return 27 + Shift; }
        }

        /// <summary>
        /// Reads a cell, or an empty string when the row is too short.
        /// </summary>
        public static string Cell(STB listZone, int row, int column)
        {
            if (row < 0 || row >= listZone.Cells.Count)
                return string.Empty;

            List<string> cells = listZone.Cells[row];

            return column < cells.Count && cells[column] != null ? cells[column] : string.Empty;
        }

        /// <summary>
        /// Works out the layout from the rows' object table paths.
        /// </summary>
        public static void Detect(STB listZone)
        {
            int classic = 0, rednim = 0;

            for (int row = 1; row < listZone.Cells.Count; row++)
            {
                bool at12 = IsZscPath(Cell(listZone, row, 12));
                bool at13 = IsZscPath(Cell(listZone, row, 13));
                bool at14 = IsZscPath(Cell(listZone, row, 14));

                if (at12 && at13)
                    classic++;
                else if (!at12 && at13 && at14)
                    rednim++;
            }

            Shift = rednim > classic ? 1 : 0;

            if (IsRednim)
                Output.WriteLine(Output.MessageType.Event, string.Format("LIST_ZONE has the Rednim (668) layout ({0} rows): reading the object tables from columns {1}/{2} and the names from column {3}", rednim, Decoration, Construction, NameKey));
        }

        private static bool IsZscPath(string cell)
        {
            return cell.Trim().EndsWith(".ZSC", StringComparison.OrdinalIgnoreCase);
        }
    }
}
