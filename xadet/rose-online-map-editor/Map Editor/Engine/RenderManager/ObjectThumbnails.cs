using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Threading;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using Map_Editor.Engine.Models;
using Map_Editor.Misc;
using Microsoft.Xna.Framework;
using XNA = Microsoft.Xna.Framework.Graphics;
using Matrix = Microsoft.Xna.Framework.Matrix;

namespace Map_Editor.Engine.RenderManager
{
    /// <summary>
    /// Renders one picture per ZSC object for the object browser, on its own
    /// thread and graphics device, and keeps every picture as a PNG under
    /// %LOCALAPPDATA% so a table is only ever rendered once. Requests are
    /// served newest first, so what is on screen comes before what was
    /// scrolled past; a request whose caller has gone (the panel closed) is
    /// dropped by <see cref="CancelAll"/>.
    ///
    /// Replaces the per-tool copies of the same loop, which rendered every
    /// object of the table on each open through a .bmp on disk.
    /// </summary>
    public static class ObjectThumbnails
    {
        public const int SIZE = 96;

        public delegate void Done(BitmapSource image);

        private class Job
        {
            public ZSC Zsc;
            public string Key;
            public int Index;
            public Done Callback;
            public Dispatcher Dispatcher;
        }

        private static readonly object sync = new object();
        private static readonly List<Job> queue = new List<Job>();
        private static readonly Dictionary<string, BitmapSource> memory = new Dictionary<string, BitmapSource>();
        private static readonly Dictionary<string, List<Job>> waiting = new Dictionary<string, List<Job>>();
        private static Thread worker;
        private static XNA.GraphicsDevice device;
        private static XNA.BasicEffect shader;
        private static XNA.VertexDeclaration vertexDeclaration;
        private static bool deviceFailed;
        private static BitmapSource placeholder;

        /// <summary>
        /// Asks for the picture of object <paramref name="index"/> of
        /// <paramref name="zsc"/>. The callback runs on the caller's dispatcher,
        /// synchronously when the picture is already in memory.
        /// </summary>
        public static void Request(ZSC zsc, string tablePath, int index, Done callback)
        {
            string key = Key(zsc, tablePath, index);
            if (key == null)
            {
                callback(Placeholder());
                return;
            }

            BitmapSource cached;
            lock (sync)
            {
                if (memory.TryGetValue(key, out cached))
                {
                    // fall through, call outside the lock
                }
                else
                {
                    Job r = new Job()
                    {
                        Zsc = zsc,
                        Key = key,
                        Index = index,
                        Callback = callback,
                        Dispatcher = Dispatcher.CurrentDispatcher
                    };
                    List<Job> others;
                    if (waiting.TryGetValue(key, out others))
                    {
                        others.Add(r);
                        return;
                    }
                    waiting.Add(key, new List<Job>() { r });
                    queue.Add(r);
                    EnsureWorker();
                    Monitor.Pulse(sync);
                    return;
                }
            }
            callback(cached);
        }

        /// <summary>Drops every pending request (the browser was closed or refilled).</summary>
        public static void CancelAll()
        {
            lock (sync)
            {
                queue.Clear();
                waiting.Clear();
            }
        }

        /// <summary>How many pictures are still to be made.</summary>
        public static int Pending
        {
            get { lock (sync) { return queue.Count; } }
        }

        /// <summary>How many pictures were rendered since the editor started (cache hits excluded).</summary>
        public static int Completed
        {
            get { return completed; }
        }
        private static volatile int completed;

        /// <summary>
        /// Set by the tools while the user is placing or dragging: the worker
        /// waits rather than compete for the GPU (each render ends in a
        /// read-back that stalls the device the editor is drawing with).
        /// </summary>
        public static volatile bool Busy;

        public static BitmapSource Placeholder()
        {
            if (placeholder == null)
            {
                byte[] pixels = new byte[SIZE * SIZE * 4];
                for (int i = 0; i < pixels.Length; i += 4)
                {
                    pixels[i] = 236; pixels[i + 1] = 238; pixels[i + 2] = 241; pixels[i + 3] = 255;
                }
                placeholder = BitmapSource.Create(SIZE, SIZE, 96, 96, PixelFormats.Bgra32, null, pixels, SIZE * 4);
                placeholder.Freeze();
            }
            return placeholder;
        }

