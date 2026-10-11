using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using Map_Editor.Engine;
using Map_Editor.Engine.Models;
using Map_Editor.Engine.RenderManager;
using Map_Editor.Misc;

namespace Map_Editor.Forms.Controls
{
    /// <summary>
    /// The object palette shared by the decoration and construction tools: a
    /// searchable grid of thumbnails over the open zone's table, or over every
    /// table LIST_ZONE names. Picking an object from another table copies it
    /// into the zone's table (<see cref="ZSC.AppendFrom"/>) the moment it is
    /// used, never on browsing.
    ///
    /// Thumbnails come from <see cref="ObjectThumbnails"/> as they are made;
    /// nothing here waits for them, so an object can be picked by name before
    /// its picture exists.
    /// </summary>
    public partial class ObjectBrowser : UserControl
    {
        public const int MAX_SHOWN = 300;

        public static readonly Brush COLOUR_NORMAL = new SolidColorBrush(Color.FromRgb(201, 210, 225));
        public static readonly Brush COLOUR_HOVER = new SolidColorBrush(Color.FromRgb(225, 201, 201));
        public static readonly Brush COLOUR_SELECTED = new SolidColorBrush(Color.FromRgb(170, 54, 54));
        public static readonly Brush COLOUR_FOREIGN = new SolidColorBrush(Color.FromRgb(248, 244, 232));

        /// <summary>An object of the zone's table was clicked (index in that table).</summary>
        public event Action<int> ZoneModelSelected;

        /// <summary>
        /// An object was double-clicked: it is in the zone's table now (appended if
        /// it came from another one) and the tool should start placing it.
        /// </summary>
        public event Action<int> ModelActivated;

        private ZSC zoneTable;
        private string zoneTablePath;
        private string kind;
        private readonly List<ZscCatalog.Entry> shownEntries = new List<ZscCatalog.Entry>();
        private readonly Dictionary<Border, ZscCatalog.Entry> tiles = new Dictionary<Border, ZscCatalog.Entry>();
        private Border selectedTile;
        private ZscCatalog.Entry selectedEntry;
        private readonly DispatcherTimer searchTimer;
        private List<ZscCatalog.Entry> allEntries;
        private List<ZscCatalog.Entry> zoneEntries;
        private bool loadingAll;

        private const string SEARCH_HINT = "Search objects (name, folder, #id)";
        private bool showingSearchHint;
        private bool settingSearchHint;

        public ObjectBrowser()
        {
            InitializeComponent();

            searchTimer = new DispatcherTimer();
            searchTimer.Interval = TimeSpan.FromMilliseconds(180);
            searchTimer.Tick += delegate { searchTimer.Stop(); Refill(); };

            SearchBox.TextChanged += SearchBox_TextChanged;
            SearchBox.KeyDown += SearchBox_KeyDown;
            SearchBox.GotFocus += delegate { HideSearchHint(); };
            SearchBox.LostFocus += delegate { ShowSearchHintIfEmpty(); };
            ShowSearchHintIfEmpty();
        }

        /// <summary>The search field (a WinForms box, see the XAML).</summary>
        public System.Windows.Forms.TextBox SearchBox
        {
            get { return (System.Windows.Forms.TextBox)SearchHost.Child; }
        }

        /// <summary>What the user typed; empty while the grey hint is shown.</summary>
        public string SearchText
        {
            get { return showingSearchHint ? string.Empty : SearchBox.Text; }
        }

        private void ShowSearchHintIfEmpty()
        {
            if (SearchBox.Text.Length > 0 && !showingSearchHint)
                return;
            settingSearchHint = true;
            try
            {
                showingSearchHint = true;
                SearchBox.ForeColor = System.Drawing.Color.Gray;
                SearchBox.Text = SEARCH_HINT;
            }
            finally
            {
                settingSearchHint = false;
            }
        }

        private void HideSearchHint()
        {
            if (!showingSearchHint)
                return;
            settingSearchHint = true;
            try
            {
                showingSearchHint = false;
                SearchBox.ForeColor = System.Drawing.SystemColors.WindowText;
                SearchBox.Text = string.Empty;
            }
            finally
            {
                settingSearchHint = false;
            }
        }

        /// <summary>The entry under the highlight, or null.</summary>
        public ZscCatalog.Entry Selected
        {
            get { return selectedEntry; }
        }

