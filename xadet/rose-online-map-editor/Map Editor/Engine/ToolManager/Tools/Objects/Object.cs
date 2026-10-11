using System;
using System.Collections.Generic;
using System.Windows.Forms;
using Map_Editor.Engine.Map;
using Map_Editor.Engine.Models;
using Map_Editor.Engine.RenderManager;
using Map_Editor.Engine.Tools.Interfaces;
using Map_Editor.Forms.Controls;
using Map_Editor.Misc.Properties;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Microsoft.Xna.Framework.Input;
using Map_Editor.Engine.SpriteManager;

namespace Map_Editor.Engine.Tools
{
    /// <summary>
    /// What the object tool needs from its side panel (decoration and
    /// construction share one implementation).
    /// </summary>
    public interface IObjectToolPanel
    {
        /// <summary>True while the Clone toggle is down (placing copies of the selection).</summary>
        bool IsCloning { get; }

        /// <summary>Placing finished (one-shot click or Escape): release the Add / Clone toggles.</summary>
        void PlacementEnded();

        bool RandomYaw { get; }
        bool ScaleJitter { get; }
        bool AlignToSlope { get; }

        /// <summary>Yaw step in degrees for the mouse wheel while placing; 0 = free.</summary>
        float YawSnapStep { get; }

        /// <summary>Stay in placing mode after each click (Shift+click does the opposite).</summary>
        bool KeepPlacing { get; }

        /// <summary>Shows the tool's mode line in the panel; <paramref name="placing"/> shows the Stop button.</summary>
        void ShowMode(string text, bool placing);
    }

    /// <summary>
    /// Object class.
    /// </summary>
    public class Object : ITool
    {
        /// <summary>
        /// Type of object.
        /// </summary>
        public enum ObjectType
        {
            /// <summary>
            /// Decoration
            /// </summary>
            Decoration,

            /// <summary>
            /// Construction
            /// </summary>
            Construction
        }

        #region Member Declarations

        /// <summary>
        /// Gets or sets the type.
        /// </summary>
        /// <value>The type.</value>
        public ObjectType Type { get; set; }

        /// <summary>
        /// Gets or sets the device.
        /// </summary>
        /// <value>The device.</value>
        private GraphicsDevice device { get; set; }

        /// <summary>
        /// Gets or sets the basic effect.
        /// </summary>
        /// <value>The basic effect.</value>
        private BasicEffect basicEffect { get; set; }

        /// <summary>
        /// Gets or sets the hovered object.
        /// </summary>
        /// <value>The hovered object.</value>
        private int hoveredObject { get; set; }

        /// <summary>
        /// Gets or sets the selected object.
        /// </summary>
        /// <value>The selected object.</value>
        public int SelectedObject { get; private set; }

        /// <summary>
        /// Gets or sets the position command.
        /// </summary>
        /// <value>The position command.</value>
        private Commands.Interfaces.ICommand positionCommand { get; set; }

        #region Adding Related

        /// <summary>
        /// Gets or sets the model.
        /// </summary>
        /// <value>The model.</value>
        private int model { get; set; }

        /// <summary>
        /// Gets or sets the world model.
        /// </summary>
        /// <value>The world model.</value>
        private Objects.Object.WorldObject worldModel { get; set; }

        /// <summary>
        /// Gets or sets the object manager.
        /// </summary>
        /// <value>The object manager.</value>
        private ObjectManager objectManager { get; set; }

        /// <summary>
        /// Gets or sets the texture manager.
        /// </summary>
        /// <value>The texture manager.</value>
        private TextureManager textureManager { get; set; }

        /// <summary>
        /// Gets or sets the picked position.
        /// </summary>
        /// <value>The picked position.</value>
        private Vector3 pickedPosition { get; set; }

        /// <summary>
        /// Gets or sets a value indicating whether [mouse down].
        /// </summary>
        /// <value><c>true</c> if [mouse down]; otherwise, <c>false</c>.</value>
        private bool mouseDown { get; set; }

        /// <summary>Heading of the object being placed, degrees about Z.</summary>
        private float placeYaw;

        /// <summary>Uniform scale of the object being placed.</summary>
        private float placeScale = 1.0f;

        private int lastWheel;
        private bool wheelPrimed;
        private bool escapeDown;
        private bool leftWasDown;
        private readonly Random random = new Random();
        private string lastMode;

        /// <summary>
        /// Says what the tool is doing and what the next click does, in the 3D view,
        /// the status bar and the panel. The panel and status bar are only touched
        /// when the text changes.
        /// </summary>
        private void PublishMode()
        {
            IObjectToolPanel panel = Panel;
            ZSC zsc = FileManager.ZSCs[Type.ToString()];
            string text;
            Color colour;
            bool placing = model >= 0;

            if (placing)
            {
                bool keep = panel != null && panel.KeepPlacing;
                text = string.Format("PLACING {0}  -  click the map to put it there  |  mouse wheel turns it  |  {1}  |  Esc stops",
                    Models.ZscCatalog.ObjectName(zsc, model),
                    keep ? "every click places another (Shift+click: just this one)" : "one click places one (Shift+click keeps placing)");
                colour = new Color(255, 230, 150);
            }
            else if (SelectedObject >= 0)
            {
                List<Objects.Object.WorldObject> worldObjects = (Type == ObjectType.Decoration) ? MapManager.Decoration.WorldObjects : MapManager.Construction.WorldObjects;
                int id = worldObjects[SelectedObject].Entry.ObjectID;
                text = string.Format("SELECTED {0} (object {1})  -  drag the arrows to move  |  Rotate in the panel  |  Delete removes  |  Add or double-click in the panel places another  |  click empty ground to deselect",
                    Models.ZscCatalog.ObjectName(zsc, id), id);
                colour = Color.White;
            }
            else
            {
                text = string.Format("{0} tool  -  click an object on the map to select it  |  double-click an object in the panel to place it", Type);
                colour = new Color(200, 210, 225);
            }

            SpriteManager.HudManager.SetStatus(text, colour);

            if (text != lastMode)
            {
                lastMode = text;
                if (panel != null)
                    panel.ShowMode(text.Replace("  -  ", ". ").Replace("  |  ", ". "), placing);
                try
                {
                    App.Form.StatusText.Text = text;
                }
                catch
                {
                }
            }
        }

