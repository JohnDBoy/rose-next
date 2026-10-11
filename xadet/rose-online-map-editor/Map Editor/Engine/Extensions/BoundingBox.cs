using System;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;

/// <summary>
/// BoundingBox Extensions class.
/// </summary>
public static class BoundingBoxExtensions
{
    /// <summary>
    /// Splits the specified bounding box.
    /// </summary>
    /// <param name="boundingBox">The bounding box.</param>
    /// <returns>Split bounding box.</returns>
    public static BoundingBox[] Split(this BoundingBox boundingBox)
    {
        return new BoundingBox[]
        {
            new BoundingBox(new Vector3(boundingBox.Min.X, boundingBox.Min.Y, boundingBox.Min.Z), new Vector3((boundingBox.Min.X + boundingBox.Max.X) / 2.0f, (boundingBox.Min.Y + boundingBox.Max.Y) / 2.0f, boundingBox.Max.Z)),
            new BoundingBox(new Vector3(boundingBox.Min.X, (boundingBox.Min.Y + boundingBox.Max.Y) / 2.0f, boundingBox.Min.Z), new Vector3((boundingBox.Min.X + boundingBox.Max.X) / 2.0f, boundingBox.Max.Y, boundingBox.Max.Z)),
            new BoundingBox(new Vector3((boundingBox.Min.X + boundingBox.Max.X) / 2.0f, boundingBox.Min.Y, boundingBox.Min.Z), new Vector3(boundingBox.Max.X, (boundingBox.Min.Y + boundingBox.Max.Y) / 2.0f, boundingBox.Max.Z)),
            new BoundingBox(new Vector3((boundingBox.Min.X + boundingBox.Max.X) / 2.0f, (boundingBox.Min.Y + boundingBox.Max.Y) / 2.0f, boundingBox.Min.Z), new Vector3(boundingBox.Max.X, boundingBox.Max.Y, boundingBox.Max.Z)),
        };
    }

    /// <summary>
    /// Determines whether the specified bounding box is closer.
    /// </summary>
    /// <param name="boundingBox">The bounding box.</param>
    /// <param name="secondBoundingBox">The second bounding box.</param>
    /// <param name="cameraPosition">The camera position.</param>
    /// <returns>
    /// 	<c>true</c> if the specified bounding box is closer; otherwise, <c>false</c>.
    /// </returns>
    public static bool IsCloser(this BoundingBox boundingBox, BoundingBox secondBoundingBox, Vector3 cameraPosition)
    {
        Vector3[] cornersA = boundingBox.GetCorners();
        Vector3[] cornersB = secondBoundingBox.GetCorners();

        for (int i = 0; i < BoundingBox.CornerCount; i++)
        {
            if (Vector3.Distance(cameraPosition, cornersA[i]) > Vector3.Distance(cameraPosition, cornersB[i]))
                return true;
        }

        return false;
    }

    /// <summary>
    /// Gets the center.
    /// </summary>
    /// <param name="boundingBox">The bounding box.</param>
    /// <returns>Center position.</returns>
    public static Vector3 GetCenter(this BoundingBox boundingBox)
    {
        return (boundingBox.Min + boundingBox.Max) / 2.0f;
    }

    /// <summary>
    /// Draws the specified bounding box.
    /// </summary>
    /// <param name="boundingBox">The bounding box.</param>
    /// <param name="device">The device.</param>
    /// <param name="effect">The effect.</param>
    /// <param name="view">The view.</param>
    /// <param name="projection">The projection.</param>
    /// <param name="colour">The colour.</param>
    public static void Draw(this BoundingBox boundingBox, GraphicsDevice device, BasicEffect effect, Matrix view, Matrix projection, Color colour)
    {
        short[] indices = new short[]
        {
            0, 1, 1,
            2, 2, 3,
            3, 0, 0,
            4, 1, 5,
            2, 6, 3,
            7, 4, 5,
            5, 6, 6,
            7, 7, 4,
        };

        effect.VertexColorEnabled = true;
        effect.LightingEnabled = false;

        effect.World = Matrix.Identity;
        effect.View = view;
        effect.Projection = projection;

        Vector3[] corners = boundingBox.GetCorners();
        VertexPositionColor[] vertices = new VertexPositionColor[8];

        for (int i = 0; i < 8; i++)
        {
            vertices[i].Position = corners[i];
            vertices[i].Color = colour;
        }

        device.VertexDeclaration = BoundingBoxBatch.Declaration(device);

        effect.Begin();

        for (int i = 0; i < effect.CurrentTechnique.Passes.Count; i++)
        {
            effect.CurrentTechnique.Passes[i].Begin();

            device.DrawUserIndexedPrimitives(PrimitiveType.LineList, vertices, 0, 8, indices, 0, indices.Length / 2);

            effect.CurrentTechnique.Passes[i].End();
        }

        effect.End();
    }