        /// <summary>
        /// The cache key is the object's content hash (its bytes plus the files it
        /// names), so an appended or changed object gets a new picture and an
        /// identical object in another table shares it.
        /// </summary>
        private static string Key(ZSC zsc, string tablePath, int index)
        {
            if (zsc == null || zsc.Raw == null)
                return null;
            return zsc.Raw.ContentHash(index);
        }

        private static string CachePath(string key)
        {
            return Path.Combine(EditorPaths.Thumbnails, key + ".png");
        }

        private static void EnsureWorker()
        {
            if (worker != null && worker.IsAlive)
                return;
            worker = new Thread(Work);
            worker.IsBackground = true;
            worker.Name = "Object thumbnails";
            worker.Start();
        }

        private static void Work()
        {
            Dictionary<string, ZMS> meshes = new Dictionary<string, ZMS>(StringComparer.OrdinalIgnoreCase);
            Dictionary<string, XNA.Texture2D> textures = new Dictionary<string, XNA.Texture2D>(StringComparer.OrdinalIgnoreCase);

            while (true)
            {
                Job r;
                lock (sync)
                {
                    while (queue.Count == 0)
                    {
                        // Idle: let go of the batch caches.
                        foreach (XNA.Texture2D t in textures.Values)
                            t.Dispose();
                        textures.Clear();
                        meshes.Clear();
                        Monitor.Wait(sync);
                    }
                    r = queue[queue.Count - 1];
                    queue.RemoveAt(queue.Count - 1);
                }

                BitmapSource image = null;
                try
                {
                    string file = CachePath(r.Key);
                    if (File.Exists(file))
                        image = LoadPng(file);
                    if (image == null)
                    {
                        // Not while the user is placing or dragging, and never two in a
                        // row without a breath: the editor's frames come first.
                        while (Busy)
                            Thread.Sleep(50);
                        image = Render(r.Zsc, r.Index, meshes, textures);
                        if (image != null)
                            SavePng(file, image);
                        completed++;
                        Thread.Sleep(8);
                    }
                }
                catch (Exception ex)
                {
                    Output.WriteLine(Output.MessageType.Error, string.Format("Thumbnail for object {0} failed: {1}", r.Index, ex.Message));
                }
                if (image == null)
                    image = Placeholder();

                List<Job> callbacks;
                lock (sync)
                {
                    memory[r.Key] = image;
                    if (!waiting.TryGetValue(r.Key, out callbacks))
                        callbacks = null;
                    waiting.Remove(r.Key);
                }
                if (callbacks == null)
                    continue;

                foreach (Job c in callbacks)
                {
                    Job captured = c;
                    BitmapSource result = image;
                    captured.Dispatcher.BeginInvoke(DispatcherPriority.Background, (DispatcherOperationCallback)delegate
                    {
                        captured.Callback(result);
                        return null;
                    }, null);
                }
            }
        }

        private static BitmapSource LoadPng(string file)
        {
            byte[] bytes = File.ReadAllBytes(file);
            BitmapImage bmp = new BitmapImage();
            bmp.BeginInit();
            bmp.CacheOption = BitmapCacheOption.OnLoad;
            bmp.StreamSource = new MemoryStream(bytes);
            bmp.EndInit();
            bmp.Freeze();
            return bmp;
        }

        private static void SavePng(string file, BitmapSource image)
        {
            PngBitmapEncoder encoder = new PngBitmapEncoder();
            encoder.Frames.Add(BitmapFrame.Create(image));
            string temp = file + ".tmp";
            using (FileStream fs = new FileStream(temp, FileMode.Create, FileAccess.Write))
                encoder.Save(fs);
            if (File.Exists(file))
                File.Delete(file);
            File.Move(temp, file);
        }