        #endregion

        #endregion

        private IObjectToolPanel Panel
        {
            get { return App.Form.ToolHost.Content as IObjectToolPanel; }
        }

        /// <summary>
        /// Initializes a new instance of the <see cref="Object"/> class.
        /// </summary>
        /// <param name="device">The device.</param>
        public Object(GraphicsDevice device)
        {
            this.device = device;
            model = -1;

            basicEffect = new BasicEffect(device, null);

            SelectedObject = -1;
            hoveredObject = -1;
        }

        #region Adding Related

        /// <summary>
        /// Starts the adding process.
        /// </summary>
        /// <param name="model">The model.</param>
        public void StartAdding(int model)
        {
            this.model = model;

            objectManager = new ObjectManager(device, ZMS.Vertex.VertexElements, ZMS.Vertex.SIZE_IN_BYTES);
            textureManager = new TextureManager(device);

            ZSC.Object zscObject = FileManager.ZSCs[Type.ToString()].Objects[model];

            worldModel = new Objects.Object.WorldObject()
            {
                Entry = null,
                FileID = 0,
                EntryID = 0,
                World = Matrix.Identity,
                Parts = new List<Objects.Object.WorldObject.Part>(zscObject.Models.Count),
            };

            for (int i = 0; i < zscObject.Models.Count; i++)
            {
                int modelID = -1;

                if (zscObject.Models[i].Motion != null)
                    modelID = objectManager.Add(FileManager.ZSCs[Type.ToString()].Models[zscObject.Models[i].ModelID], zscObject.Models[i].Motion);
                else
                    modelID = objectManager.Add(FileManager.ZSCs[Type.ToString()].Models[zscObject.Models[i].ModelID]);

                if (modelID == -1)
                    return;

                Matrix world = Matrix.CreateFromQuaternion(zscObject.Models[i].Rotation) *
                               Matrix.CreateScale(zscObject.Models[i].Scale) *
                               Matrix.CreateTranslation(zscObject.Models[i].Position);

                worldModel.Parts.Add(new Objects.Object.WorldObject.Part()
                {
                    TextureID = textureManager.Add(FileManager.ZSCs[Type.ToString()].Textures[zscObject.Models[i].TextureID]),
                    ModelID = modelID,
                    Position = zscObject.Models[i].Position,
                    Scale = zscObject.Models[i].Scale,
                    Rotation = zscObject.Models[i].Rotation,
                    LightmapEnabled = false,
                    BoundingBox = objectManager.CreateBox(modelID, world)   // object space, once
                });
            }

            worldModel.Add(objectManager, model);

            Cursor.Current = Cursors.Default;

            hoveredObject = -1;

            RollPlacement();
            wheelPrimed = false;

            // The ghost follows the mouse only while the map has the focus (see
            // MouseStateExtensions.Intersects); take it now rather than after a click.
            App.Form.RenderPanel.Focus();
        }

        /// <summary>
        /// Stops the adding process.
        /// </summary>
        public void StopAdding()
        {
            model = -1;
        }

        /// <summary>
        /// Leaves placing mode and tells the panel to release its toggles.
        /// </summary>
        private void StopPlacing()
        {
            StopAdding();
            IObjectToolPanel panel = Panel;
            if (panel != null)
                panel.PlacementEnded();
        }

        /// <summary>
        /// Picks the heading and scale of the next placed copy: random when the
        /// panel asks for it, otherwise the heading stays whatever the wheel set.
        /// </summary>
        private void RollPlacement()
        {
            IObjectToolPanel panel = Panel;
            if (panel != null && panel.RandomYaw)
                placeYaw = Rotation.Wrap((float)(random.NextDouble() * 360.0));
            placeScale = (panel != null && panel.ScaleJitter) ? 0.9f + (float)random.NextDouble() * 0.2f : 1.0f;
        }

        private Vector3 TerrainNormal(Vector3 at)
        {
            const float d = 0.5f;
            float x1, x2, y1, y2;
            if (!MapManager.Heightmaps.TryGetHeight(at.X - d, at.Y, out x1) || !MapManager.Heightmaps.TryGetHeight(at.X + d, at.Y, out x2) ||
                !MapManager.Heightmaps.TryGetHeight(at.X, at.Y - d, out y1) || !MapManager.Heightmaps.TryGetHeight(at.X, at.Y + d, out y2))
                return Vector3.UnitZ;

            Vector3 n = new Vector3(-(x2 - x1) / (2.0f * d), -(y2 - y1) / (2.0f * d), 1.0f);
            n.Normalize();
            return n;
        }

