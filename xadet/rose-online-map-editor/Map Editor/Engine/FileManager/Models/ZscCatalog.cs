using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Map_Editor.Misc;

namespace Map_Editor.Engine.Models
{
    /// <summary>
    /// Every decoration / construction table LIST_ZONE names, so the object
    /// browser can search across zones. A placement in an IFO is an index into
    /// its own zone's table, so an object from another table is only placeable
    /// once <see cref="ZSC.AppendFrom"/> has copied it in; the catalogue just
    /// finds it.
    /// </summary>
    public static class ZscCatalog
    {
        public class Table
        {
            public string Key;          // normalized path, the identity
            public string Path;         // as LIST_ZONE spells it
            public string Name;         // "DECO JPT"
            public string Kind;         // "Decoration" / "Construction"
            public List<string> Zones = new List<string>();
            public ZSC Zsc;             // loaded lazily, or the open zone's own instance
            public bool IsCurrent;      // one of the open zone's two tables
            public string LoadError;

            public string ZonesText
            {
                get { return Zones.Count == 0 ? "no zone" : string.Join(", ", Zones.ToArray()); }
            }
        }

        public class Entry
        {
            public Table Table;
            public int Index;
            public string Name;
            public string Folder;
            public int PartCount;
            public string Haystack;     // lower case, what the search matches
            public string ContentKey;   // ZscRaw.ContentHash: identical objects share it
            public List<Table> AlsoIn = new List<Table>();  // other tables holding an identical object

            public string Tooltip
            {
                get
                {
                    string also = string.Empty;
                    if (AlsoIn.Count > 0)
                    {
                        List<string> names = new List<string>();
                        foreach (Table t in AlsoIn)
                            names.Add(t.Name);
                        also = "\nAlso in: " + string.Join(", ", names.ToArray());
                    }
                    string how = Table.IsCurrent
                        ? "\n\nClick: select (with a placement selected, swaps its model). Double-click: start placing it."
                        : "\n\nNot in this zone's table yet. Double-click (or Add) copies it in as a new ID and starts placing it.";
                    return string.Format("{0}\nID {1} in {2} ({3})\n{4}\n{5} part(s)\nUsed by: {6}{7}{8}", Name, Index, Table.Name, Table.Kind, Folder, PartCount, Table.ZonesText, also, how);
                }
            }
        }

        private static List<Table> tables;
        private static string tablesSignature;

        /// <summary>
        /// The tables LIST_ZONE names, deduplicated by path. The open zone's own
        /// instances are substituted for their files so appended objects show.
        /// Cached for the session; the list of files does not change while the
        /// editor runs.
        /// </summary>
        public static List<Table> Tables(ZSC currentDecoration, string decorationPath, ZSC currentConstruction, string constructionPath)
        {
            string signature = Normalize(decorationPath) + "|" + Normalize(constructionPath);

            if (tables == null)
            {
                tables = new List<Table>();
                Dictionary<string, Table> byKey = new Dictionary<string, Table>();

                Data.STB listZone = FileManager.STBs.ContainsKey("LIST_ZONE") ? FileManager.STBs["LIST_ZONE"] : null;
                Data.STL names = FileManager.STLs.ContainsKey("LIST_ZONE_S") ? FileManager.STLs["LIST_ZONE_S"] : null;

                if (listZone != null)
                {
                    for (int row = 0; row < listZone.Cells.Count; row++)
                    {
                        if (listZone.Cells[row].Count <= ZoneColumns.NameKey)
                            continue;

                        string zoneName = null;
                        try
                        {
                            if (names != null)
                                zoneName = names.Search(listZone.Cells[row][ZoneColumns.NameKey]);
                        }
                        catch
                        {
                        }
                        if (string.IsNullOrEmpty(zoneName))
                            zoneName = "zone " + row;

                        AddTable(byKey, listZone.Cells[row][ZoneColumns.Decoration], "Decoration", zoneName);
                        AddTable(byKey, listZone.Cells[row][ZoneColumns.Construction], "Construction", zoneName);
                    }
                }

                tables.Sort(delegate(Table a, Table b) { return string.Compare(a.Name, b.Name, true); });
            }

            if (signature != tablesSignature)
            {
                foreach (Table t in tables)
                {
                    t.IsCurrent = false;
                    if (t.Key == Normalize(decorationPath) && currentDecoration != null)
                    {
                        t.Zsc = currentDecoration;
                        t.IsCurrent = true;
                    }
                    else if (t.Key == Normalize(constructionPath) && currentConstruction != null)
                    {
                        t.Zsc = currentConstruction;
                        t.IsCurrent = true;
                    }
                }
                tablesSignature = signature;
            }

            return tables;
        }

