using System;
using System.Windows;
using System.Windows.Controls;
using Map_Editor.Engine;
using Map_Editor.Engine.Map;
using Map_Editor.Engine.Models;
using Map_Editor.Engine.Tools;
using Map_Editor.Misc;
using Map_Editor.Misc.Properties;
using Microsoft.Xna.Framework;

namespace Map_Editor.Forms.Controls
{
    /// <summary>
    /// Side panel of the construction tool: the object browser (search across
    /// every zone's table, thumbnails made once and cached), placement options,
    /// rotation in degrees and the property grid.
    /// </summary>
    public partial class ConstructionTool : UserControl, IObjectToolPanel
    {
        private const string TABLE_KEY = "Construction";

        /// <summary>
        /// Gets the properties.
        /// </summary>
        /// <value>The properties.</value>
        public System.Windows.Forms.PropertyGrid Properties
        {
            get { return (System.Windows.Forms.PropertyGrid)PropertiesHost.Child; }
        }

        #region Static Members

        /// <summary>
        /// Gets or sets the copied object.
        /// </summary>
        /// <value>The copied object.</value>
        public static IFO.BaseIFO CopiedObject { get; set; }

        /// <summary>The table the copied object's ID belongs to, so a paste into another zone is refused.</summary>
        public static string CopiedTable { get; set; }

        #endregion

        #region Member Declarations

        /// <summary>
        /// The model picked in the browser, as an index into this zone's table (-1 = none).
        /// </summary>
        public int Model { get; set; }

        /// <summary>
        /// Gets or sets the selected object.
        /// </summary>
        /// <value>The selected object.</value>
        private int selectedObject { get; set; }

        private bool settingUp;

        #endregion

        /// <summary>
        /// Initializes a new instance of the <see cref="ConstructionTool"/> class.
        /// </summary>
        public ConstructionTool()
        {
            InitializeComponent();

            Model = -1;
            selectedObject = -1;

            settingUp = true;
            DrawBoundingBoxes.IsChecked = ConfigurationManager.GetValue<bool>(TABLE_KEY, "DrawBoundingBoxes");
            KeepPlacingBox.IsChecked = true;
            try
            {
                RandomYawBox.IsChecked = ConfigurationManager.GetValue<bool>("Placement", "RandomYaw");
                ScaleJitterBox.IsChecked = ConfigurationManager.GetValue<bool>("Placement", "ScaleJitter");
                AlignToSlopeBox.IsChecked = ConfigurationManager.GetValue<bool>("Placement", "AlignToSlope");
                KeepPlacingBox.IsChecked = ConfigurationManager.GetValue<bool>("Placement", "KeepPlacing");
            }
            catch
            {
            }
            settingUp = false;

            ZSC table = FileManager.ZSCs[TABLE_KEY];
            Browser.Initialize(table, table.FilePath, TABLE_KEY);
            Browser.ZoneModelSelected += Browser_ZoneModelSelected;
            Browser.ModelActivated += Browser_ModelActivated;

            Rotation.RotationChanged += Rotation_RotationChanged;
            Rotation.RotationCommitted += Rotation_RotationCommitted;
            Rotation.SetEnabled(false);
        }

        #region IObjectToolPanel

        public bool IsCloning
        {
            get { return Clone.IsChecked == true; }
        }

        public void PlacementEnded()
        {
            if (Add.IsChecked == true)
                Add.IsChecked = false;
            if (Clone.IsChecked == true)
                Clone.IsChecked = false;
        }

        public bool RandomYaw
        {
            get { return RandomYawBox.IsChecked == true; }
        }

        public bool ScaleJitter
        {
            get { return ScaleJitterBox.IsChecked == true; }
        }

        public bool AlignToSlope
        {
            get { return AlignToSlopeBox.IsChecked == true; }
        }

        public float YawSnapStep
        {
            get { return Rotation.SnapStep; }
        }

        public bool KeepPlacing
        {
            get { return KeepPlacingBox.IsChecked == true; }
        }