        /// <summary>The rotation a new copy gets at <paramref name="at"/>.</summary>
        private Quaternion PlacementRotation(Vector3 at)
        {
            IObjectToolPanel panel = Panel;
            if (panel != null && panel.AlignToSlope)
                return Rotation.OnSlope(TerrainNormal(at), placeYaw);
            return Rotation.Yaw(placeYaw);
        }

        /// <summary>
        /// Adds a new placement to the block under <paramref name="position"/> and
        /// returns its index in the world list, or -1 when no block file covers
        /// that spot.
        /// </summary>
        private int Place(Vector3 position, int objectID, Quaternion rotation, Vector3 scale, string description, short eventID, short warpID, IFO.ObjectType objectType)
        {
            int fileID = MapManager.InsideFile(position);
            if (fileID < 0)
            {
                Map_Editor.Misc.Output.WriteLine(Map_Editor.Misc.Output.MessageType.Error, string.Format("No block file covers ({0:0.0}, {1:0.0}); the object was not placed", position.X, position.Y));
                return -1;
            }

            Vector2 fileBlock = MapManager.InsideBlock(position);
            List<IFO.BaseIFO> list = (Type == ObjectType.Decoration) ? FileManager.IFOs[fileID].Decoration : FileManager.IFOs[fileID].Construction;
            int entryID = list.Count;

            IFO.BaseIFO newObject = new IFO.BaseIFO()
            {
                Description = description ?? string.Empty,
                WarpID = warpID,
                EventID = eventID,
                ObjectID = objectID,
                ObjectType = objectType,
                MapPosition = new Vector2()
                {
                    X = (int)MapManager.MapPosition(fileBlock, position).X,
                    Y = (int)MapManager.MapPosition(fileBlock, position).Y
                },
                Position = position,
                Rotation = rotation,
                Scale = scale,
                Parent = FileManager.IFOs[fileID]
            };

            list.Add(newObject);

            switch (Type)
            {
                case ObjectType.Decoration:
                    MapManager.Decoration.Add(list[entryID], fileID, entryID);
                    UndoManager.AddCommand(new Commands.Decoration.Added()
                    {
                        ObjectID = MapManager.Decoration.WorldObjects.Count - 1,
                        Object = MapManager.Decoration.WorldObjects[MapManager.Decoration.WorldObjects.Count - 1],
                        File = fileID,
                        Entry = newObject
                    });
                    return MapManager.Decoration.WorldObjects.Count - 1;
                case ObjectType.Construction:
                    MapManager.Construction.Add(list[entryID], fileID, entryID);
                    UndoManager.AddCommand(new Commands.Construction.Added()
                    {
                        ObjectID = MapManager.Construction.WorldObjects.Count - 1,
                        Object = MapManager.Construction.WorldObjects[MapManager.Construction.WorldObjects.Count - 1],
                        File = fileID,
                        Entry = newObject
                    });
                    return MapManager.Construction.WorldObjects.Count - 1;
            }
            return -1;
        }

        /// <summary>
        /// Pastes a copied placement as a new object: under the mouse when it is
        /// over the map, else two metres beside the original. The copy is
        /// selected afterwards.
        /// </summary>
        public void PasteNew(IFO.BaseIFO copied)
        {
            if (copied == null)
                return;

            ZSC zsc = FileManager.ZSCs[Type.ToString()];
            if (copied.ObjectID < 0 || copied.ObjectID >= zsc.Objects.Count)
            {
                Map_Editor.Misc.Output.WriteLine(Map_Editor.Misc.Output.MessageType.Error, string.Format("The copied object (ID {0}) is not in this zone's table; nothing pasted", copied.ObjectID));
                return;
            }

            if (model >= 0)
                StopPlacing();

            Vector3 position = Vector3.Zero;
            if (Mouse.GetState().Intersects(device.Viewport))
                position = MapManager.Heightmaps.PickPosition();

            if (position == Vector3.Zero)
            {
                position = copied.Position + new Vector3(2.0f, 0.0f, 0.0f);
                float here, there;
                if (MapManager.Heightmaps.TryGetHeight(copied.Position.X, copied.Position.Y, out there) && MapManager.Heightmaps.TryGetHeight(position.X, position.Y, out here))
                    position.Z = here + (copied.Position.Z - there);
            }

            int index = Place(position, copied.ObjectID, copied.Rotation, copied.Scale, copied.Description, copied.EventID, copied.WarpID, copied.ObjectType);
            if (index >= 0)
            {
                Deselect();
                SelectedObject = Select(index);
            }
        }

        #endregion

        #region Selecting and Editing Related