        private static void AddTable(Dictionary<string, Table> byKey, string path, string kind, string zoneName)
        {
            if (path == null || path.Trim().Length == 0)
                return;

            string key = Normalize(path);
            Table t;
            if (!byKey.TryGetValue(key, out t))
            {
                t = new Table()
                {
                    Key = key,
                    Path = path.Trim(),
                    Kind = kind,
                    Name = TableName(path)
                };
                byKey.Add(key, t);
                tables.Add(t);
            }
            if (!t.Zones.Contains(zoneName))
                t.Zones.Add(zoneName);
        }

        /// <summary>"3DDATA\JUNON\LIST_DECO_JPT.ZSC" -> "DECO JPT".</summary>
        public static string TableName(string path)
        {
            string stem = System.IO.Path.GetFileNameWithoutExtension(path).ToUpperInvariant();
            if (stem.StartsWith("LIST_"))
                stem = stem.Substring(5);
            return stem.Replace('_', ' ');
        }

        public static string Normalize(string path)
        {
            if (path == null)
                return string.Empty;
            return path.Trim().Replace('/', '\\').ToUpperInvariant();
        }

        /// <summary>Loads a table's file if it is not loaded yet. Returns false on failure (logged once).</summary>
        public static bool EnsureLoaded(Table table)
        {
            if (table.Zsc != null)
                return true;
            if (table.LoadError != null)
                return false;

            try
            {
                table.Zsc = new ZSC(table.Path);
                return true;
            }
            catch (Exception ex)
            {
                table.LoadError = ex.Message;
                Output.WriteLine(Output.MessageType.Error, string.Format("Object browser: could not read {0}: {1}", table.Path, ex.Message));
                return false;
            }
        }

        /// <summary>The searchable entries of one table (empty objects skipped).</summary>
        public static List<Entry> Entries(Table table)
        {
            List<Entry> entries = new List<Entry>();
            if (!EnsureLoaded(table))
                return entries;

            ZSC zsc = table.Zsc;
            for (int i = 0; i < zsc.Objects.Count; i++)
            {
                if (zsc.Objects[i].Models == null || zsc.Objects[i].Models.Count == 0)
                    continue;
                entries.Add(MakeEntry(table, i));
            }
            return entries;
        }

        public static Entry MakeEntry(Table table, int index)
        {
            ZSC zsc = table.Zsc;
            ZSC.Object o = zsc.Objects[index];

            StringBuilder hay = new StringBuilder();
            hay.Append('#').Append(index).Append(' ');

            string name = null;
            string folder = null;
            List<string> stems = new List<string>();

            for (int i = 0; i < o.Models.Count; i++)
            {
                int modelID = o.Models[i].ModelID;
                int textureID = o.Models[i].TextureID;
                string mesh = (modelID >= 0 && modelID < zsc.Models.Count) ? zsc.Models[modelID] : string.Empty;
                string texture = (textureID >= 0 && textureID < zsc.Textures.Count) ? zsc.Textures[textureID].Path : string.Empty;

                string stem = Stem(mesh);
                if (stem.Length > 0 && !stems.Contains(stem))
                {
                    stems.Add(stem);
                    hay.Append(stem).Append(' ');
                }
                if (name == null && stem.Length > 0)
                {
                    name = stem;
                    folder = Folder(mesh);
                }

                string texStem = Stem(texture);
                if (texStem.Length > 0)
                    hay.Append(texStem).Append(' ');
            }

            if (name == null)
                name = "object " + index;
            if (folder == null)
                folder = string.Empty;

            if (folder.Length > 0)
                hay.Append(folder.Replace('\\', ' ').Replace('/', ' ')).Append(' ');
            hay.Append(table.Name).Append(' ').Append(table.Kind);

            string shown = name;
            if (o.Models.Count > 1)
                shown = string.Format("{0} (+{1})", name, o.Models.Count - 1);

            return new Entry()
            {
                Table = table,
                Index = index,
                Name = shown,
                Folder = folder,
                PartCount = o.Models.Count,
                Haystack = hay.ToString().ToLowerInvariant(),
                ContentKey = zsc.Raw != null ? zsc.Raw.ContentHash(index) : null
            };
        }