        /// <summary>The entries currently shown as tiles, in display order.</summary>
        public IList<ZscCatalog.Entry> ShownEntries
        {
            get { return shownEntries.AsReadOnly(); }
        }

        /// <summary>Highlights a shown entry as a click would (used by the tests).</summary>
        public bool Select(ZscCatalog.Entry entry)
        {
            foreach (KeyValuePair<Border, ZscCatalog.Entry> kv in tiles)
            {
                if (kv.Value == entry)
                {
                    Highlight(kv.Key, kv.Value, true);
                    return true;
                }
            }
            return false;
        }

        /// <summary>True while the "All zones" tables are still being read.</summary>
        public bool IsLoadingAll
        {
            get { return loadingAll; }
        }

        /// <summary>The picture a tile shows (used by the tests to see thumbnails arrive).</summary>
        public ImageSource TileImage(ZscCatalog.Entry entry)
        {
            foreach (KeyValuePair<Border, ZscCatalog.Entry> kv in tiles)
                if (kv.Value == entry)
                    return ((Image)((StackPanel)kv.Key.Child).Children[0]).Source;
            return null;
        }

        /// <summary>The highlighted object's index in the zone's table, or -1 when it is from another table.</summary>
        public int SelectedZoneIndex
        {
            get
            {
                if (selectedEntry == null)
                    return -1;
                return selectedEntry.Table.IsCurrent && selectedEntry.Table.Zsc == zoneTable ? selectedEntry.Index : -1;
            }
        }

        /// <summary>Binds the browser to the open zone's table of the given kind.</summary>
        public void Initialize(ZSC table, string tablePath, string tableKind)
        {
            zoneTable = table;
            zoneTablePath = tablePath;
            kind = tableKind;
            zoneEntries = null;
            allEntries = null;

            bool all = false;
            try { all = ConfigurationManager.GetValue<bool>("Placement", "BrowseAllTables"); }
            catch { }
            Scope.SelectedIndex = all ? 1 : 0;

            Refill();
        }

        /// <summary>Highlights the object with this index in the zone's table and scrolls to it.</summary>
        public void SelectZoneIndex(int index)
        {
            foreach (KeyValuePair<Border, ZscCatalog.Entry> kv in tiles)
            {
                if (kv.Value.Table.Zsc == zoneTable && kv.Value.Index == index)
                {
                    Highlight(kv.Key, kv.Value, false);
                    kv.Key.BringIntoView();
                    return;
                }
            }

            // Not among the shown tiles (filtered out): show it alone.
            if (zoneTable != null && index >= 0 && index < zoneTable.Objects.Count)
            {
                ZscCatalog.Table t = CurrentTable();
                if (t != null)
                {
                    HideSearchHint();
                    SearchBox.Text = "#" + index;
                    searchTimer.Stop();
                    Refill();
                    foreach (KeyValuePair<Border, ZscCatalog.Entry> kv in tiles)
                    {
                        if (kv.Value.Index == index && kv.Value.Table.Zsc == zoneTable)
                        {
                            Highlight(kv.Key, kv.Value, false);
                            return;
                        }
                    }
                }
            }
        }

        /// <summary>
        /// Makes sure the highlighted object is in the zone's table, appending it
        /// from its own table if needed, and returns its index there (-1 when
        /// nothing is highlighted or the copy failed).
        /// </summary>
        public int EnsureInZone()
        {
            if (selectedEntry == null || zoneTable == null)
                return -1;

            if (selectedEntry.Table.Zsc == zoneTable)
                return selectedEntry.Index;

            try
            {
                int before = zoneTable.Objects.Count;
                int index = zoneTable.AppendFrom(selectedEntry.Table.Zsc, selectedEntry.Index);

                if (zoneTable.Objects.Count > before)
                {
                    Output.WriteLine(Output.MessageType.Event, string.Format("Copied {0} (ID {1} of {2}) into {3} as ID {4}; the table is saved with the map",
                        selectedEntry.Name, selectedEntry.Index, selectedEntry.Table.Name, System.IO.Path.GetFileName(zoneTablePath), index));
                    zoneEntries = null;
                    if (allEntries != null)
                    {
                        ZscCatalog.Table t = CurrentTable();
                        if (t != null)
                            allEntries.Add(ZscCatalog.MakeEntry(t, index));
                    }
                }
                else
                {
                    Output.WriteLine(Output.MessageType.Normal, string.Format("{0} is already ID {1} of {2}", selectedEntry.Name, index, System.IO.Path.GetFileName(zoneTablePath)));
                }

                // Re-point the highlight at the zone's copy.
                ZscCatalog.Table current = CurrentTable();
                if (current != null)
                    selectedEntry = ZscCatalog.MakeEntry(current, index);
                UpdateForeignHint();
                return index;
            }
            catch (Exception ex)
            {
                Output.WriteException("Copying the object into the zone's table", ex);
                MessageBox.Show("The object could not be copied into this zone's table:\n\n" + ex.Message, "Object browser", MessageBoxButton.OK, MessageBoxImage.Error);
                return -1;
            }
        }

