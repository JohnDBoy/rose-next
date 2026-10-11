// Headless checks of the object browser, the ZSC append/save path and the
// rotation editor, against the real data folder. Run by Run-ObjectBrowserTests.ps1.
//
// C# 3 (the .NET 3.5 compiler): no var-less lambdas with statements beyond
// what C# 3 allows, no optional parameters, no string interpolation.
using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Windows.Threading;
using Map_Editor.Engine;
using Map_Editor.Engine.Models;
using Map_Editor.Engine.RenderManager;
using Map_Editor.Forms.Controls;
using Map_Editor.Misc;
using Microsoft.Xna.Framework;

public static class ObjectBrowserTests
{
    private static int failures;

    private static void Check(bool ok, string what)
    {
        Console.WriteLine((ok ? "  ok    " : "  FAIL  ") + what);
        if (!ok)
            failures++;
    }

    /// <summary>Runs the dispatcher for a while (timers, thumbnail callbacks).</summary>
    private static void Pump(int milliseconds)
    {
        DispatcherFrame frame = new DispatcherFrame();
        DispatcherTimer timer = new DispatcherTimer();
        timer.Interval = TimeSpan.FromMilliseconds(milliseconds);
        timer.Tick += delegate { timer.Stop(); frame.Continue = false; };
        timer.Start();
        Dispatcher.PushFrame(frame);
    }

    private static bool PumpUntil(Func<bool> done, int timeoutMs)
    {
        DateTime end = DateTime.Now.AddMilliseconds(timeoutMs);
        while (DateTime.Now < end)
        {
            if (done())
                return true;
            Pump(100);
        }
        return done();
    }

