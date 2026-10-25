using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Microsoft.Xna.Framework.Input;

namespace Map_Editor.Engine.Types
{
    /// <summary>
    /// Perspective cass.
    /// </summary>
    public class Perspective
    {
        /// <summary>
        /// Speed of the camera.
        /// </summary>
        public const float CAMERA_SPEED = 0.833335f;

        /// <summary>
        /// Smooth mode: seconds for the movement to cover about two thirds of
        /// the way to the keys' speed (or back to rest).
        /// </summary>
        private const float SMOOTH_MOVE_SECONDS = 0.6f;

        /// <summary>
        /// Smooth mode: the same for turning towards where the mouse points.
        /// </summary>
        private const float SMOOTH_TURN_SECONDS = 0.25f;

        #region Member Declarations

        /// <summary>
        /// Gets or sets the velocity position.
        /// </summary>
        /// <value>The velocity position.</value>
        private Vector3 velocityPosition { get;  set; }

        /// <summary>
        /// Gets or sets the mouse rotation X.
        /// </summary>
        /// <value>The mouse rotation X.</value>
        private float mouseRotationX { get;  set; }

        /// <summary>
        /// Gets or sets the mouse rotation Z.
        /// </summary>
        /// <value>The mouse rotation Z.</value>
        private float mouseRotationZ { get;  set; }

        /// <summary>
        /// Where the mouse has turned the camera to; the camera follows at
        /// once, or eases there in smooth mode.
        /// </summary>
        private float targetRotationX { get; set; }
        private float targetRotationZ { get; set; }

        /// <summary>
        /// Gets or sets the last mouse location.
        /// </summary>
        /// <value>The last mouse location.</value>
        private Vector2 lastMouseLocation { get;  set; }

        /// <summary>
        /// Gets or sets the view.
        /// </summary>
        /// <value>The view.</value>
        public Matrix View { get; private set; }

        /// <summary>
        /// Gets or sets the projection.
        /// </summary>
        /// <value>The projection.</value>
        public Matrix Projection { get; private set; }

        /// <summary>
        /// Gets or sets the position.
        /// </summary>
        /// <value>The position.</value>
        public Vector3 Position { get; private set; }

        /// <summary>
        /// Gets whether the camera is held by a script (ShotRunner): mouse and
        /// keyboard no longer move it.
        /// </summary>
        public bool Scripted { get; private set; }

        /// <summary>
        /// Scales the W/A/S/D speed: 1 is the editor's original 50 m/s.
        /// </summary>
        public float SpeedScale { get; set; }

        /// <summary>
        /// Eases movement and turning in and out instead of starting and
        /// stopping dead (fullscreen showcase).
        /// </summary>
        public bool Smooth { get; set; }

        #endregion

        /// <summary>
        /// Initializes a new instance of the <see cref="Perspective"/> class.
        /// </summary>
        public Perspective()
        {
            View = Matrix.Identity;
            Projection = Matrix.Identity;

            mouseRotationX = 1.54f;
            mouseRotationZ = -3.150001f;
            targetRotationX = mouseRotationX;
            targetRotationZ = mouseRotationZ;

            SpeedScale = 1.0f;

            Position = new Vector3(5650.0f, 5250.0f, 10.0f);

            velocityPosition = Vector3.Zero;
        }

        /// <summary>
        /// Rotates the camera.
        /// </summary>
        /// <param name="x">X angle.</param>
        /// <param name="z">Z angle.</param>
        private void Rotate(float x, float z)
        {
            targetRotationX += x;
            targetRotationZ += z;
        }

        /// <summary>
        /// Brings the camera's rotation to the mouse's: at once, or part of the
        /// way in smooth mode.
        /// </summary>
        private void FollowRotation(float seconds)
        {
            float t = Smooth ? Ease(seconds, SMOOTH_TURN_SECONDS) : 1.0f;

            mouseRotationX += (targetRotationX - mouseRotationX) * t;
            mouseRotationZ += (targetRotationZ - mouseRotationZ) * t;
        }

        /// <summary>
        /// The share of the remaining distance to cover this frame for an
        /// exponential ease with the given time constant (frame-rate independent).
        /// </summary>
        private static float Ease(float seconds, float timeConstant)
        {
            return 1.0f - (float)System.Math.Exp(-seconds / timeConstant);
        }

        /// <summary>
        /// Changes the position of the camera affected by the rotation.
        /// </summary>
        /// <param name="distanceChange">The change in distance.</param>
        private void Translate(Vector3 distanceChange)
        {
            Position += Vector3.Transform(distanceChange, Matrix.CreateRotationX(mouseRotationX) * Matrix.CreateRotationZ(mouseRotationZ));
        }