        /// <summary>
        /// A short name for object <paramref name="index"/> of a table: its first
        /// mesh's file name, "(+N)" for more parts. For labels outside the browser.
        /// </summary>
        public static string ObjectName(ZSC zsc, int index)
        {
            if (zsc == null || index < 0 || index >= zsc.Objects.Count)
                return "object " + index;
            ZSC.Object o = zsc.Objects[index];
            if (o.Models == null || o.Models.Count == 0)
                return "object " + index;
            string name = null;
            foreach (ZSC.Object.Model m in o.Models)
            {
                if (m.ModelID >= 0 && m.ModelID < zsc.Models.Count)
                {
                    name = Stem(zsc.Models[m.ModelID]);
                    if (name.Length > 0)
                        break;
                }
            }
            if (string.IsNullOrEmpty(name))
                name = "object " + index;
            return o.Models.Count > 1 ? string.Format("{0} (+{1})", name, o.Models.Count - 1) : name;
        }

        /// <summary>The file name without folder or extension, lower case.</summary>
        public static string Stem(string path)
        {
            if (string.IsNullOrEmpty(path))
                return string.Empty;
            string p = path.Replace('/', '\\');
            int slash = p.LastIndexOf('\\');
            string file = slash >= 0 ? p.Substring(slash + 1) : p;
            int dot = file.LastIndexOf('.');
            if (dot > 0)
                file = file.Substring(0, dot);
            return file.ToLowerInvariant();
        }

        /// <summary>The folder below 3DDATA, e.g. "JUNON\ETC\AGIT001".</summary>
        public static string Folder(string path)
        {
            if (string.IsNullOrEmpty(path))
                return string.Empty;
            string p = path.Replace('/', '\\');
            int slash = p.LastIndexOf('\\');
            string folder = slash >= 0 ? p.Substring(0, slash) : string.Empty;
            if (folder.ToUpperInvariant().StartsWith("3DDATA\\"))
                folder = folder.Substring(7);
            return folder.ToUpperInvariant();
        }

        /// <summary>
        /// True when every whitespace-separated token of <paramref name="query"/>
        /// occurs in the entry's haystack. "#12" matches the id exactly.
        /// </summary>
        public static bool Matches(Entry e, string[] tokens)
        {
            for (int i = 0; i < tokens.Length; i++)
            {
                string t = tokens[i];
                if (t.Length == 0)
                    continue;
                if (t[0] == '#')
                {
                    if (!e.Haystack.StartsWith(t + " "))
                        return false;
                    continue;
                }
                if (e.Haystack.IndexOf(t) < 0)
                    return false;
            }
            return true;
        }