        /// <summary>
        /// Selects the specified object.
        /// </summary>
        /// <param name="index">The index.</param>
        /// <returns></returns>
        public int Select(int index)
        {
            // Select used to add these handlers on every call and never remove
            // them, so each selection ran every earlier selection's handlers too.
            Unsubscribe();

            switch (Type)
            {
                case ObjectType.Decoration:
                    {
                        ToolManager.Cursor.Position = MapManager.Decoration.WorldObjects[index].Entry.Position;

                        ToolManager.Cursor.PositionChanged += new EventHandler(Cursor_PositionChanged);
                        ToolManager.Cursor.Cancelled += new EventHandler(Cursor_Cancelled);
                        ToolManager.Cursor.Finished += new EventHandler(Cursor_Finished);

                        ToolManager.Position.BoundingBox = MapManager.Decoration.WorldObjects[index].BoundingBox;
                        ToolManager.Position.Position = ToolManager.Position.RealPosition = MapManager.Decoration.WorldObjects[index].Entry.Position;

                        ToolManager.Position.MouseReleased += new System.EventHandler(Translate_MouseReleased);
                        ToolManager.Position.PositionChanged += new EventHandler(Translate_PositionChanged);

                        ToolManager.Position.FirstTime = true;

                        ToolManager.Position.Update();

                        return ((DecorationTool)App.Form.ToolHost.Content).Select(index);
                    }
                case ObjectType.Construction:
                    {
                        ToolManager.Cursor.Position = MapManager.Construction.WorldObjects[index].Entry.Position;

                        ToolManager.Cursor.PositionChanged += new EventHandler(Cursor_PositionChanged);
                        ToolManager.Cursor.Cancelled += new EventHandler(Cursor_Cancelled);
                        ToolManager.Cursor.Finished += new EventHandler(Cursor_Finished);

                        ToolManager.Position.BoundingBox = MapManager.Construction.WorldObjects[index].BoundingBox;
                        ToolManager.Position.Position = ToolManager.Position.RealPosition = MapManager.Construction.WorldObjects[index].Entry.Position;

                        ToolManager.Position.MouseReleased += new EventHandler(Translate_MouseReleased);
                        ToolManager.Position.PositionChanged += new EventHandler(Translate_PositionChanged);

                        ToolManager.Position.FirstTime = true;

                        ToolManager.Position.Update();

                        return ((ConstructionTool)App.Form.ToolHost.Content).Select(index);
                    }
            }

            return -1;
        }

        private void Unsubscribe()
        {
            ToolManager.Cursor.PositionChanged -= new EventHandler(Cursor_PositionChanged);
            ToolManager.Cursor.Cancelled -= new EventHandler(Cursor_Cancelled);
            ToolManager.Cursor.Finished -= new EventHandler(Cursor_Finished);
            ToolManager.Position.MouseReleased -= new EventHandler(Translate_MouseReleased);
            ToolManager.Position.PositionChanged -= new EventHandler(Translate_PositionChanged);
        }

        /// <summary>
        /// Drops the selection (a click on empty ground).
        /// </summary>
        public void Deselect()
        {
            if (SelectedObject < 0)
                return;

            Unsubscribe();
            SelectedObject = -1;
            hoveredObject = -1;
            positionCommand = null;

            switch (Type)
            {
                case ObjectType.Decoration:
                    ((DecorationTool)App.Form.ToolHost.Content).Clean();
                    break;
                case ObjectType.Construction:
                    ((ConstructionTool)App.Form.ToolHost.Content).Clean();
                    break;
            }

            ToolManager.Cursor.Position = Vector3.Zero;
            ToolManager.Position.BoundingBox = new BoundingBox();
            ToolManager.Position.Position = Vector3.Zero;
        }

        /// <summary>
        /// Changes the model.
        /// </summary>
        /// <param name="model">The model.</param>
        public void ChangeModel(int model)
        {
            if (this.model >= 0)
                StartAdding(model);
            else if (SelectedObject >= 0)
            {
                List<Objects.Object.WorldObject> worldObjects = (Type == ObjectType.Decoration) ? MapManager.Decoration.WorldObjects : MapManager.Construction.WorldObjects;

                if (worldObjects[SelectedObject].Entry.ObjectID != model)
                {
                    switch (Type)
                    {
                        case ObjectType.Decoration:
                            {
                                UndoManager.AddCommand(new Commands.Decoration.ObjectChanged()
                                {
                                    Object = worldObjects[SelectedObject],
                                    ObjectID  = SelectedObject,
                                    OldObject = worldObjects[SelectedObject].Entry.ObjectID,
                                    NewObject = model
                                });

                                worldObjects[SelectedObject].Entry.ObjectID = model;

                                MapManager.Decoration.Add(SelectedObject, worldObjects[SelectedObject].Entry, worldObjects[SelectedObject].FileID, worldObjects[SelectedObject].EntryID, true);
                            }
                            break;
                        case ObjectType.Construction:
                            {
                                UndoManager.AddCommand(new Commands.Construction.ObjectChanged()
                                {
                                    Object = worldObjects[SelectedObject],
                                    ObjectID = SelectedObject,
                                    OldObject = worldObjects[SelectedObject].Entry.ObjectID,
                                    NewObject = model
                                });

                                worldObjects[SelectedObject].Entry.ObjectID = model;

                                MapManager.Construction.Add(SelectedObject, worldObjects[SelectedObject].Entry, worldObjects[SelectedObject].FileID, worldObjects[SelectedObject].EntryID, true);
                            }
                            break;
                    }
                }
            }
        }

        /// <summary>
        /// Removes the selected object.
        /// </summary>
        /// <param name="undoAction">if set to <c>true</c> [undo action].</param>
        public void Remove(bool undoAction)
        {
            switch (Type)
            {
                case ObjectType.Decoration:
                    {
                        MapManager.Decoration.RemoveAt(SelectedObject, undoAction);

                        ((DecorationTool)App.Form.ToolHost.Content).Clean();
                    }
                    break;
                case ObjectType.Construction:
                    {
                        MapManager.Construction.RemoveAt(SelectedObject, undoAction);

                        ((ConstructionTool)App.Form.ToolHost.Content).Clean();
                    }
                    break;
            }

            ToolManager.Cursor.Position = Vector3.Zero;

            ToolManager.Position.BoundingBox = new BoundingBox();
            ToolManager.Position.Position = Vector3.Zero;

            SelectedObject = -1;
        }

