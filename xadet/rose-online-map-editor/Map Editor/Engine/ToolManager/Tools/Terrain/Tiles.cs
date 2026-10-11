using System.Collections.Generic;
using System.Windows.Forms;
using Map_Editor.Engine.Tools.Interfaces;
using Map_Editor.Forms.Controls;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Microsoft.Xna.Framework.Input;

namespace Map_Editor.Engine.Tools
{
    /// <summary>
    /// Tiles class.
    /// </summary>
    public class Tiles : ITool
    {
        /// <summary>
        /// Tile Tool type.
        /// </summary>
        public enum TileToolType
        {
            /// <summary>
            /// None.
            /// </summary>
            None,

            /// <summary>
            /// Pick.
            /// </summary>
            Pick,

            /// <summary>
            /// Modify.
            /// </summary>
            Modify
        }

        /// <summary>
        /// Tile structure.
        /// </summary>
        public struct Tile
        {
            #region Member Declarations

            /// <summary>
            /// Gets or sets the X.
            /// </summary>
            /// <value>The X.</value>
            public int X { get; set; }

            /// <summary>
            /// Gets or sets the Y.
            /// </summary>
            /// <value>The Y.</value>
            public int Y { get; set; }

            /// <summary>
            /// Gets or sets the tile X.
            /// </summary>
            /// <value>The tile X.</value>
            public int TileX { get; set; }

            /// <summary>
            /// Gets or sets the tile Y.
            /// </summary>
            /// <value>The tile Y.</value>
            public int TileY { get; set; }

            #endregion
        };

        #region Member Declarations

        /// <summary>
        /// Gets or sets the device.
        /// </summary>
        /// <value>The device.</value>
        private GraphicsDevice device { get; set; }

        /// <summary>
        /// Gets or sets the hovered tile.
        /// </summary>
        /// <value>The hovered tile.</value>
        public Tile? HoveredTile { get; set; }

        /// <summary>
        /// Gets or sets the tool mode.
        /// </summary>
        /// <value>The tool mode.</value>
        public TileToolType ToolMode { get; set; }

        /// <summary>
        /// The tiles changed by the stroke in progress, keyed by cell: one undo
        /// command per stroke, pushed when the button comes up.
        /// </summary>
        private Dictionary<int, Commands.Tiles.Placement.Tile> stroke;

        #endregion

        /// <summary>
        /// Initializes a new instance of the <see cref="Tiles"/> class.
        /// </summary>
        /// <param name="device">The device.</param>
        public Tiles(GraphicsDevice device)
        {
            this.device = device;

            ToolMode = TileToolType.None;
        }