        private ZscCatalog.Table CurrentTable()
        {
            foreach (ZscCatalog.Table t in Tables())
                if (t.Zsc == zoneTable)
                    return t;
            return null;
        }

        private List<ZscCatalog.Table> Tables()
        {
            ZSC deco = FileManager.ZSCs.ContainsKey("Decoration") ? FileManager.ZSCs["Decoration"] : null;
            ZSC cnst = FileManager.ZSCs.ContainsKey("Construction") ? FileManager.ZSCs["Construction"] : null;
            string decoPath = deco != null ? deco.FilePath : null;
            string cnstPath = cnst != null ? cnst.FilePath : null;
            List<ZscCatalog.Table> list = ZscCatalog.Tables(deco, decoPath, cnst, cnstPath);

            // A zone whose table LIST_ZONE does not list (a placeholder) still gets
            // its own entry so the "This zone" scope has something to show.
            bool found = false;
            foreach (ZscCatalog.Table t in list)
                if (t.Zsc == zoneTable)
                    found = true;
            if (!found && zoneTable != null)
            {
                list = new List<ZscCatalog.Table>(list);
                list.Insert(0, new ZscCatalog.Table()
                {
                    Key = ZscCatalog.Normalize(zoneTablePath),
                    Path = zoneTablePath ?? string.Empty,
                    Name = ZscCatalog.TableName(zoneTablePath ?? "this zone"),
                    Kind = kind,
                    Zsc = zoneTable,
                    IsCurrent = true
                });
            }
            return list;
        }

        #region Filling

        private void Refill()
        {
            long uiStart = Engine.FrameStats.Start();
            try
            {
                RefillCore();
            }
            finally
            {
                Engine.FrameStats.Add("ui", uiStart);
            }
        }

        private void RefillCore()
        {
            ObjectThumbnails.CancelAll();
            Grid.Children.Clear();
            tiles.Clear();
            shownEntries.Clear();
            selectedTile = null;

            if (zoneTable == null)
            {
                Status.Text = "No table loaded";
                return;
            }

            List<ZscCatalog.Entry> source;
            if (Scope.SelectedIndex == 1)
            {
                if (allEntries == null)
                {
                    BeginLoadingAll();
                    Status.Text = "Reading every zone's tables...";
                    return;
                }
                source = allEntries;
            }
            else
            {
                if (zoneEntries == null)
                {
                    ZscCatalog.Table t = CurrentTable();
                    zoneEntries = t != null ? ZscCatalog.Entries(t) : new List<ZscCatalog.Entry>();
                }
                source = zoneEntries;
            }

            string[] tokens = ZscCatalog.Tokens(SearchText);
            int matches = 0;
            foreach (ZscCatalog.Entry e in source)
            {
                if (tokens.Length > 0 && !ZscCatalog.Matches(e, tokens))
                    continue;
                matches++;
                if (shownEntries.Count < MAX_SHOWN)
                    shownEntries.Add(e);
            }

            if (Scope.SelectedIndex == 1)
            {
                // Objects of the open zone first, then by name.
                shownEntries.Sort(delegate(ZscCatalog.Entry a, ZscCatalog.Entry b)
                {
                    bool ca = a.Table.Zsc == zoneTable, cb = b.Table.Zsc == zoneTable;
                    if (ca != cb) return ca ? -1 : 1;
                    int n = string.Compare(a.Name, b.Name, true);
                    if (n != 0) return n;
                    n = string.Compare(a.Table.Name, b.Table.Name, true);
                    return n != 0 ? n : a.Index.CompareTo(b.Index);
                });
            }

            foreach (ZscCatalog.Entry e in shownEntries)
                AddTile(e);

            if (matches > shownEntries.Count)
                Status.Text = string.Format("{0} matches, showing the first {1}. Narrow the search.", matches, shownEntries.Count);
            else if (tokens.Length > 0)
                Status.Text = string.Format("{0} of {1} objects match", matches, source.Count);
            else
                Status.Text = string.Format("{0} objects{1}", source.Count, Scope.SelectedIndex == 1 ? " in every zone's tables" : " in this zone's table");

            // Keep the previous highlight if it is still shown.
            if (selectedEntry != null)
            {
                foreach (KeyValuePair<Border, ZscCatalog.Entry> kv in tiles)
                {
                    if (kv.Value.Table == selectedEntry.Table && kv.Value.Index == selectedEntry.Index)
                    {
                        Highlight(kv.Key, kv.Value, false);
                        break;
                    }
                }
            }
            Scroller.ScrollToTop();
        }