        /// <summary>
        /// Changes the world.
        /// </summary>
        /// <param name="position">The position.</param>
        /// <param name="rotation">The rotation.</param>
        /// <param name="scale">The scale.</param>
        public void ChangeWorld(Vector3 position, Quaternion rotation, Vector3 scale)
        {
            if (SelectedObject >= 0)
            {
                List<Objects.Object.WorldObject> worldObjects = (Type == ObjectType.Decoration) ? MapManager.Decoration.WorldObjects : MapManager.Construction.WorldObjects;

                worldObjects[SelectedObject].Entry.Position = position;
                worldObjects[SelectedObject].Entry.Rotation = rotation;
                worldObjects[SelectedObject].Entry.Scale = scale;

                switch (Type)
                {
                    case ObjectType.Decoration:
                        MapManager.Decoration.Add(SelectedObject, worldObjects[SelectedObject].Entry, worldObjects[SelectedObject].FileID, worldObjects[SelectedObject].EntryID, true);
                        break;
                    case ObjectType.Construction:
                        MapManager.Construction.Add(SelectedObject, worldObjects[SelectedObject].Entry, worldObjects[SelectedObject].FileID, worldObjects[SelectedObject].EntryID, true);
                        break;
                }

                ToolManager.Cursor.Position = worldObjects[SelectedObject].Entry.Position;

                ToolManager.Position.BoundingBox = worldObjects[SelectedObject].BoundingBox;
                ToolManager.Position.Position = worldObjects[SelectedObject].Entry.Position;
            }
        }

        /// <summary>
        /// Removes the lightmaps.
        /// </summary>
        public void RemoveLightmaps()
        {
            List<Objects.Object.WorldObject> worldObjects = (Type == ObjectType.Decoration) ? MapManager.Decoration.WorldObjects : MapManager.Construction.WorldObjects;

            LIT blockLIT = (Type == ObjectType.Decoration) ? FileManager.DecorationLITs[worldObjects[SelectedObject].FileID] : FileManager.ConstructionLITs[worldObjects[SelectedObject].FileID];
            int objectID = blockLIT.SearchObject(worldObjects[SelectedObject].EntryID + 1);

            if (objectID == -1)
                return;

            switch (Type)
            {
                case ObjectType.Decoration:
                    {
                        UndoManager.AddCommand(new Commands.Decoration.LightmapRemoved()
                        {
                            ObjectID = SelectedObject,
                            Object = worldObjects[SelectedObject],
                            LightmapObject = blockLIT.Objects[objectID]
                        });
                    }
                    break;
                case ObjectType.Construction:
                    {
                        UndoManager.AddCommand(new Commands.Construction.LightmapRemoved()
                        {
                            ObjectID = SelectedObject,
                            Object = worldObjects[SelectedObject],
                            LightmapObject = blockLIT.Objects[objectID]
                        });
                    }
                    break;
            }

            blockLIT.Objects.RemoveAt(objectID);

            switch (Type)
            {
                case ObjectType.Decoration:
                    MapManager.Decoration.Add(SelectedObject, worldObjects[SelectedObject].Entry, worldObjects[SelectedObject].FileID, worldObjects[SelectedObject].EntryID, true);
                    break;
                case ObjectType.Construction:
                    MapManager.Construction.Add(SelectedObject, worldObjects[SelectedObject].Entry, worldObjects[SelectedObject].FileID, worldObjects[SelectedObject].EntryID, true);
                    break;
            }
        }

        #endregion

        #region Manipulation Events

        /// <summary>
        /// Handles the PositionChanged event of the Cursor control.
        /// </summary>
        /// <param name="sender">The source of the event.</param>
        /// <param name="e">The <see cref="System.EventArgs"/> instance containing the event data.</param>
        private void Cursor_PositionChanged(object sender, EventArgs e)
        {
            List<Objects.Object.WorldObject> worldObjects = (Type == ObjectType.Decoration) ? MapManager.Decoration.WorldObjects : MapManager.Construction.WorldObjects;

            if (positionCommand == null)
            {
                switch (Type)
                {
                    case ObjectType.Decoration:
                        {
                            positionCommand = new Commands.Decoration.Positioned()
                            {
                                OldPosition = worldObjects[SelectedObject].Entry.Position,
                                ObjectID = SelectedObject
                            };
                        }
                        break;
                    case ObjectType.Construction:
                        {
                            positionCommand = new Commands.Construction.Positioned()
                            {
                                OldPosition = worldObjects[SelectedObject].Entry.Position,
                                ObjectID = SelectedObject
                            };
                        }
                        break;
                }                
            }

            Vector3 realPosition = worldObjects[SelectedObject].Entry.Position;

            ChangeWorld(ToolManager.Cursor.Position, worldObjects[SelectedObject].Entry.Rotation, worldObjects[SelectedObject].Entry.Scale);

            worldObjects[SelectedObject].Entry.Position = realPosition;
        }

        /// <summary>
        /// Handles the Cancelled event of the Cursor control.
        /// </summary>
        /// <param name="sender">The source of the event.</param>
        /// <param name="e">The <see cref="System.EventArgs"/> instance containing the event data.</param>
        private void Cursor_Cancelled(object sender, EventArgs e)
        {
            List<Objects.Object.WorldObject> worldObjects = (Type == ObjectType.Decoration) ? MapManager.Decoration.WorldObjects : MapManager.Construction.WorldObjects;

            ChangeWorld(worldObjects[SelectedObject].Entry.Position, worldObjects[SelectedObject].Entry.Rotation, worldObjects[SelectedObject].Entry.Scale);

            positionCommand = null;
        }