        private static bool EnsureDevice()
        {
            if (device != null)
                return true;
            if (deviceFailed)
                return false;

            try
            {
                device = new XNA.GraphicsDevice(XNA.GraphicsAdapter.DefaultAdapter, XNA.DeviceType.Hardware, new System.Windows.Forms.Panel().Handle, new XNA.PresentationParameters()
                {
                    AutoDepthStencilFormat = XNA.DepthFormat.Depth24,
                    BackBufferCount = 1,
                    BackBufferFormat = XNA.SurfaceFormat.Color,
                    BackBufferHeight = SIZE,
                    BackBufferWidth = SIZE,
                    EnableAutoDepthStencil = true,
                    FullScreenRefreshRateInHz = 0,
                    IsFullScreen = false,
                    MultiSampleQuality = 0,
                    MultiSampleType = XNA.MultiSampleType.NonMaskable,
                    PresentationInterval = XNA.PresentInterval.One,
                    PresentOptions = XNA.PresentOptions.None,
                    RenderTargetUsage = XNA.RenderTargetUsage.DiscardContents,
                    SwapEffect = XNA.SwapEffect.Discard
                });
                device.RenderState.CullMode = XNA.CullMode.None;
                shader = new XNA.BasicEffect(device, null);
                vertexDeclaration = new XNA.VertexDeclaration(device, ZMS.Vertex.VertexElements);
                return true;
            }
            catch (Exception ex)
            {
                deviceFailed = true;
                Output.WriteLine(Output.MessageType.Error, "Thumbnail device could not be created: " + ex.Message);
                return false;
            }
        }