        /// <summary>
        /// Update the camera matrices each frame.
        /// </summary>
        /// <param name="gameTime">Time passed since the last call to Update.</param>
        public void Update(GameTime gameTime)
        {
            if (Scripted)
                return;

            float seconds = (float)gameTime.ElapsedGameTime.TotalSeconds;

            MouseState mouseState = Mouse.GetState();

            Vector2 mouseMoved = new Vector2(lastMouseLocation.X - mouseState.X, lastMouseLocation.Y - mouseState.Y);
            lastMouseLocation = new Vector2(mouseState.X, mouseState.Y);

            if (!mouseState.Intersects(App.Engine.GraphicsDevice.Viewport))
            {
                FollowRotation(seconds);

                if (Smooth)
                    Translate(velocityPosition = Vector3.Lerp(velocityPosition, Vector3.Zero, Ease(seconds, SMOOTH_MOVE_SECONDS)));
                else
                    Translate(velocityPosition *= CAMERA_SPEED);

                View = Matrix.Invert(Matrix.CreateRotationX(mouseRotationX) * Matrix.CreateRotationZ(mouseRotationZ) * Matrix.CreateTranslation(Position));

                return;
            }

            bool redeclare = false;
            Vector3 movement = Vector3.Zero;

            if (mouseState.RightButton == ButtonState.Pressed)
                Rotate((mouseMoved.Y * CAMERA_SPEED) / 200.0f, (mouseMoved.X * CAMERA_SPEED) / 200.0f);

            FollowRotation(seconds);

            KeyboardState keyboardState = Keyboard.GetState();

            // Ctrl+S saves, Ctrl+A/W/D are shortcuts too: a held Control must not
            // also walk the camera.
            bool control = keyboardState.IsKeyDown(Keys.LeftControl) || keyboardState.IsKeyDown(Keys.RightControl);

            float step = CAMERA_SPEED * SpeedScale;

            if (!control && keyboardState.IsKeyDown(Keys.W))
            {
                movement += new Vector3(0, 0, -step);

                if (keyboardState.IsKeyDown(Keys.LeftShift))
                    movement += new Vector3(0, 0, -step);
            }

            if (!control && keyboardState.IsKeyDown(Keys.S))
            {
                movement += new Vector3(0, 0, step);

                if (keyboardState.IsKeyDown(Keys.LeftShift))
                    movement += new Vector3(0, 0, step);
            }

            if (!control && keyboardState.IsKeyDown(Keys.A))
            {
                movement += new Vector3(-step, 0, 0);

                if (keyboardState.IsKeyDown(Keys.LeftShift))
                    movement += new Vector3(-step, 0, 0);
            }

            if (!control && keyboardState.IsKeyDown(Keys.D))
            {
                movement += new Vector3(step, 0, 0);

                if (keyboardState.IsKeyDown(Keys.LeftShift))
                    movement += new Vector3(step, 0, 0);
            }

            if (Smooth)
            {
                // ease towards the keys' speed, and back to rest when they are let go
                Translate(velocityPosition = Vector3.Lerp(velocityPosition, movement, Ease(seconds, SMOOTH_MOVE_SECONDS)));
            }
            else
            {
                if (!control && (keyboardState.IsKeyDown(Keys.W) || keyboardState.IsKeyDown(Keys.A) || keyboardState.IsKeyDown(Keys.S) || keyboardState.IsKeyDown(Keys.D)))
                {
                    redeclare = true;

                    velocityPosition = movement;
                }

                if (!redeclare)
                    Translate(velocityPosition *= (CAMERA_SPEED / 1.0f));

                Translate(movement);
            }

            View = Matrix.Invert(Matrix.CreateRotationX(mouseRotationX) * Matrix.CreateRotationZ(mouseRotationZ) * Matrix.CreateTranslation(Position));
        }

        /// <summary>
        /// Updates the viewport.
        /// </summary>
        /// <param name="width">The width.</param>
        /// <param name="height">The height.</param>
        public void UpdateViewport(int width, int height)
        {
            Viewport viewport = App.Engine.GraphicsDevice.Viewport;
            viewport.MinDepth = 1.0f;
            viewport.MaxDepth = 50000.0f;

            Projection = Matrix.CreatePerspectiveFieldOfView(MathHelper.PiOver4, viewport.AspectRatio, viewport.MinDepth, viewport.MaxDepth);
        }

        /// <summary>
        /// Holds the camera at `eye`, looking at `target` (Z up), until the
        /// program ends: used by ShotRunner.
        /// </summary>
        public void SetLookAt(Vector3 eye, Vector3 target)
        {
            Scripted = true;
            Position = eye;
            View = Matrix.CreateLookAt(eye, target, Vector3.UnitZ);
        }

        /// <summary>
        /// Sets the position.
        /// </summary>
        /// <param name="position">The position.</param>
        public void SetPosition(Vector3 position)
        {
            Position = position;

            View = Matrix.Invert(Matrix.CreateRotationX(mouseRotationX) * Matrix.CreateRotationZ(mouseRotationZ) * Matrix.CreateTranslation(Position));
        }
    }
}