        /// <summary>
        /// Handles the Finished event of the Cursor control.
        /// </summary>
        /// <param name="sender">The source of the event.</param>
        /// <param name="e">The <see cref="System.EventArgs"/> instance containing the event data.</param>
        private void Cursor_Finished(object sender, EventArgs e)
        {
            List<Objects.Object.WorldObject> worldObjects = (Type == ObjectType.Decoration) ? MapManager.Decoration.WorldObjects : MapManager.Construction.WorldObjects;

            ChangeWorld(ToolManager.Cursor.Position, worldObjects[SelectedObject].Entry.Rotation, worldObjects[SelectedObject].Entry.Scale);

            switch (Type)
            {
                case ObjectType.Decoration:
                    {
                        ((ObjectProperty)((DecorationTool)App.Form.ToolHost.Content).Properties.SelectedObject).Position = MapManager.Decoration.WorldObjects[SelectedObject].Entry.Position;
                        ((DecorationTool)App.Form.ToolHost.Content).Properties.Refresh();

                        if (positionCommand == null)
                            return;

                        ((Commands.Decoration.Positioned)positionCommand).NewPosition = ToolManager.Position.Position;
                        ((Commands.Decoration.Positioned)positionCommand).Object = MapManager.Decoration.WorldObjects[SelectedObject];

                        UndoManager.AddCommand(positionCommand);
                    }
                    break;
                case ObjectType.Construction:
                    {
                        ((ObjectProperty)((ConstructionTool)App.Form.ToolHost.Content).Properties.SelectedObject).Position = MapManager.Construction.WorldObjects[SelectedObject].Entry.Position;
                        ((ConstructionTool)App.Form.ToolHost.Content).Properties.Refresh();

                        if (positionCommand == null)
                            return;

                        ((Commands.Construction.Positioned)positionCommand).NewPosition = ToolManager.Position.Position;
                        ((Commands.Construction.Positioned)positionCommand).Object = MapManager.Construction.WorldObjects[SelectedObject];

                        UndoManager.AddCommand(positionCommand);
                    }
                    break;
            }

            positionCommand = null;
        }

        /// <summary>
        /// Handles the PositionChanged event of the Translate control.
        /// </summary>
        /// <param name="sender">The source of the event.</param>
        /// <param name="e">The <see cref="System.EventArgs"/> instance containing the event data.</param>
        private void Translate_PositionChanged(object sender, EventArgs e)
        {
            List<Objects.Object.WorldObject> worldObjects = (Type == ObjectType.Decoration) ? MapManager.Decoration.WorldObjects : MapManager.Construction.WorldObjects;
            
            if (positionCommand == null)
            {
                switch (Type)
                {
                    case ObjectType.Decoration:
                        {
                            positionCommand = new Commands.Decoration.Positioned()
                            {
                                OldPosition = worldObjects[SelectedObject].Entry.Position,
                                ObjectID = SelectedObject
                            };
                        }
                        break;
                    case ObjectType.Construction:
                        {
                            positionCommand = new Commands.Construction.Positioned()
                            {
                                OldPosition = worldObjects[SelectedObject].Entry.Position,
                                ObjectID = SelectedObject
                            };
                        }
                        break;
                }
            }

            worldObjects[SelectedObject].Entry.Position = ToolManager.Position.Position;

            ChangeWorld(worldObjects[SelectedObject].Entry.Position, worldObjects[SelectedObject].Entry.Rotation, worldObjects[SelectedObject].Entry.Scale);
        }

        /// <summary>
        /// Handles the MouseReleased event of the Translate control.
        /// </summary>
        /// <param name="sender">The source of the event.</param>
        /// <param name="e">The <see cref="System.EventArgs"/> instance containing the event data.</param>
        private void Translate_MouseReleased(object sender, EventArgs e)
        {
            switch (Type)
            {
                case ObjectType.Decoration:
                    {
                        ((ObjectProperty)((DecorationTool)App.Form.ToolHost.Content).Properties.SelectedObject).Position = MapManager.Decoration.WorldObjects[SelectedObject].Entry.Position;
                        ((DecorationTool)App.Form.ToolHost.Content).Properties.Refresh();

                        if (positionCommand == null)
                            return;

                        ((Commands.Decoration.Positioned)positionCommand).NewPosition = ToolManager.Position.Position;
                        ((Commands.Decoration.Positioned)positionCommand).Object = MapManager.Decoration.WorldObjects[SelectedObject];

                        UndoManager.AddCommand(positionCommand);

                        positionCommand = null;
                    }
                    break;
                case ObjectType.Construction:
                    {
                        ((ObjectProperty)((ConstructionTool)App.Form.ToolHost.Content).Properties.SelectedObject).Position = MapManager.Construction.WorldObjects[SelectedObject].Entry.Position;
                        ((ConstructionTool)App.Form.ToolHost.Content).Properties.Refresh();
                        
                        if (positionCommand == null)
                            return;

                        ((Commands.Construction.Positioned)positionCommand).NewPosition = ToolManager.Position.Position;
                        ((Commands.Construction.Positioned)positionCommand).Object = MapManager.Construction.WorldObjects[SelectedObject];

                        UndoManager.AddCommand(positionCommand);

                        positionCommand = null;
                    }
                    break;
            }
        }