    public static int Main(string[] args)
    {
        string data = args[0], scratch = args[1];
        Directory.CreateDirectory(scratch);
        Directory.SetCurrentDirectory(data);

        ConfigurationManager.LoadConfig();
        ConfigurationManager.CheckConfig();

        Console.WriteLine("Tables");
        FileManager.Initialize();
        string decoPath = FileManager.STBs["LIST_ZONE"].Cells[2][12];      // Junon Polis (JPT)
        string cnstPath = FileManager.STBs["LIST_ZONE"].Cells[2][13];
        FileManager.Add("Decoration", decoPath, FileManager.FileType.ZSC);
        FileManager.Add("Construction", cnstPath, FileManager.FileType.ZSC);
        ZSC zone = FileManager.ZSCs["Decoration"];
        int zoneCount = zone.Objects.Count;
        Check(zoneCount > 100 && zone.Raw != null && zone.FilePath == decoPath, string.Format("zone 2 decoration table {0}: {1} objects, raw kept", decoPath, zoneCount));

        List<ZscCatalog.Table> tables = ZscCatalog.Tables(zone, decoPath, FileManager.ZSCs["Construction"], cnstPath);
        int current = 0;
        foreach (ZscCatalog.Table t in tables)
            if (t.IsCurrent) current++;
        Check(tables.Count >= 40 && current == 2, string.Format("catalogue lists {0} tables from LIST_ZONE, 2 of them the open zone's", tables.Count));

        ZscCatalog.Table zoneTable = null;
        foreach (ZscCatalog.Table t in tables)
            if (t.Zsc == zone) zoneTable = t;
        List<ZscCatalog.Entry> entries = ZscCatalog.Entries(zoneTable);
        Check(entries.Count > 100 && entries[0].Name.Length > 0 && entries[0].Haystack.StartsWith("#" + entries[0].Index + " "), string.Format("{0} searchable entries (empty objects skipped); first is '{1}' (id {2}) in {3}", entries.Count, entries[0].Name, entries[0].Index, entries[0].Folder));
        int trees = 0;
        string[] tokens = ZscCatalog.Tokens("tree");
        foreach (ZscCatalog.Entry e in entries)
            if (ZscCatalog.Matches(e, tokens)) trees++;
        Check(trees > 5, string.Format("'tree' matches {0} objects of the zone table", trees));
        ZscCatalog.Entry five = entries.Find(delegate(ZscCatalog.Entry e) { return e.Index == 5; });
        Check(five != null && ZscCatalog.Matches(five, ZscCatalog.Tokens("#5")) && !ZscCatalog.Matches(five, ZscCatalog.Tokens("#50")) && !ZscCatalog.Matches(entries[0], ZscCatalog.Tokens("#5")), "'#5' matches id 5 only");

        Console.WriteLine("Browser");
        Exception uiError = null;
        Thread ui = new Thread(delegate()
        {
            try
            {
                ObjectBrowser browser = new ObjectBrowser();
                browser.Width = 300;
                browser.Height = 470;
                ConfigurationManager.SetValue("Placement", "BrowseAllTables", false);
                browser.Initialize(zone, decoPath, "Decoration");
                Pump(300);
                int shown = browser.ShownEntries.Count;
                Check(shown == Math.Min(ObjectBrowser.MAX_SHOWN, entries.Count), string.Format("'This zone' shows {0} tiles ({1})", shown, browser.Status.Text));

                browser.SearchBox.Text = "tree";
                Pump(400);
                bool allTrees = browser.ShownEntries.Count > 0;
                foreach (ZscCatalog.Entry e in browser.ShownEntries)
                    if (!e.Haystack.Contains("tree")) allTrees = false;
                Check(allTrees && browser.ShownEntries.Count == trees, string.Format("search 'tree': {0} tiles, all trees ({1})", browser.ShownEntries.Count, browser.Status.Text));

                // Thumbnails arrive for the shown tiles.
                ZscCatalog.Entry first = browser.ShownEntries[0];
                bool pictured = PumpUntil(delegate { return browser.TileImage(first) != ObjectThumbnails.Placeholder(); }, 60000);
                Check(pictured, string.Format("thumbnail for '{0}' arrived (pending {1})", first.Name, ObjectThumbnails.Pending));
                PumpUntil(delegate { return ObjectThumbnails.Pending == 0; }, 120000);
                Check(ObjectThumbnails.Pending == 0 && Directory.GetFiles(EditorPaths.Thumbnails, "*.png").Length > 0, string.Format("all shown thumbnails made; {0} cached in {1}", Directory.GetFiles(EditorPaths.Thumbnails, "*.png").Length, EditorPaths.Thumbnails));

                // All zones: more objects, foreign ones marked, append on use.
                browser.SearchBox.Text = string.Empty;
                browser.Scope.SelectedIndex = 1;
                bool loaded = PumpUntil(delegate { return !browser.IsLoadingAll && !browser.Status.Text.StartsWith("Reading"); }, 60000);
                Check(loaded && browser.ShownEntries.Count == ObjectBrowser.MAX_SHOWN, string.Format("'All zones' loaded: {0}", browser.Status.Text));
                int grouped = 0;
                foreach (ZscCatalog.Entry e in browser.ShownEntries)
                    if (e.AlsoIn.Count > 0) grouped++;
                Check(grouped > 0, string.Format("{0} of the shown objects stand for identical copies in other tables", grouped));

                browser.SearchBox.Text = "crane";
                Pump(400);
                ZscCatalog.Entry foreign = null;
                foreach (ZscCatalog.Entry e in browser.ShownEntries)
                    if (e.Table.Zsc != zone) { foreign = e; break; }
                Check(foreign != null, string.Format("search 'crane' across zones finds an object from another table ({0})", browser.Status.Text));

                if (foreign != null)
                {
                    Check(browser.Select(foreign) && browser.SelectedZoneIndex == -1 && browser.ForeignHint.Visibility == System.Windows.Visibility.Visible, string.Format("'{0}' from {1} highlighted as foreign, hint shown", foreign.Name, foreign.Table.Name));
                    int meshesBefore = zone.Models.Count;
                    int index = browser.EnsureInZone();
                    Check(index == zoneCount && zone.Objects.Count == zoneCount + 1 && zone.Dirty, string.Format("appended as ID {0} ({1} objects, table dirty, {2} -> {3} meshes)", index, zone.Objects.Count, meshesBefore, zone.Models.Count));
                    Check(browser.EnsureInZone() == index && zone.Objects.Count == zoneCount + 1, "a second use returns the same ID, no duplicate");

                    ZSC.Object copy = zone.Objects[index];
                    ZSC.Object src = foreign.Table.Zsc.Objects[foreign.Index];
                    bool samePaths = copy.Models.Count == src.Models.Count;
                    for (int i = 0; samePaths && i < copy.Models.Count; i++)
                        samePaths = string.Compare(zone.Models[copy.Models[i].ModelID], foreign.Table.Zsc.Models[src.Models[i].ModelID], true) == 0 &&
                                    string.Compare(zone.Textures[copy.Models[i].TextureID].Path, foreign.Table.Zsc.Textures[src.Models[i].TextureID].Path, true) == 0;
                    Check(samePaths, "the copy's parts resolve to the source's mesh and texture paths");

                    // Save to a scratch copy and read it back with both readers.
                    string saved = Path.Combine(scratch, Path.GetFileName(decoPath));
                    string original = zone.FilePath;
                    zone.FilePath = saved;
                    zone.Save();
                    zone.FilePath = original;
                    ZSC back = new ZSC(saved);
                    Check(back.Objects.Count == zoneCount + 1 && back.Models.Count == zone.Models.Count && !zone.Dirty, string.Format("saved table reads back with {0} objects, {1} meshes", back.Objects.Count, back.Models.Count));
                    ZscRaw rawBack = new ZscRaw(File.ReadAllBytes(saved));
                    ZscRaw rawOriginal = new ZscRaw(File.ReadAllBytes(original));
                    bool prefix = rawBack.Objects.Count == rawOriginal.Objects.Count + 1;
                    for (int i = 0; prefix && i < rawOriginal.Objects.Count; i++)
                        prefix = ZscRaw.Same(rawOriginal.Objects[i].Cylinder, rawBack.Objects[i].Cylinder) && rawOriginal.Objects[i].Parts.Count == rawBack.Objects[i].Parts.Count;
                    for (int i = 0; prefix && i < rawOriginal.Meshes.Count; i++)
                        prefix = ZscRaw.Same(rawOriginal.Meshes[i], rawBack.Meshes[i]);
                    Check(prefix, "every original object and mesh keeps its index and bytes");
                }

                // Layout picture.
                browser.Measure(new System.Windows.Size(300, 470));
                browser.Arrange(new System.Windows.Rect(0, 0, 300, 470));
                Pump(200);
                System.Windows.Media.Imaging.RenderTargetBitmap shot = new System.Windows.Media.Imaging.RenderTargetBitmap(300, 470, 96, 96, System.Windows.Media.PixelFormats.Pbgra32);
                shot.Render(browser);
                System.Windows.Media.Imaging.PngBitmapEncoder png = new System.Windows.Media.Imaging.PngBitmapEncoder();
                png.Frames.Add(System.Windows.Media.Imaging.BitmapFrame.Create(shot));
                using (FileStream fs = File.Create(Path.Combine(scratch, "browser.png")))
                    png.Save(fs);
                Check(true, "browser layout in browser.png");

                Console.WriteLine("Rotation editor");
                RotationEditor editor = new RotationEditor();
                editor.SnapCombo.SelectedIndex = 0;
                editor.SetRotation(Rotation.FromDegrees(90, 0, 0));
                Check(editor.YawBox.Text == "90" && editor.PitchBox.Text == "0", string.Format("90 degrees yaw shows as yaw {0} pitch {1} roll {2}", editor.YawBox.Text, editor.PitchBox.Text, editor.RollBox.Text));
                int committed = 0;
                Quaternion last = Quaternion.Identity;
                editor.RotationCommitted += delegate(Quaternion q) { committed++; last = q; };
                editor.YawBox.Text = "45";
                editor.CommitTyped();
                Vector3 degrees = Rotation.ToDegrees(editor.Rotation);
                Check(committed == 1 && Math.Abs(degrees.X - 45) < 0.01f, string.Format("typing 45 commits once; rotation reads back yaw {0:0.##}", degrees.X));
                editor.SnapCombo.SelectedIndex = 3;
                Check(editor.SnapStep == 90.0f && editor.YawSlider.IsSnapToTickEnabled, "90 degree snap sets the slider ticks");
                editor.SnapCombo.SelectedIndex = 0;
                ConfigurationManager.SetValue("Placement", "YawSnap", 0);
                ConfigurationManager.SaveConfig();

                editor.Measure(new System.Windows.Size(300, 120));
                editor.Arrange(new System.Windows.Rect(0, 0, 300, 120));
                System.Windows.Media.Imaging.RenderTargetBitmap shot2 = new System.Windows.Media.Imaging.RenderTargetBitmap(300, 120, 96, 96, System.Windows.Media.PixelFormats.Pbgra32);
                shot2.Render(editor);
                System.Windows.Media.Imaging.PngBitmapEncoder png2 = new System.Windows.Media.Imaging.PngBitmapEncoder();
                png2.Frames.Add(System.Windows.Media.Imaging.BitmapFrame.Create(shot2));
                using (FileStream fs = File.Create(Path.Combine(scratch, "rotation.png")))
                    png2.Save(fs);
            }
            catch (Exception e)
            {
                uiError = e;
            }
        });
        ui.SetApartmentState(ApartmentState.STA);
        ui.Start();
        ui.Join();
        Check(uiError == null, "browser and rotation editor run without exceptions" + (uiError != null ? ": " + uiError : ""));

        Console.WriteLine("Rotation maths");
        string rotation = Rotation.SelfTest();
        Check(rotation == null, "round trips" + (rotation != null ? ": " + rotation : ""));

        Console.WriteLine(failures == 0 ? "all passed" : failures + " failed");
        return failures == 0 ? 0 : 1;
    }
}