    /// <summary>
    /// Draws the specified bounding box.
    /// </summary>
    /// <param name="boundingBox">The bounding box.</param>
    /// <param name="device">The device.</param>
    public static void Draw(this BoundingBox boundingBox, GraphicsDevice device)
    {
        short[] indices = new short[]
        {
            0, 1, 1,
            2, 2, 3,
            3, 0, 0,
            4, 1, 5,
            2, 6, 3,
            7, 4, 5,
            5, 6, 6,
            7, 7, 4,
        };

        Vector3[] corners = boundingBox.GetCorners();
        VertexPositionColor[] vertices = new VertexPositionColor[8];

        for (int i = 0; i < 8; i++)
        {
            vertices[i].Position = corners[i];
            vertices[i].Color = Color.White;
        }

        device.VertexDeclaration = BoundingBoxBatch.Declaration(device);

        device.DrawUserIndexedPrimitives(PrimitiveType.LineList, vertices, 0, 8, indices, 0, indices.Length / 2);
    }
}

/// <summary>
/// Draws many bounding boxes in one call. The per-box Draw above created a new
/// vertex declaration (a Direct3D object) on every call and never disposed it,
/// hundreds of times a frame with "Draw bounding boxes" on; both now share one
/// declaration per device, and the tools' all-objects loops go through here.
/// </summary>
public static class BoundingBoxBatch
{
    private const int MAX_BOXES = 4000;   // 8 vertices each, under the 16-bit index limit

    private static readonly short[] boxIndices = new short[]
    {
        0, 1, 1, 2, 2, 3, 3, 0,
        4, 5, 5, 6, 6, 7, 7, 4,
        0, 4, 1, 5, 2, 6, 3, 7,
    };

    private static VertexDeclaration declaration;
    private static GraphicsDevice declarationDevice;
    private static VertexPositionColor[] vertices = new VertexPositionColor[0];
    private static short[] indices = new short[0];
    private static int count;

    public static VertexDeclaration Declaration(GraphicsDevice device)
    {
        if (declaration == null || declarationDevice != device || declaration.IsDisposed)
        {
            declaration = new VertexDeclaration(device, VertexPositionColor.VertexElements);
            declarationDevice = device;
        }
        return declaration;
    }

    /// <summary>Queues a box; Flush draws them all.</summary>
    public static void Add(BoundingBox box, Color colour)
    {
        if (count >= MAX_BOXES)
            return;

        if (vertices.Length < (count + 1) * 8)
        {
            int capacity = Math.Max(64, Math.Min(MAX_BOXES, vertices.Length / 8 * 2 + 1));
            VertexPositionColor[] v = new VertexPositionColor[capacity * 8];
            Array.Copy(vertices, v, count * 8);
            vertices = v;
            short[] ix = new short[capacity * 24];
            for (int b = 0; b < capacity; b++)
                for (int i = 0; i < 24; i++)
                    ix[b * 24 + i] = (short)(b * 8 + boxIndices[i]);
            indices = ix;
        }

        Vector3[] corners = box.GetCorners();
        int baseIndex = count * 8;
        for (int i = 0; i < 8; i++)
        {
            vertices[baseIndex + i].Position = corners[i];
            vertices[baseIndex + i].Color = colour;
        }
        count++;
    }

    public static int Pending
    {
        get { return count; }
    }

    public static void Flush(GraphicsDevice device, BasicEffect effect, Matrix view, Matrix projection)
    {
        if (count == 0)
            return;

        effect.VertexColorEnabled = true;
        effect.LightingEnabled = false;
        effect.World = Matrix.Identity;
        effect.View = view;
        effect.Projection = projection;

        device.VertexDeclaration = Declaration(device);

        effect.Begin();
        for (int i = 0; i < effect.CurrentTechnique.Passes.Count; i++)
        {
            effect.CurrentTechnique.Passes[i].Begin();
            device.DrawUserIndexedPrimitives(PrimitiveType.LineList, vertices, 0, count * 8, indices, 0, count * 12);
            effect.CurrentTechnique.Passes[i].End();
        }
        effect.End();

        count = 0;
    }
}