        #endregion

        /// <summary>
        /// Updates the tool.
        /// </summary>
        /// <param name="gameTime">The game time.</param>
        public void Update(GameTime gameTime)
        {
            KeyboardState keyboardState = Keyboard.GetState();
            MouseState mouseState = Mouse.GetState();

            PublishMode();

            bool escape = keyboardState.IsKeyDown(Microsoft.Xna.Framework.Input.Keys.Escape);
            bool escapePressed = escape && !escapeDown;
            escapeDown = escape;

            // Escape leaves placing mode wherever the mouse is.
            if (model >= 0 && escapePressed)
            {
                StopPlacing();
                return;
            }

            bool inViewport = mouseState.Intersects(device.Viewport);
            bool leftDown = mouseState.LeftButton == Microsoft.Xna.Framework.Input.ButtonState.Pressed;

            // The thumbnail worker yields while the map is being worked on.
            ObjectThumbnails.Busy = model >= 0 || (leftDown && inViewport);
            bool leftPressed = leftDown && !leftWasDown && inViewport;
            leftWasDown = leftDown;

            // The keyboard is polled, not routed, so Delete is only honoured while
            // the mouse is over the map: typing in a panel field must not delete.
            if (SelectedObject >= 0 && inViewport && keyboardState.IsKeyDown(Microsoft.Xna.Framework.Input.Keys.Delete))
                Remove(false);

            if (!inViewport)
            {
                wheelPrimed = false;
                return;
            }

            if (model >= 0)
            {
                objectManager.Update(gameTime);

                // The wheel turns the ghost: one snap step per notch, 5 degrees when
                // snapping is off.
                if (!wheelPrimed)
                {
                    lastWheel = mouseState.ScrollWheelValue;
                    wheelPrimed = true;
                }
                int notches = (mouseState.ScrollWheelValue - lastWheel) / 120;
                if (notches != 0)
                {
                    lastWheel += notches * 120;
                    IObjectToolPanel panel = Panel;
                    float step = (panel != null && panel.YawSnapStep > 0.0f) ? panel.YawSnapStep : 5.0f;
                    placeYaw = Rotation.Snap(placeYaw + notches * step, (panel != null) ? panel.YawSnapStep : 0.0f);
                }

                if (leftDown && !mouseDown)
                {
                    mouseDown = true;

                    bool cloning = Panel != null && Panel.IsCloning && SelectedObject >= 0;
                    List<Objects.Object.WorldObject> source = (Type == ObjectType.Decoration) ? MapManager.Decoration.WorldObjects : MapManager.Construction.WorldObjects;

                    int placed;
                    if (cloning)
                    {
                        IFO.BaseIFO from = source[SelectedObject].Entry;
                        placed = Place(pickedPosition, model, from.Rotation, from.Scale, from.Description, from.EventID, from.WarpID, from.ObjectType);
                    }
                    else
                        placed = Place(pickedPosition, model, PlacementRotation(pickedPosition), new Vector3(placeScale, placeScale, placeScale), string.Empty, 0, 0, IFO.ObjectType.User);

                    bool shift = keyboardState.IsKeyDown(Microsoft.Xna.Framework.Input.Keys.LeftShift) || keyboardState.IsKeyDown(Microsoft.Xna.Framework.Input.Keys.RightShift);
                    bool keepPlacing = (Panel != null && Panel.KeepPlacing) != shift;

                    if (placed >= 0)
                    {
                        string name = Models.ZscCatalog.ObjectName(FileManager.ZSCs[Type.ToString()], model);
                        SpriteManager.HudManager.Notice(string.Format("Placed {0} here{1}.", name, keepPlacing ? "; click again to place another, Esc to stop" : "; it is selected now"), 4.0f);
                    }

                    if (keepPlacing)
                        RollPlacement();
                    else
                    {
                        // One click places one object and selects it, ready to adjust.
                        StopPlacing();
                        if (placed >= 0)
                        {
                            Deselect();
                            SelectedObject = Select(placed);
                        }
                    }
                }
                else if (!leftDown && mouseDown)
                    mouseDown = false;

                return;
            }

            if (ToolManager.GetManipulationMode() == ToolManager.ManipulationMode.Position)
            {
                if (!ToolManager.Position.Update())
                    return;
            }
            else if (ToolManager.GetManipulationMode() == ToolManager.ManipulationMode.Cursor)
            {
                ToolManager.Cursor.Update();

                if (ToolManager.Cursor.Position != Vector3.Zero)
                    return;
            }

            List<Objects.Object.WorldObject> worldObjects = (Type == ObjectType.Decoration) ? MapManager.Decoration.WorldObjects : MapManager.Construction.WorldObjects;
            List<int> mouseSelections = new List<int>();

            BoundingFrustum boundingFrustum = new BoundingFrustum(CameraManager.View * CameraManager.Projection);
            Ray pickRay = new Ray().Create(device, mouseState, CameraManager.View, CameraManager.Projection);

            for (int i = 0; i < worldObjects.Count; i++)
            {
                if (boundingFrustum.OnScreen(worldObjects[i].BoundingBox) && pickRay.Intersects(worldObjects[i].BoundingBox).HasValue)
                    mouseSelections.Add(i);
            }

            if (mouseSelections.Count == 0)
            {
                Cursor.Current = Cursors.Default;

                hoveredObject = -1;

                // A click on empty ground drops the selection.
                if (leftPressed)
                    Deselect();

                return;
            }

            int closestObject = mouseSelections[0];
            float currentDistance = Vector3.Distance(CameraManager.Position, worldObjects[closestObject].BoundingBox.GetCenter());

            for (int i = 0; i < mouseSelections.Count; i++)
            {
                float distance = Vector3.Distance(CameraManager.Position, worldObjects[mouseSelections[i]].BoundingBox.GetCenter());

                if (distance > currentDistance)
                    continue;

                closestObject = mouseSelections[i];
                currentDistance = distance;
            }

            if (leftPressed && closestObject != SelectedObject)
                SelectedObject = Select(closestObject);
            else
                hoveredObject = closestObject;

            if (hoveredObject != SelectedObject && hoveredObject >= 0)
            {
                ToolTipManager.Set(string.Format("Object ID: {0}", worldObjects[hoveredObject].Entry.ObjectID), worldObjects[hoveredObject].BoundingBox.GetCenter());

                Cursor.Current = Cursors.Hand;
            }
        }