        /// <summary>
        /// Updates the tool.
        /// </summary>
        /// <param name="gameTime">The game time.</param>
        public void Update(GameTime gameTime)
        {
            MouseState mouseState = Mouse.GetState();

            // A stroke ends when the button comes up, wherever the mouse is.
            if (mouseState.LeftButton == Microsoft.Xna.Framework.Input.ButtonState.Released)
                EndStroke();

            if (ToolMode == TileToolType.None)
                return;

            Cursor.Current = ((HoveredTile = MapManager.Heightmaps.PickTile()) == null) ? Cursors.Default : Cursors.Hand;

            if (HoveredTile == null)
                return;

            if (mouseState.LeftButton == Microsoft.Xna.Framework.Input.ButtonState.Released)
                return;

            switch (ToolMode)
            {
                case TileToolType.Pick:
                    ((TileTool)App.Form.ToolHost.Content).SelectTile(MapManager.Heightmaps.Blocks[HoveredTile.Value.Y, HoveredTile.Value.X].TileFile.Tiles[HoveredTile.Value.TileY, HoveredTile.Value.TileX].TileID);
                    break;
                case TileToolType.Modify:
                    {
                        int gridSize = 1;

                        switch (((TileTool)App.Form.ToolHost.Content).MultipleSelection.SelectedIndex)
                        {
                            case 0:
                                gridSize = 3;
                                break;
                            case 1:
                                gridSize = 5;
                                break;
                            case 2:
                                gridSize = 7;
                                break;
                            case 3:
                                gridSize = 9;
                                break;
                        }

                        if (((TileTool)App.Form.ToolHost.Content).MultiplePlacement.IsChecked == true)
                        {
                            for (int ty = HoveredTile.Value.TileY - (gridSize / 2); ty <= HoveredTile.Value.TileY + (gridSize / 2); ty++)
                            {
                                for (int tx = HoveredTile.Value.TileX - (gridSize / 2); tx <= HoveredTile.Value.TileX + (gridSize / 2); tx++)
                                {
                                    int tileX = tx;
                                    int fileX = HoveredTile.Value.X;

                                    int tileY = ty;
                                    int fileY = HoveredTile.Value.Y;

                                    if (tileX > 15)
                                    {
                                        tileX -= 16;
                                        fileY += 1;
                                    }
                                    else if (tileX < 0)
                                    {
                                        tileX += 16;
                                        fileY -= 1;
                                    }

                                    if (tileY > 15)
                                    {
                                        tileY -= 16;
                                        fileX += 1;
                                    }
                                    else if (tileY < 0)
                                    {
                                        tileY += 16;
                                        fileX -= 1;
                                    }

                                    if (MapManager.Heightmaps.Blocks[fileY, fileX] == null)
                                        continue;

                                    RecordTile(new Commands.Tiles.Placement.Tile()
                                    {
                                        X = fileX,
                                        Y = fileY,
                                        TileX = tileX,
                                        TileY = tileY,
                                        OldID = MapManager.Heightmaps.Blocks[fileY, fileX].TileFile.Tiles[tileY, tileX].TileID,
                                        NewID = ((TileTool)App.Form.ToolHost.Content).Tile
                                    });

                                    MapManager.Heightmaps.Blocks[fileY, fileX].ChangeTile(tileX, tileY, ((TileTool)App.Form.ToolHost.Content).Tile);                               
                                }
                            }
                        }
                        else
                        {
                            RecordTile(new Commands.Tiles.Placement.Tile()
                            {
                                X = HoveredTile.Value.X,
                                Y = HoveredTile.Value.Y,
                                TileX = HoveredTile.Value.TileX,
                                TileY = HoveredTile.Value.TileY,
                                OldID = MapManager.Heightmaps.Blocks[HoveredTile.Value.Y, HoveredTile.Value.X].TileFile.Tiles[HoveredTile.Value.TileY, HoveredTile.Value.TileX].TileID,
                                NewID = ((TileTool)App.Form.ToolHost.Content).Tile
                            });

                            MapManager.Heightmaps.Blocks[HoveredTile.Value.Y, HoveredTile.Value.X].ChangeTile(HoveredTile.Value.TileX, HoveredTile.Value.TileY, ((TileTool)App.Form.ToolHost.Content).Tile);
                        }
                    }
                    break;
            }
        }

        /// <summary>
        /// Merges one changed tile into the stroke in progress: a cell keeps the
        /// old value first seen and takes the latest new one.
        /// </summary>
        /// <param name="tile">The tile.</param>
        private void RecordTile(Commands.Tiles.Placement.Tile tile)
        {
            if (stroke == null)
                stroke = new Dictionary<int, Commands.Tiles.Placement.Tile>();

            int key = ((tile.Y * 100 + tile.X) * 16 + tile.TileY) * 16 + tile.TileX;

            Commands.Tiles.Placement.Tile seen;

            if (stroke.TryGetValue(key, out seen))
            {
                seen.NewID = tile.NewID;
                stroke[key] = seen;
            }
            else if (tile.NewID != tile.OldID)
                stroke.Add(key, tile);
        }

        /// <summary>
        /// Pushes the stroke in progress as one undo command.
        /// </summary>
        private void EndStroke()
        {
            if (stroke == null)
                return;

            if (stroke.Count > 0)
            {
                Commands.Tiles.Placement.Tile[] tiles = new Commands.Tiles.Placement.Tile[stroke.Count];
                stroke.Values.CopyTo(tiles, 0);

                UndoManager.AddCommand(new Commands.Tiles.Placement()
                {
                    Tiles = tiles
                });
            }

            stroke = null;
        }
    }
}