        private void BeginLoadingAll()
        {
            if (loadingAll)
                return;
            loadingAll = true;

            List<ZscCatalog.Table> tables = Tables();
            System.Threading.Thread thread = new System.Threading.Thread(delegate()
            {
                List<ZscCatalog.Entry> entries = new List<ZscCatalog.Entry>();
                DateTime start = DateTime.Now;
                foreach (ZscCatalog.Table t in tables)
                {
                    try
                    {
                        entries.AddRange(ZscCatalog.Entries(t));
                    }
                    catch (Exception ex)
                    {
                        Output.WriteLine(Output.MessageType.Error, string.Format("Object browser: {0}: {1}", t.Path, ex.Message));
                    }
                }
                Output.WriteLine(Output.MessageType.Normal, string.Format("Object browser: {0} objects in {1} tables read in {2:0.0} s", entries.Count, tables.Count, (DateTime.Now - start).TotalSeconds));

                Dispatcher.BeginInvoke(DispatcherPriority.Normal, (DispatcherOperationCallback)delegate
                {
                    allEntries = ZscCatalog.Collapse(entries, zoneTable);
                    Output.WriteLine(Output.MessageType.Normal, string.Format("Object browser: {0} distinct objects after folding copies shared between tables", allEntries.Count));
                    loadingAll = false;
                    if (Scope.SelectedIndex == 1)
                        Refill();
                    return null;
                }, null);
            });
            thread.IsBackground = true;
            thread.Start();
        }

        private void AddTile(ZscCatalog.Entry entry)
        {
            bool foreign = entry.Table.Zsc != zoneTable;

            Image image = new Image()
            {
                Width = ObjectThumbnails.SIZE,
                Height = ObjectThumbnails.SIZE,
                Source = ObjectThumbnails.Placeholder(),
                SnapsToDevicePixels = true
            };

            TextBlock caption = new TextBlock()
            {
                Text = entry.Name,
                FontSize = 10,
                TextTrimming = TextTrimming.CharacterEllipsis,
                TextAlignment = TextAlignment.Center,
                Margin = new Thickness(2, 1, 2, 1),
                Foreground = new SolidColorBrush(Color.FromRgb(60, 66, 76))
            };

            TextBlock table = new TextBlock()
            {
                Text = (foreign ? entry.Table.Name : "#" + entry.Index) + (entry.AlsoIn.Count > 0 ? string.Format(" (+{0})", entry.AlsoIn.Count) : string.Empty),
                FontSize = 9,
                TextTrimming = TextTrimming.CharacterEllipsis,
                TextAlignment = TextAlignment.Center,
                Margin = new Thickness(2, 0, 2, 2),
                Foreground = new SolidColorBrush(foreign ? Color.FromRgb(160, 110, 30) : Color.FromRgb(140, 148, 160))
            };

            StackPanel stack = new StackPanel();
            stack.Children.Add(image);
            stack.Children.Add(caption);
            stack.Children.Add(table);

            Border tile = new Border()
            {
                BorderBrush = COLOUR_NORMAL,
                BorderThickness = new Thickness(1),
                Margin = new Thickness(4, 4, 0, 0),
                Width = ObjectThumbnails.SIZE + 2,
                Background = foreign ? COLOUR_FOREIGN : Brushes.White,
                SnapsToDevicePixels = true,
                Cursor = Cursors.Hand,
                ToolTip = entry.Tooltip,
                Child = stack
            };

            tile.MouseEnter += Tile_MouseEnter;
            tile.MouseLeave += Tile_MouseLeave;
            tile.MouseLeftButtonDown += Tile_MouseLeftButtonDown;

            tiles.Add(tile, entry);
            Grid.Children.Add(tile);

            Image captured = image;
            ObjectThumbnails.Request(entry.Table.Zsc, entry.Table.Path, entry.Index, delegate(BitmapSource picture)
            {
                long uiStart = Engine.FrameStats.Start();
                captured.Source = picture;
                Engine.FrameStats.Add("ui", uiStart);
            });
        }

