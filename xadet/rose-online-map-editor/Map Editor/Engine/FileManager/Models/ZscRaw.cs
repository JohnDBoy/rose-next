using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace Map_Editor.Engine.Models
{
    /// <summary>
    /// A ZSC table kept as the bytes the game reads, so it can be written back
    /// unchanged and grown by appending objects copied from another table.
    ///
    /// The parsed <see cref="ZSC"/> class is lossy (cylinder values are divided,
    /// collision bits are folded, unknown part properties are skipped), so it is
    /// not a writer. This mirrors scripts/import-oro.py's Zsc: every object is
    /// kept as (cylinder, parts, dummies, bounding box) with each part's property
    /// list as opaque bytes, and only the mesh / material / effect indices are
    /// touched when an object moves between tables.
    ///
    /// Layout: u16 mesh count + NUL strings | u16 material count + (NUL string,
    /// 36 flag bytes) | u16 effect count + NUL strings | u16 object count +
    /// objects. An object is 12 cylinder bytes, u16 part count, parts, u16 dummy
    /// count, dummies, 24 bounding-box bytes; an object with zero parts ends
    /// after the part count. A part is (u16 mesh, u16 material, props); a dummy
    /// is (u16 effect, u16 type, props); props are (u8 tag, u8 len, bytes)*
    /// ended by a zero tag.
    ///
    /// Bytes after the last object are kept in <see cref="Trailing"/> and written
    /// back after the objects. The game reads the declared object count and stops
    /// there; Rednim (668) tables end with an extra block starting "A2C", and
    /// third-party editors leave junk.
    /// </summary>
    public class ZscRaw
    {
        public const int MATERIAL_FLAGS_SIZE = 36;

        /// <summary>A dummy point with no effect file (the game reads it as -1).</summary>
        public const int NO_EFFECT = 0xFFFF;
        public const int CYLINDER_SIZE = 12;
        public const int BOUNDING_BOX_SIZE = 24;

        public class Part
        {
            public ushort Mesh;
            public ushort Material;
            public byte[] Props;
        }

        public class Dummy
        {
            public ushort Effect;
            public ushort Type;
            public byte[] Props;
        }

        public class Entry
        {
            public byte[] Cylinder;
            public List<Part> Parts = new List<Part>();
            public List<Dummy> Dummies = new List<Dummy>();
            public byte[] BoundingBox;
        }

        public class Material
        {
            public byte[] Path;
            public byte[] Flags;
        }

        /// <summary>What an append added to the destination table.</summary>
        public class AppendResult
        {
            public int ObjectIndex;
            public bool AlreadyPresent;
            /// <summary>(source index, destination index) of each mesh that was new.</summary>
            public List<KeyValuePair<int, int>> NewMeshes = new List<KeyValuePair<int, int>>();
            public List<KeyValuePair<int, int>> NewMaterials = new List<KeyValuePair<int, int>>();
            public List<KeyValuePair<int, int>> NewEffects = new List<KeyValuePair<int, int>>();
        }

        public List<byte[]> Meshes = new List<byte[]>();
        public List<Material> Materials = new List<Material>();
        public List<byte[]> Effects = new List<byte[]>();
        public List<Entry> Objects = new List<Entry>();
        public byte[] Trailing = new byte[0];

        public ZscRaw()
        {
        }

        public ZscRaw(byte[] data)
        {
            Load(data);
        }

        public void Load(byte[] data)
        {
            Meshes.Clear();
            Materials.Clear();
            Effects.Clear();
            Objects.Clear();

            int o = 0;

            int meshCount = U16(data, ref o);
            for (int i = 0; i < meshCount; i++)
                Meshes.Add(CStr(data, ref o));

            int materialCount = U16(data, ref o);
            for (int i = 0; i < materialCount; i++)
            {
                Material m = new Material();
                m.Path = CStr(data, ref o);
                m.Flags = Slice(data, ref o, MATERIAL_FLAGS_SIZE);
                Materials.Add(m);
            }

            int effectCount = U16(data, ref o);
            for (int i = 0; i < effectCount; i++)
                Effects.Add(CStr(data, ref o));

            int objectCount = U16(data, ref o);
            for (int i = 0; i < objectCount; i++)
            {
                Entry e = new Entry();
                e.Cylinder = Slice(data, ref o, CYLINDER_SIZE);
                int partCount = U16(data, ref o);
                if (partCount > 0)
                {
                    for (int j = 0; j < partCount; j++)
                    {
                        Part p = new Part();
                        p.Mesh = U16(data, ref o);
                        p.Material = U16(data, ref o);
                        p.Props = Props(data, ref o);
                        e.Parts.Add(p);
                    }
                    int dummyCount = U16(data, ref o);
                    for (int j = 0; j < dummyCount; j++)
                    {
                        Dummy d = new Dummy();
                        d.Effect = U16(data, ref o);
                        d.Type = U16(data, ref o);
                        d.Props = Props(data, ref o);
                        e.Dummies.Add(d);
                    }
                    e.BoundingBox = Slice(data, ref o, BOUNDING_BOX_SIZE);
                }
                Objects.Add(e);
            }

            if (o > data.Length)
                throw new InvalidDataException("ZSC ends inside its last object");

            Trailing = Slice(data, ref o, data.Length - o);
        }

        public byte[] ToBytes()
        {
            MemoryStream ms = new MemoryStream();
            BinaryWriter w = new BinaryWriter(ms);

            w.Write((ushort)Meshes.Count);
            foreach (byte[] m in Meshes)
            {
                w.Write(m);
                w.Write((byte)0);
            }

            w.Write((ushort)Materials.Count);
            foreach (Material m in Materials)
            {
                w.Write(m.Path);
                w.Write((byte)0);
                w.Write(m.Flags);
            }

            w.Write((ushort)Effects.Count);
            foreach (byte[] e in Effects)
            {
                w.Write(e);
                w.Write((byte)0);
            }

            w.Write((ushort)Objects.Count);
            foreach (Entry e in Objects)
            {
                w.Write(e.Cylinder);
                w.Write((ushort)e.Parts.Count);
                if (e.Parts.Count == 0)
                    continue;
                foreach (Part p in e.Parts)
                {
                    w.Write(p.Mesh);
                    w.Write(p.Material);
                    w.Write(p.Props);
                }
                w.Write((ushort)e.Dummies.Count);
                foreach (Dummy d in e.Dummies)
                {
                    w.Write(d.Effect);
                    w.Write(d.Type);
                    w.Write(d.Props);
                }
                w.Write(e.BoundingBox);
            }

            w.Write(Trailing);

            w.Flush();
            return ms.ToArray();
        }

        /// <summary>
        /// Copies object <paramref name="index"/> of <paramref name="source"/> into
        /// this table. Meshes, materials (path + flags) and effects are matched by
        /// value, case-insensitively for paths, and only appended when absent, so
        /// nothing already in the table moves. If an object with the same parts
        /// and dummies (resolved to paths) already exists it is returned instead
        /// of being duplicated.
        /// </summary>
        public AppendResult AppendObject(ZscRaw source, int index)
        {
            if (index < 0 || index >= source.Objects.Count)
                throw new ArgumentOutOfRangeException("index");

            Entry src = source.Objects[index];
            if (src.Parts.Count == 0)
                throw new InvalidOperationException("Cannot copy an empty object");

            foreach (Part p in src.Parts)
            {
                if (p.Mesh >= source.Meshes.Count || p.Material >= source.Materials.Count)
                    throw new InvalidDataException(string.Format("Source object {0} references mesh {1} / material {2} outside its table", index, p.Mesh, p.Material));
            }
            foreach (Dummy d in src.Dummies)
            {
                // 0xFFFF is "no effect" (a bare dummy point); anything else must exist.
                if (d.Effect != NO_EFFECT && d.Effect >= source.Effects.Count)
                    throw new InvalidDataException(string.Format("Source object {0} references effect {1} outside its table", index, d.Effect));
            }

            AppendResult result = new AppendResult();

            // Resolve every index before touching the lists, so an equivalent object
            // can be found without appending anything.
            Dictionary<int, int> meshMap = new Dictionary<int, int>();
            Dictionary<int, int> materialMap = new Dictionary<int, int>();
            Dictionary<int, int> effectMap = new Dictionary<int, int>();

            foreach (Part p in src.Parts)
            {
                if (!meshMap.ContainsKey(p.Mesh))
                    meshMap[p.Mesh] = FindMesh(source.Meshes[p.Mesh]);
                if (!materialMap.ContainsKey(p.Material))
                    materialMap[p.Material] = FindMaterial(source.Materials[p.Material]);
            }
            foreach (Dummy d in src.Dummies)
            {
                if (!effectMap.ContainsKey(d.Effect))
                    effectMap[d.Effect] = d.Effect == NO_EFFECT ? NO_EFFECT : FindEffect(source.Effects[d.Effect]);
            }

            int existing = FindEquivalent(source, src, meshMap, materialMap, effectMap);
            if (existing >= 0)
            {
                result.ObjectIndex = existing;
                result.AlreadyPresent = true;
                return result;
            }

            // Append in the order they are first used, so the result is stable. A
            // source table can list one path under two indices, so look again
            // right before appending: the first part's append must serve the second.
            foreach (Part p in src.Parts)
            {
                if (meshMap[p.Mesh] < 0)
                    meshMap[p.Mesh] = FindMesh(source.Meshes[p.Mesh]);
                if (meshMap[p.Mesh] < 0)
                {
                    Meshes.Add((byte[])source.Meshes[p.Mesh].Clone());
                    meshMap[p.Mesh] = Meshes.Count - 1;
                    result.NewMeshes.Add(new KeyValuePair<int, int>(p.Mesh, Meshes.Count - 1));
                }
                if (materialMap[p.Material] < 0)
                    materialMap[p.Material] = FindMaterial(source.Materials[p.Material]);
                if (materialMap[p.Material] < 0)
                {
                    Materials.Add(new Material()
                    {
                        Path = (byte[])source.Materials[p.Material].Path.Clone(),
                        Flags = (byte[])source.Materials[p.Material].Flags.Clone()
                    });
                    materialMap[p.Material] = Materials.Count - 1;
                    result.NewMaterials.Add(new KeyValuePair<int, int>(p.Material, Materials.Count - 1));
                }
            }
            foreach (Dummy d in src.Dummies)
            {
                if (d.Effect == NO_EFFECT)
                    continue;
                if (effectMap[d.Effect] < 0)
                    effectMap[d.Effect] = FindEffect(source.Effects[d.Effect]);
                if (effectMap[d.Effect] < 0)
                {
                    Effects.Add((byte[])source.Effects[d.Effect].Clone());
                    effectMap[d.Effect] = Effects.Count - 1;
                    result.NewEffects.Add(new KeyValuePair<int, int>(d.Effect, Effects.Count - 1));
                }
            }

            Entry copy = new Entry();
            copy.Cylinder = (byte[])src.Cylinder.Clone();
            copy.BoundingBox = (byte[])src.BoundingBox.Clone();
            foreach (Part p in src.Parts)
            {
                copy.Parts.Add(new Part()
                {
                    Mesh = (ushort)meshMap[p.Mesh],
                    Material = (ushort)materialMap[p.Material],
                    Props = (byte[])p.Props.Clone()
                });
            }
            foreach (Dummy d in src.Dummies)
            {
                copy.Dummies.Add(new Dummy()
                {
                    Effect = (ushort)effectMap[d.Effect],
                    Type = d.Type,
                    Props = (byte[])d.Props.Clone()
                });
            }

            if (Objects.Count >= ushort.MaxValue)
                throw new InvalidOperationException("The table already holds 65535 objects");

            Objects.Add(copy);
            result.ObjectIndex = Objects.Count - 1;
            return result;
        }

        private int FindEquivalent(ZscRaw source, Entry src, Dictionary<int, int> meshMap, Dictionary<int, int> materialMap, Dictionary<int, int> effectMap)
        {
            foreach (KeyValuePair<int, int> kv in meshMap)
                if (kv.Value < 0) return -1;
            foreach (KeyValuePair<int, int> kv in materialMap)
                if (kv.Value < 0) return -1;
            foreach (KeyValuePair<int, int> kv in effectMap)
                if (kv.Value < 0 && kv.Key != NO_EFFECT) return -1;

            for (int i = 0; i < Objects.Count; i++)
            {
                Entry e = Objects[i];
                if (e.Parts.Count != src.Parts.Count || e.Dummies.Count != src.Dummies.Count)
                    continue;
                if (!Same(e.Cylinder, src.Cylinder) || !Same(e.BoundingBox, src.BoundingBox))
                    continue;
                bool same = true;
                for (int j = 0; j < e.Parts.Count && same; j++)
                {
                    same = e.Parts[j].Mesh == meshMap[src.Parts[j].Mesh] &&
                           e.Parts[j].Material == materialMap[src.Parts[j].Material] &&
                           Same(e.Parts[j].Props, src.Parts[j].Props);
                }
                for (int j = 0; j < e.Dummies.Count && same; j++)
                {
                    same = e.Dummies[j].Effect == effectMap[src.Dummies[j].Effect] &&
                           e.Dummies[j].Type == src.Dummies[j].Type &&
                           Same(e.Dummies[j].Props, src.Dummies[j].Props);
                }
                if (same)
                    return i;
            }
            return -1;
        }

        public int FindMesh(byte[] path)
        {
            for (int i = 0; i < Meshes.Count; i++)
                if (SamePath(Meshes[i], path))
                    return i;
            return -1;
        }

        public int FindMaterial(Material material)
        {
            for (int i = 0; i < Materials.Count; i++)
                if (SamePath(Materials[i].Path, material.Path) && Same(Materials[i].Flags, material.Flags))
                    return i;
            return -1;
        }

        public int FindEffect(byte[] path)
        {
            // The effect list doubles as a light list (entries not starting with
            // "3D" are light names); both compare as plain strings.
            for (int i = 0; i < Effects.Count; i++)
                if (SamePath(Effects[i], path))
                    return i;
            return -1;
        }

        /// <summary>Paths compare case-insensitively with / and \ folded.</summary>
        public static bool SamePath(byte[] a, byte[] b)
        {
            if (a.Length != b.Length)
                return false;
            for (int i = 0; i < a.Length; i++)
            {
                byte x = a[i], y = b[i];
                if (x == (byte)'/') x = (byte)'\\';
                if (y == (byte)'/') y = (byte)'\\';
                if (x >= (byte)'a' && x <= (byte)'z') x -= 32;
                if (y >= (byte)'a' && y <= (byte)'z') y -= 32;
                if (x != y)
                    return false;
            }
            return true;
        }

        public static bool Same(byte[] a, byte[] b)
        {
            if (a == null || b == null)
                return a == b;
            if (a.Length != b.Length)
                return false;
            for (int i = 0; i < a.Length; i++)
                if (a[i] != b[i])
                    return false;
            return true;
        }

        public static string Decode(byte[] s)
        {
            return Encoding.GetEncoding("EUC-KR").GetString(s);
        }

        /// <summary>
        /// A hash of everything that makes object <paramref name="index"/> what it
        /// is: its own bytes plus the paths and flags it points at (case and slash
        /// folded). The same object in two tables hashes the same, so it names the
        /// thumbnail and lets the browser show it once. Null for an empty object.
        /// </summary>
        public string ContentHash(int index)
        {
            if (index < 0 || index >= Objects.Count)
                return null;

            Entry e = Objects[index];
            if (e.Parts.Count == 0)
                return null;

            MemoryStream ms = new MemoryStream();
            BinaryWriter w = new BinaryWriter(ms);
            w.Write(e.Cylinder);
            foreach (Part p in e.Parts)
            {
                w.Write(FoldPath(Meshes[p.Mesh]));
                w.Write(FoldPath(Materials[p.Material].Path));
                w.Write(Materials[p.Material].Flags);
                w.Write(p.Props);
            }
            foreach (Dummy d in e.Dummies)
            {
                w.Write(d.Effect == NO_EFFECT ? new byte[0] : FoldPath(Effects[d.Effect]));
                w.Write(d.Type);
                w.Write(d.Props);
            }
            w.Write(e.BoundingBox);
            w.Flush();

            byte[] hash = System.Security.Cryptography.MD5.Create().ComputeHash(ms.ToArray());
            StringBuilder sb = new StringBuilder("v1-");
            foreach (byte b in hash)
                sb.Append(b.ToString("x2"));
            return sb.ToString();
        }

        private static byte[] FoldPath(byte[] path)
        {
            byte[] p = (byte[])path.Clone();
            for (int i = 0; i < p.Length; i++)
            {
                if (p[i] == (byte)'/') p[i] = (byte)'\\';
                if (p[i] >= (byte)'a' && p[i] <= (byte)'z') p[i] -= 32;
            }
            return p;
        }

        #region Reading helpers

        private static ushort U16(byte[] d, ref int o)
        {
            if (o + 2 > d.Length)
                throw new EndOfStreamException("ZSC ends inside a count");
            ushort v = (ushort)(d[o] | (d[o + 1] << 8));
            o += 2;
            return v;
        }

        private static byte[] CStr(byte[] d, ref int o)
        {
            int start = o;
            while (o < d.Length && d[o] != 0)
                o++;
            if (o >= d.Length)
                throw new EndOfStreamException("ZSC ends inside a string");
            byte[] s = new byte[o - start];
            Array.Copy(d, start, s, 0, s.Length);
            o++;
            return s;
        }

        private static byte[] Slice(byte[] d, ref int o, int length)
        {
            if (o + length > d.Length)
                throw new EndOfStreamException("ZSC ends inside a record");
            byte[] s = new byte[length];
            Array.Copy(d, o, s, 0, length);
            o += length;
            return s;
        }

        private static byte[] Props(byte[] d, ref int o)
        {
            int start = o;
            while (true)
            {
                if (o >= d.Length)
                    throw new EndOfStreamException("ZSC ends inside a property list");
                byte tag = d[o++];
                if (tag == 0)
                    break;
                if (o >= d.Length)
                    throw new EndOfStreamException("ZSC ends inside a property list");
                byte len = d[o++];
                o += len;
            }
            if (o > d.Length)
                throw new EndOfStreamException("ZSC ends inside a property");
            byte[] s = new byte[o - start];
            Array.Copy(d, start, s, 0, s.Length);
            return s;
        }

        #endregion
    }
}