        public void ShowMode(string text, bool placing)
        {
            ModeText.Text = text;
            ModeBanner.Background = placing ? new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(255, 244, 214)) : new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(238, 242, 247));
            ModeBanner.BorderBrush = placing ? new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(228, 201, 121)) : new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(201, 210, 224));
            StopButton.Visibility = placing ? Visibility.Visible : Visibility.Collapsed;
        }

        private void Stop_Click(object sender, RoutedEventArgs e)
        {
            PlacementEnded();
        }

        #endregion

        private Engine.Tools.Object Tool
        {
            get { return MapManager.Construction.Tool; }
        }

        /// <summary>
        /// Handles the Click event of the DrawBoundingBoxes control.
        /// </summary>
        private void DrawBoundingBoxes_Click(object sender, RoutedEventArgs e)
        {
            ConfigurationManager.SetValue(TABLE_KEY, "DrawBoundingBoxes", DrawBoundingBoxes.IsChecked);
            ConfigurationManager.SaveConfig();
        }

        private void Placement_Click(object sender, RoutedEventArgs e)
        {
            if (settingUp)
                return;
            ConfigurationManager.SetValue("Placement", "RandomYaw", RandomYawBox.IsChecked == true);
            ConfigurationManager.SetValue("Placement", "ScaleJitter", ScaleJitterBox.IsChecked == true);
            ConfigurationManager.SetValue("Placement", "AlignToSlope", AlignToSlopeBox.IsChecked == true);
            ConfigurationManager.SetValue("Placement", "KeepPlacing", KeepPlacingBox.IsChecked == true);
            ConfigurationManager.SaveConfig();
        }

        /// <summary>
        /// Selects the specified object (a placement in the world).
        /// </summary>
        public int Select(int index)
        {
            selectedObject = index;

            Add.IsChecked = false;
            Remove.IsEnabled = false;
            Clone.IsEnabled = false;
            Clone.IsChecked = false;
            RemoveLightmap.IsEnabled = false;

            IFO.BaseIFO ifoEntry = MapManager.Construction.WorldObjects[index].Entry;

            Model = ifoEntry.ObjectID;
            Browser.SelectZoneIndex(ifoEntry.ObjectID);

            Rotation.SetRotation(ifoEntry.Rotation);
            Rotation.SetEnabled(true);

            Properties.SelectedObject = new ObjectProperty()
            {
                Description = ifoEntry.Description,
                EventID = ifoEntry.EventID,
                Position = ifoEntry.Position,
                Rotation = ifoEntry.Rotation,
                Scale = ifoEntry.Scale
            };

            Remove.IsEnabled = true;
            Clone.IsEnabled = true;
            RemoveLightmap.IsEnabled = true;

            App.Form.Cut.IsEnabled = true;
            App.Form.QuickCut.IsEnabled = true;

            App.Form.Copy.IsEnabled = true;
            App.Form.QuickCopy.IsEnabled = true;

            UpdatePasteEnabled();

            return index;
        }

        /// <summary>
        /// Points the browser at a model of this zone's table (undo / redo of a model change).
        /// </summary>
        public void SelectModel(int index)
        {
            Model = index;
            Browser.SelectZoneIndex(index);
        }

        /// <summary>
        /// Cleans this instance.
        /// </summary>
        public void Clean()
        {
            Remove.IsEnabled = false;
            Clone.IsEnabled = false;
            Clone.IsChecked = false;
            RemoveLightmap.IsEnabled = false;

            App.Form.Cut.IsEnabled = false;
            App.Form.QuickCut.IsEnabled = false;

            App.Form.Copy.IsEnabled = false;
            App.Form.QuickCopy.IsEnabled = false;

            UpdatePasteEnabled();

            Properties.SelectedObject = null;

            Rotation.SetRotation(Quaternion.Identity);
            Rotation.SetEnabled(false);

            selectedObject = -1;
        }

        /// <summary>
        /// Paste creates a new object, so it only needs something copied from this
        /// zone's table, not a selection.
        /// </summary>
        public void UpdatePasteEnabled()
        {
            bool can = CopiedObject != null && CopiedTable == ZscCatalog.Normalize(FileManager.ZSCs[TABLE_KEY].FilePath);
            App.Form.Paste.IsEnabled = can;
            App.Form.QuickPaste.IsEnabled = can;
        }

        #region Browser events

        private void Browser_ZoneModelSelected(int index)
        {
            Model = index;

            if (!Add.IsEnabled)
                Add.IsEnabled = true;

            // While placing, or with a placement selected, picking another object
            // swaps the model (the old behaviour of clicking a thumbnail).
            if (Remove.IsEnabled || Add.IsChecked == true)
                Tool.ChangeModel(Model);
        }

        private void Browser_ModelActivated(int index)
        {
            Model = index;
            Add.IsEnabled = true;

            if (Add.IsChecked == true)
                Tool.ChangeModel(Model);
            else
                Add.IsChecked = true;
        }

        #endregion

        #region Button Events

        private void Add_Checked(object sender, RoutedEventArgs e)
        {
            if (Clone.IsChecked == true)
                Clone.IsChecked = false;

            int index = Browser.EnsureInZone();
            if (index < 0)
                index = Model;
            if (index < 0)
            {
                Add.IsChecked = false;
                return;
            }

            Model = index;
            Tool.StartAdding(Model);
        }

        private void Add_Unchecked(object sender, RoutedEventArgs e)
        {
            Tool.StopAdding();
        }

        private void Remove_Click(object sender, RoutedEventArgs e)
        {
            Tool.Remove(false);
        }

        private void Clone_Checked(object sender, RoutedEventArgs e)
        {
            if (Add.IsChecked == true)
                Add.IsChecked = false;

            if (selectedObject < 0)
            {
                Clone.IsChecked = false;
                return;
            }

            Model = MapManager.Construction.WorldObjects[selectedObject].Entry.ObjectID;
            Tool.StartAdding(Model);
        }

        private void Clone_Unchecked(object sender, RoutedEventArgs e)
        {
            Tool.StopAdding();
        }

        private void RemoveLightmap_Click(object sender, RoutedEventArgs e)
        {
            Tool.RemoveLightmaps();
        }

        #endregion

        /// <summary>
        /// Handles the PropertyValueChanged event of the Properties control.
        /// </summary>
        private void Properties_PropertyValueChanged(object s, System.Windows.Forms.PropertyValueChangedEventArgs e)
        {
            if (selectedObject < 0)
                return;

            ObjectProperty objectValues = (ObjectProperty)Properties.SelectedObject;

            IFO.BaseIFO ifoEntry = MapManager.Construction.WorldObjects[selectedObject].Entry;

            UndoManager.AddCommand(new Engine.Commands.Construction.ValueChanged()
            {
                ObjectID = selectedObject,
                Object = MapManager.Construction.WorldObjects[selectedObject],
                OldValue = new Engine.Commands.Construction.ValueChanged.ObjectValue()
                {
                    Description = ifoEntry.Description,
                    EventID = ifoEntry.EventID,
                    Position = ifoEntry.Position,
                    Rotation = ifoEntry.Rotation,
                    Scale = ifoEntry.Scale
                },
                NewValue = new Engine.Commands.Construction.ValueChanged.ObjectValue()
                {
                    Description = objectValues.Description,
                    EventID = objectValues.EventID,
                    Position = objectValues.Position,
                    Rotation = objectValues.Rotation,
                    Scale = objectValues.Scale
                }
            });

            ifoEntry.Description = objectValues.Description;
            ifoEntry.EventID = objectValues.EventID;

            Tool.ChangeWorld(objectValues.Position, objectValues.Rotation, objectValues.Scale);
            Rotation.SetRotation(objectValues.Rotation);
        }

        #region Rotation events

        private void Rotation_RotationChanged(Quaternion rotation)
        {
            if (selectedObject < 0)
                return;

            IFO.BaseIFO ifoEntry = MapManager.Construction.WorldObjects[selectedObject].Entry;
            Tool.ChangeWorld(ifoEntry.Position, rotation, ifoEntry.Scale);
        }

        private void Rotation_RotationCommitted(Quaternion rotation)
        {
            if (selectedObject < 0 || Properties.SelectedObject == null)
                return;

            ObjectProperty objectValues = (ObjectProperty)Properties.SelectedObject;
            IFO.BaseIFO ifoEntry = MapManager.Construction.WorldObjects[selectedObject].Entry;

            if (objectValues.Rotation == rotation)
                return;

            UndoManager.AddCommand(new Engine.Commands.Construction.ValueChanged()
            {
                ObjectID = selectedObject,
                Object = MapManager.Construction.WorldObjects[selectedObject],
                OldValue = new Engine.Commands.Construction.ValueChanged.ObjectValue()
                {
                    Description = objectValues.Description,
                    EventID = objectValues.EventID,
                    Position = objectValues.Position,
                    Rotation = objectValues.Rotation,
                    Scale = objectValues.Scale
                },
                NewValue = new Engine.Commands.Construction.ValueChanged.ObjectValue()
                {
                    Description = ifoEntry.Description,
                    EventID = ifoEntry.EventID,
                    Position = ifoEntry.Position,
                    Rotation = rotation,
                    Scale = ifoEntry.Scale
                }
            });

            Tool.ChangeWorld(ifoEntry.Position, rotation, ifoEntry.Scale);

            objectValues.Rotation = rotation;
            Properties.Refresh();
        }

        #endregion
    }
}