        /// <summary>
        /// Draws the bounding boxes.
        /// </summary>
        /// <param name="drawBoundingBoxes">if set to <c>true</c> [draw bounding boxes].</param>
        public void Draw(bool drawBoundingBoxes)
        {
            if (model >= 0)
            {
                long pickStart = FrameStats.Start();
                pickedPosition = MapManager.Heightmaps.PickPosition();
                FrameStats.Add("pick", pickStart);

                long ghostStart = FrameStats.Start();
                objectManager.ClearBatch();

                worldModel.World = Matrix.Identity;

                IObjectToolPanel panel = Panel;
                if (panel != null && panel.IsCloning && SelectedObject >= 0)
                {
                    List<Objects.Object.WorldObject> source = (Type == ObjectType.Decoration) ? MapManager.Decoration.WorldObjects : MapManager.Construction.WorldObjects;
                    worldModel.World *= Matrix.CreateFromQuaternion(source[SelectedObject].Entry.Rotation);
                    worldModel.World *= Matrix.CreateScale(source[SelectedObject].Entry.Scale);
                }
                else
                {
                    // The ghost shows the heading, slope and scale the click will give.
                    worldModel.World *= Matrix.CreateFromQuaternion(PlacementRotation(pickedPosition));
                    worldModel.World *= Matrix.CreateScale(placeScale);
                }

                worldModel.World *= Matrix.CreateTranslation(pickedPosition);

                worldModel.Add(objectManager, model);

                Effect shader = ShaderManager.GetShader(ShaderManager.ShaderType.Object);

                shader.SetValue("MasterLightmapEnabled", false);
                shader.Start("Object");

                objectManager.Draw(textureManager, shader, false);

                shader.Finish();

                // The ghost is marked as such: a green box and a label, so it is never
                // mistaken for a placed object. Each part's object-space box was made
                // once in StartAdding; only its eight corners move per frame.
                BoundingBox ghostBox = new BoundingBox();
                bool any = false;
                Vector3[] corners = new Vector3[8];
                foreach (Objects.Object.WorldObject.Part part in worldModel.Parts)
                {
                    part.BoundingBox.GetCorners(corners);
                    for (int c = 0; c < 8; c++)
                        corners[c] = Vector3.Transform(corners[c], worldModel.World);
                    BoundingBox box = BoundingBox.CreateFromPoints(corners);
                    ghostBox = any ? BoundingBox.CreateMerged(ghostBox, box) : box;
                    any = true;
                }
                if (any)
                {
                    ghostBox.Draw(device, basicEffect, CameraManager.View, CameraManager.Projection, new Color(120, 255, 120));
                    ToolTipManager.Set("Placing: " + Models.ZscCatalog.ObjectName(FileManager.ZSCs[Type.ToString()], model) + " (click to put it here)", new Vector3(ghostBox.GetCenter().X, ghostBox.GetCenter().Y, ghostBox.Max.Z));
                }
                FrameStats.Add("ghost", ghostStart);
            }

            List<Objects.Object.WorldObject> worldObjects = (Type == ObjectType.Decoration) ? MapManager.Decoration.WorldObjects : MapManager.Construction.WorldObjects;

            if (!drawBoundingBoxes)
            {
                if (SelectedObject >= 0)
                    worldObjects[SelectedObject].BoundingBox.Draw(device, basicEffect, CameraManager.View, CameraManager.Projection, Color.White);

                if (hoveredObject != SelectedObject && hoveredObject >= 0)
                    worldObjects[hoveredObject].BoundingBox.Draw(device, basicEffect, CameraManager.View, CameraManager.Projection, Color.Red);

                return;
            }

            BoundingFrustum boundingFrustum = new BoundingFrustum(CameraManager.View * CameraManager.Projection);

            // Every visible box in one draw call (this loop used to make one call,
            // and one leaked vertex declaration, per box).
            long boxesStart = FrameStats.Start();
            for(int i = 0; i < worldObjects.Count; i++)
            {
                if (!boundingFrustum.OnScreen(worldObjects[i].BoundingBox))
                    continue;

                BoundingBoxBatch.Add(worldObjects[i].BoundingBox, (SelectedObject == i) ? Color.White : (hoveredObject == i) ? Color.Red : Color.Blue);
            }
            FrameStats.Count("boxes", BoundingBoxBatch.Pending);
            BoundingBoxBatch.Flush(device, basicEffect, CameraManager.View, CameraManager.Projection);
            FrameStats.Add("boxes", boxesStart);
        }
    }
}