        public static string[] Tokens(string query)
        {
            if (query == null)
                return new string[0];
            return query.Trim().ToLowerInvariant().Split(new char[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
        }

        /// <summary>
        /// Collapses identical objects found in several tables into one entry
        /// (the open zone's copy when there is one, else the first), noting the
        /// other tables in <see cref="Entry.AlsoIn"/>. The retail tables share a
        /// lot (every Junon table carries the same trees), so this shortens the
        /// "All zones" list considerably.
        /// </summary>
        public static List<Entry> Collapse(List<Entry> entries, ZSC preferred)
        {
            Dictionary<string, Entry> byKey = new Dictionary<string, Entry>();
            Dictionary<string, int> position = new Dictionary<string, int>();
            List<Entry> result = new List<Entry>();
            foreach (Entry e in entries)
            {
                if (e.ContentKey == null)
                {
                    result.Add(e);
                    continue;
                }
                Entry kept;
                if (!byKey.TryGetValue(e.ContentKey, out kept))
                {
                    byKey.Add(e.ContentKey, e);
                    position.Add(e.ContentKey, result.Count);
                    result.Add(e);
                    continue;
                }
                if (e.Table.Zsc == preferred && kept.Table.Zsc != preferred)
                {
                    // The zone's own copy represents the group.
                    e.AlsoIn.AddRange(kept.AlsoIn);
                    if (!e.AlsoIn.Contains(kept.Table))
                        e.AlsoIn.Add(kept.Table);
                    kept.AlsoIn.Clear();
                    byKey[e.ContentKey] = e;
                    result[position[e.ContentKey]] = e;
                }
                else if (e.Table != kept.Table && !kept.AlsoIn.Contains(e.Table))
                    kept.AlsoIn.Add(e.Table);
            }
            return result;
        }

        /// <summary>Forget the cached table list (a new data folder was mounted).</summary>
        public static void Reset()
        {
            tables = null;
            tablesSignature = null;
        }

        #region Self test

        /// <summary>
        /// "--zsc-selftest": every LIST_*.ZSC under 3DDATA of the working folder
        /// round-trips byte for byte through the raw codec, each table's parsed
        /// and raw counts agree, appending every object of one table into another
        /// produces a file both readers accept with the right paths behind every
        /// index, and the rotation maths round-trip. Prints to the console and the
        /// editor log; true on success.
        /// </summary>
        public static bool SelfTest()
        {
            bool ok = true;
            int files = 0;

            string root = Path.Combine(Directory.GetCurrentDirectory(), "3DDATA");
            if (!Directory.Exists(root))
            {
                Report("3DDATA not found in " + Directory.GetCurrentDirectory() + " (run from the data folder)");
                return false;
            }

            string rotation = Rotation.SelfTest();
            if (rotation != null)
            {
                Report("FAIL rotation: " + rotation);
                ok = false;
            }
            else
                Report("ok   rotation build/decompose/on-slope");

            List<string> paths = new List<string>();
            Collect(root, paths);
            paths.Sort(StringComparer.OrdinalIgnoreCase);

            Dictionary<string, ZscRaw> raws = new Dictionary<string, ZscRaw>();
            foreach (string path in paths)
            {
                try
                {
                    byte[] bytes = File.ReadAllBytes(path);
                    ZscRaw raw = new ZscRaw(bytes);
                    byte[] back = raw.ToBytes();
                    if (!ZscRaw.Same(bytes, back))
                    {
                        Report("FAIL round trip differs: " + path);
                        ok = false;
                        continue;
                    }

                    ZSC parsed = new ZSC(path);
                    if (parsed.Objects.Count != raw.Objects.Count || parsed.Models.Count != raw.Meshes.Count ||
                        parsed.Textures.Count != raw.Materials.Count || parsed.Effects.Count != raw.Effects.Count)
                    {
                        Report(string.Format("FAIL parsed/raw counts differ: {0} ({1}/{2} objects, {3}/{4} meshes)", path, parsed.Objects.Count, raw.Objects.Count, parsed.Models.Count, raw.Meshes.Count));
                        ok = false;
                        continue;
                    }
                    for (int i = 0; i < raw.Objects.Count; i++)
                    {
                        if (parsed.Objects[i].Models.Count != raw.Objects[i].Parts.Count || parsed.Objects[i].Effects.Count != raw.Objects[i].Dummies.Count)
                        {
                            Report(string.Format("FAIL object {0} part/dummy counts differ in {1}", i, path));
                            ok = false;
                            break;
                        }
                    }

                    raws[path] = raw;
                    files++;
                }
                catch (Exception ex)
                {
                    Report("FAIL " + path + ": " + ex.Message);
                    ok = false;
                }
            }
            Report(string.Format("ok   {0} tables round-trip byte for byte", files));

            // Append test: every object of the second table into a copy of the first,
            // for the first few zone table pairs found.
            int appendPairs = 0;
            List<string> zoneTables = paths.FindAll(delegate(string p)
            {
                string n = Path.GetFileName(p).ToUpperInvariant();
                return (n.StartsWith("LIST_DECO") || n.StartsWith("LIST_CNST")) && raws.ContainsKey(p);
            });

            for (int a = 0; a + 1 < zoneTables.Count && appendPairs < 6; a += 2)
            {
                string dstPath = zoneTables[a];
                string srcPath = zoneTables[a + 1];
                ZscRaw src = raws[srcPath];
                if (src.Objects.Count == 0)
                    continue;

                try
                {
                    ZscRaw dst = new ZscRaw(raws[dstPath].ToBytes());
                    int before = dst.Objects.Count;
                    List<int> indices = new List<int>();
                    for (int i = 0; i < src.Objects.Count; i++)
                    {
                        if (src.Objects[i].Parts.Count == 0)
                            continue;
                        indices.Add(dst.AppendObject(src, i).ObjectIndex);
                    }
                    // Appending again must find every object already present.
                    for (int i = 0, k = 0; i < src.Objects.Count; i++)
                    {
                        if (src.Objects[i].Parts.Count == 0)
                            continue;
                        ZscRaw.AppendResult again = dst.AppendObject(src, i);
                        if (!again.AlreadyPresent || again.ObjectIndex != indices[k++])
                        {
                            Report(string.Format("FAIL re-append of object {0} from {1} was not detected as present", i, srcPath));
                            ok = false;
                            break;
                        }
                    }

                    byte[] bytes = dst.ToBytes();
                    ZscRaw reread = new ZscRaw(bytes);
                    if (reread.Objects.Count != dst.Objects.Count)
                    {
                        Report("FAIL appended table did not read back: " + dstPath);
                        ok = false;
                        continue;
                    }

                    // Every copied part must resolve to the same mesh and material path.
                    for (int i = 0, k = 0; i < src.Objects.Count; i++)
                    {
                        if (src.Objects[i].Parts.Count == 0)
                            continue;
                        ZscRaw.Entry s = src.Objects[i];
                        ZscRaw.Entry d = reread.Objects[indices[k++]];
                        for (int j = 0; j < s.Parts.Count; j++)
                        {
                            if (!ZscRaw.SamePath(src.Meshes[s.Parts[j].Mesh], reread.Meshes[d.Parts[j].Mesh]) ||
                                !ZscRaw.SamePath(src.Materials[s.Parts[j].Material].Path, reread.Materials[d.Parts[j].Material].Path) ||
                                !ZscRaw.Same(src.Materials[s.Parts[j].Material].Flags, reread.Materials[d.Parts[j].Material].Flags) ||
                                !ZscRaw.Same(s.Parts[j].Props, d.Parts[j].Props))
                            {
                                Report(string.Format("FAIL object {0} part {1} from {2} does not resolve to the same files after append", i, j, srcPath));
                                ok = false;
                            }
                        }
                        for (int j = 0; j < s.Dummies.Count; j++)
                        {
                            if (s.Dummies[j].Effect == ZscRaw.NO_EFFECT)
                            {
                                if (d.Dummies[j].Effect != ZscRaw.NO_EFFECT)
                                {
                                    Report(string.Format("FAIL object {0} dummy {1} from {2} lost its no-effect marker", i, j, srcPath));
                                    ok = false;
                                }
                                continue;
                            }
                            if (!ZscRaw.SamePath(src.Effects[s.Dummies[j].Effect], reread.Effects[d.Dummies[j].Effect]))
                            {
                                Report(string.Format("FAIL object {0} dummy {1} from {2} does not resolve to the same effect after append", i, j, srcPath));
                                ok = false;
                            }
                        }
                    }

                    // The parsed reader must accept the result too.
                    string temp = Path.Combine(Path.GetTempPath(), "zsc-selftest.zsc");
                    File.WriteAllBytes(temp, bytes);
                    ZSC parsed = new ZSC(temp);
                    File.Delete(temp);
                    if (parsed.Objects.Count != dst.Objects.Count)
                    {
                        Report("FAIL parsed reader disagrees on the appended table: " + dstPath);
                        ok = false;
                        continue;
                    }

                    Report(string.Format("ok   {0} + all of {1}: {2} -> {3} objects, {4} meshes -> {5}", Path.GetFileName(dstPath), Path.GetFileName(srcPath), before, dst.Objects.Count, raws[dstPath].Meshes.Count, dst.Meshes.Count));
                    appendPairs++;
                }
                catch (Exception ex)
                {
                    Report(string.Format("FAIL append {0} -> {1}: {2}", srcPath, dstPath, ex.Message));
                    ok = false;
                }
            }

            Report(ok ? "ZSC self-test passed" : "ZSC self-test FAILED");
            return ok;
        }

        private static void Collect(string folder, List<string> paths)
        {
            foreach (string file in Directory.GetFiles(folder))
            {
                string name = Path.GetFileName(file).ToUpperInvariant();
                if (name.StartsWith("LIST_") && name.EndsWith(".ZSC"))
                    paths.Add(file);
            }
            foreach (string sub in Directory.GetDirectories(folder))
                Collect(sub, paths);
        }

        private static void Report(string line)
        {
            Console.WriteLine(line);
            try
            {
                File.AppendAllText("Map Editor.log", string.Format("[{0:HH:mm:ss.fff}] zsc-selftest: {1}\r\n", DateTime.Now, line));
            }
            catch
            {
            }
        }

        #endregion
    }
}