        /// <summary>
        /// The same framing as the old per-tool loop: the object's bounding sphere
        /// filling a 45 degree view from the front, Z up.
        /// </summary>
        private static BitmapSource Render(ZSC zsc, int index, Dictionary<string, ZMS> meshes, Dictionary<string, XNA.Texture2D> textures)
        {
            if (!EnsureDevice())
                return null;

            ZSC.Object o = zsc.Objects[index];
            if (o.Models.Count == 0)
                return null;

            ZMS[] models = new ZMS[o.Models.Count];
            Matrix[] worlds = new Matrix[o.Models.Count];
            BoundingBox box = new BoundingBox();
            bool any = false;

            for (int j = 0; j < o.Models.Count; j++)
            {
                worlds[j] = Matrix.CreateFromQuaternion(o.Models[j].Rotation) *
                            Matrix.CreateScale(o.Models[j].Scale) *
                            Matrix.CreateTranslation(o.Models[j].Position);

                string meshPath = zsc.Models[o.Models[j].ModelID];
                ZMS mesh;
                if (!meshes.TryGetValue(meshPath, out mesh))
                {
                    try
                    {
                        mesh = new ZMS();
                        mesh.Load(meshPath);
                    }
                    catch (Exception ex)
                    {
                        Output.WriteLine(Output.MessageType.Error, string.Format("Thumbnail: mesh {0} did not load: {1}", meshPath, ex.Message));
                        mesh = null;
                    }
                    meshes[meshPath] = mesh;
                }
                models[j] = mesh;
                if (mesh == null || mesh.VertexCount == 0)
                    continue;

                Vector3[] points = new Vector3[mesh.VertexCount];
                for (int k = 0; k < points.Length; k++)
                    points[k] = Vector3.Transform(mesh.Vertices[k].Position, worlds[j]);
                BoundingBox part = BoundingBox.CreateFromPoints(points);
                box = any ? BoundingBox.CreateMerged(box, part) : part;
                any = true;
            }
            if (!any)
                return null;

            XNA.RenderTarget2D target = new XNA.RenderTarget2D(device, SIZE, SIZE, 1, device.PresentationParameters.BackBufferFormat, device.PresentationParameters.MultiSampleType, device.PresentationParameters.MultiSampleQuality, device.PresentationParameters.RenderTargetUsage);
            try
            {
                device.SetRenderTarget(0, target);
                device.Clear(XNA.ClearOptions.Target | XNA.ClearOptions.DepthBuffer, new XNA.Color(245, 247, 250), 1.0f, 0);

                XNA.Viewport viewport = device.Viewport;
                viewport.Width = SIZE;
                viewport.Height = SIZE;
                viewport.MinDepth = 1.0f;
                viewport.MaxDepth = 50000.0f;
                device.Viewport = viewport;

                BoundingSphere sphere = BoundingSphere.CreateFromBoundingBox(box);
                Matrix projection = Matrix.CreatePerspectiveFieldOfView(MathHelper.PiOver4, 1.0f, viewport.MinDepth, viewport.MaxDepth);
                Vector3 cameraPosition = Vector3.Transform(sphere.Center + (Vector3.Forward * ((sphere.Radius + 0.5f) / (float)Math.Sin(MathHelper.PiOver4 / 2))), Matrix.CreateRotationX(MathHelper.ToRadians(270)));
                Matrix view = Matrix.CreateLookAt(cameraPosition, sphere.Center, Vector3.Down);

                for (int j = 0; j < o.Models.Count; j++)
                {
                    if (models[j] == null || models[j].VertexCount == 0)
                        continue;

                    ZSC.Texture material = zsc.Textures[o.Models[j].TextureID];
                    XNA.Texture2D texture;
                    if (!textures.TryGetValue(material.Path, out texture))
                    {
                        try
                        {
                            texture = GameData.LoadTexture(device, material.Path);
                        }
                        catch (Exception ex)
                        {
                            Output.WriteLine(Output.MessageType.Error, string.Format("Thumbnail: texture {0} did not load: {1}", material.Path, ex.Message));
                            texture = null;
                        }
                        textures[material.Path] = texture;
                    }

                    shader.World = worlds[j];
                    shader.View = view;
                    shader.Projection = projection;
                    shader.DiffuseColor = XNA.Color.White.ToVector3();
                    shader.Texture = texture;
                    shader.TextureEnabled = texture != null;
                    shader.Alpha = material.Alpha;

                    device.VertexDeclaration = vertexDeclaration;
                    XNA.IndexBuffer indices = models[j].CreateIndexBuffer(device);
                    XNA.VertexBuffer vertices = models[j].CreateVertexBuffer(device);
                    try
                    {
                        device.Indices = indices;
                        device.Vertices[0].SetSource(vertices, 0, ZMS.Vertex.SIZE_IN_BYTES);

                        device.RenderState.AlphaBlendEnable = material.AlphaEnabled;
                        if (material.AlphaEnabled)
                        {
                            device.RenderState.AlphaTestEnable = material.AlphaTestEnabled;
                            device.RenderState.SourceBlend = TextureManager.GetSourceBlend(material.BlendingMode);
                            device.RenderState.DestinationBlend = TextureManager.GetDestinationBlend(material.BlendingMode);
                            device.RenderState.ReferenceAlpha = material.AlphaReference;
                            device.RenderState.AlphaFunction = XNA.CompareFunction.GreaterEqual;
                            device.RenderState.BlendFunction = TextureManager.GetBlendFunction(material.BlendingMode);
                        }
                        else
                        {
                            device.RenderState.AlphaTestEnable = false;
                            device.RenderState.SourceBlend = XNA.Blend.One;
                            device.RenderState.DestinationBlend = XNA.Blend.Zero;
                            device.RenderState.ReferenceAlpha = 0;
                            device.RenderState.AlphaFunction = XNA.CompareFunction.Always;
                            device.RenderState.BlendFunction = XNA.BlendFunction.Add;
                        }
                        device.RenderState.DepthBufferEnable = material.ZTestEnabled;
                        device.RenderState.DepthBufferWriteEnable = material.ZWriteEnabled;

                        shader.Begin();
                        for (int k = 0; k < shader.CurrentTechnique.Passes.Count; k++)
                        {
                            shader.CurrentTechnique.Passes[k].Begin();
                            device.DrawIndexedPrimitives(XNA.PrimitiveType.TriangleList, 0, 0, models[j].VertexCount, 0, models[j].IndexCount);
                            shader.CurrentTechnique.Passes[k].End();
                        }
                        shader.End();
                    }
                    finally
                    {
                        device.Indices = null;
                        device.Vertices[0].SetSource(null, 0, 0);
                        indices.Dispose();
                        vertices.Dispose();
                    }
                }

                device.SetRenderTarget(0, null);

                XNA.Texture2D result = target.GetTexture();
                XNA.Color[] colors = new XNA.Color[SIZE * SIZE];
                result.GetData<XNA.Color>(colors);

                byte[] pixels = new byte[SIZE * SIZE * 4];
                for (int i = 0; i < colors.Length; i++)
                {
                    pixels[i * 4] = colors[i].B;
                    pixels[i * 4 + 1] = colors[i].G;
                    pixels[i * 4 + 2] = colors[i].R;
                    pixels[i * 4 + 3] = 255;
                }

                BitmapSource image = BitmapSource.Create(SIZE, SIZE, 96, 96, PixelFormats.Bgra32, null, pixels, SIZE * 4);
                image.Freeze();
                return image;
            }
            finally
            {
                device.SetRenderTarget(0, null);
                target.Dispose();
            }
        }
    }
}