        #endregion

        #region Tile events

        private void Tile_MouseEnter(object sender, MouseEventArgs e)
        {
            Border tile = (Border)sender;
            if (tile != selectedTile)
                tile.BorderBrush = COLOUR_HOVER;
        }

        private void Tile_MouseLeave(object sender, MouseEventArgs e)
        {
            Border tile = (Border)sender;
            if (tile != selectedTile)
                tile.BorderBrush = COLOUR_NORMAL;
        }

        private void Tile_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
        {
            Border tile = (Border)sender;
            ZscCatalog.Entry entry;
            if (!tiles.TryGetValue(tile, out entry))
                return;

            Highlight(tile, entry, true);

            if (e.ClickCount == 2)
            {
                int index = EnsureInZone();
                if (index >= 0 && ModelActivated != null)
                    ModelActivated(index);
                e.Handled = true;
            }
        }

        private void Highlight(Border tile, ZscCatalog.Entry entry, bool raise)
        {
            if (selectedTile != null)
            {
                selectedTile.BorderBrush = COLOUR_NORMAL;
                selectedTile.BorderThickness = new Thickness(1);
            }
            selectedTile = tile;
            selectedEntry = entry;
            tile.BorderBrush = COLOUR_SELECTED;
            tile.BorderThickness = new Thickness(2);

            UpdateForeignHint();

            if (raise && ZoneModelSelected != null && entry.Table.Zsc == zoneTable)
                ZoneModelSelected(entry.Index);
        }

        private void UpdateForeignHint()
        {
            if (selectedEntry != null && selectedEntry.Table.Zsc != zoneTable)
            {
                ForeignHintText.Text = string.Format("{0} is not in this zone's table yet (it comes from {1}). Double-click it, or press Add, to copy it into {2} as a new ID and start placing it. The table is written when you save the map; re-bake the client's data afterwards.",
                    selectedEntry.Name, selectedEntry.Table.Name, System.IO.Path.GetFileName(zoneTablePath ?? string.Empty));
                ForeignHint.Visibility = Visibility.Visible;
            }
            else
                ForeignHint.Visibility = Visibility.Collapsed;
        }

        #endregion

        #region Search box

        private void SearchBox_TextChanged(object sender, EventArgs e)
        {
            if (settingSearchHint)
                return;
            if (showingSearchHint)
            {
                // Text set from code (the tests, SelectZoneIndex) while the hint showed.
                showingSearchHint = false;
                SearchBox.ForeColor = System.Drawing.SystemColors.WindowText;
            }
            searchTimer.Stop();
            searchTimer.Start();
        }

        private void SearchBox_KeyDown(object sender, System.Windows.Forms.KeyEventArgs e)
        {
            if (e.KeyCode == System.Windows.Forms.Keys.Escape)
            {
                SearchBox.Text = string.Empty;
                e.SuppressKeyPress = true;
                e.Handled = true;
            }
            else if (e.KeyCode == System.Windows.Forms.Keys.Enter)
            {
                searchTimer.Stop();
                Refill();
                e.SuppressKeyPress = true;
                e.Handled = true;
            }
        }

        private void Scope_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            if (!IsLoaded && zoneTable == null)
                return;
            try
            {
                ConfigurationManager.SetValue("Placement", "BrowseAllTables", Scope.SelectedIndex == 1);
                ConfigurationManager.SaveConfig();
            }
            catch
            {
            }
            if (zoneTable != null)
                Refill();
        }

        #endregion
    }
}
