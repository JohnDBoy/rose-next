using System;
using Microsoft.Xna.Framework;

namespace Map_Editor.Engine
{
    /// <summary>
    /// Yaw / pitch / roll in degrees for a Z-up world, built from and decomposed
    /// into the row-vector matrices XNA uses. Yaw turns about Z (the heading an
    /// object is placed with), pitch tips it about X, roll tips it about Y; roll
    /// is applied first, then pitch, then yaw, so a yaw-only rotation stays a
    /// plain heading change and round-trips exactly.
    /// </summary>
    public static class Rotation
    {
        public static Quaternion FromDegrees(float yaw, float pitch, float roll)
        {
            Matrix m = Matrix.CreateRotationY(MathHelper.ToRadians(roll)) *
                       Matrix.CreateRotationX(MathHelper.ToRadians(pitch)) *
                       Matrix.CreateRotationZ(MathHelper.ToRadians(yaw));

            return Quaternion.Normalize(Quaternion.CreateFromRotationMatrix(m));
        }

        /// <summary>Yaw only, about Z.</summary>
        public static Quaternion Yaw(float degrees)
        {
            return Quaternion.Normalize(Quaternion.CreateFromAxisAngle(Vector3.UnitZ, MathHelper.ToRadians(degrees)));
        }

        /// <summary>
        /// Decomposes a rotation into degrees (yaw, pitch, roll), each in
        /// [-180, 180]. A zero quaternion (the editor's old "no rotation") reads
        /// as (0, 0, 0).
        /// </summary>
        public static Vector3 ToDegrees(Quaternion q)
        {
            if (q.LengthSquared() < 1e-8f)
                return Vector3.Zero;

            Matrix m = Matrix.CreateFromQuaternion(Quaternion.Normalize(q));

            Vector3 y = Vector3.Transform(Vector3.UnitY, m);
            float pitch = (float)Math.Asin(MathHelper.Clamp(y.Z, -1.0f, 1.0f));
            float yaw = (float)Math.Atan2(-y.X, y.Y);

            // Remove yaw and pitch, what is left on the Z axis is the roll.
            Vector3 z = Vector3.Transform(Vector3.UnitZ, m);
            z = Vector3.Transform(z, Matrix.CreateRotationZ(-yaw));
            z = Vector3.Transform(z, Matrix.CreateRotationX(-pitch));
            float roll = (float)Math.Atan2(z.X, z.Z);

            return new Vector3(Wrap(MathHelper.ToDegrees(yaw)), Wrap(MathHelper.ToDegrees(pitch)), Wrap(MathHelper.ToDegrees(roll)));
        }

        /// <summary>
        /// A rotation whose up axis is <paramref name="normal"/>, turned by
        /// <paramref name="yawDegrees"/> about the original Z first. Used to stand an
        /// object on a slope.
        /// </summary>
        public static Quaternion OnSlope(Vector3 normal, float yawDegrees)
        {
            normal = Vector3.Normalize(normal);
            Matrix yaw = Matrix.CreateRotationZ(MathHelper.ToRadians(yawDegrees));

            float dot = MathHelper.Clamp(Vector3.Dot(Vector3.UnitZ, normal), -1.0f, 1.0f);
            float angle = (float)Math.Acos(dot);
            if (angle < 1e-4f)
                return Quaternion.Normalize(Quaternion.CreateFromRotationMatrix(yaw));

            Vector3 axis = Vector3.Cross(Vector3.UnitZ, normal);
            if (axis.LengthSquared() < 1e-8f)
                axis = Vector3.UnitX;
            axis.Normalize();

            return Quaternion.Normalize(Quaternion.CreateFromRotationMatrix(yaw * Matrix.CreateFromAxisAngle(axis, angle)));
        }

        public static float Wrap(float degrees)
        {
            degrees %= 360.0f;
            if (degrees > 180.0f) degrees -= 360.0f;
            if (degrees <= -180.0f) degrees += 360.0f;
            return degrees;
        }

        public static float Snap(float degrees, float step)
        {
            if (step <= 0.0f)
                return degrees;
            return Wrap((float)Math.Round(degrees / step) * step);
        }

        /// <summary>
        /// Checks that build and decompose agree, and that OnSlope stands Z on the
        /// normal. Returns a message on failure, null when everything holds.
        /// </summary>
        public static string SelfTest()
        {
            Random r = new Random(1234);
            for (int i = 0; i < 2000; i++)
            {
                float yaw = (float)(r.NextDouble() * 360.0 - 180.0);
                float pitch = (float)(r.NextDouble() * 170.0 - 85.0);
                float roll = (float)(r.NextDouble() * 360.0 - 180.0);
                if (i < 8)
                {
                    // Axis-aligned headings must come back exactly.
                    yaw = i * 45.0f - 180.0f;
                    pitch = 0.0f;
                    roll = 0.0f;
                }

                Quaternion q = FromDegrees(yaw, pitch, roll);
                Vector3 back = ToDegrees(q);
                Quaternion q2 = FromDegrees(back.X, back.Y, back.Z);

                float d = Math.Min((q - q2).Length(), (q + q2).Length());
                if (d > 1e-3f)
                    return string.Format("rotation round trip failed for ({0}, {1}, {2}) -> ({3}, {4}, {5}), distance {6}", yaw, pitch, roll, back.X, back.Y, back.Z, d);
                if (i < 8 && Math.Abs(Wrap(back.X - yaw)) > 1e-3f)
                    return string.Format("yaw {0} decomposed as {1}", yaw, back.X);

                Vector3 n = new Vector3((float)(r.NextDouble() - 0.5), (float)(r.NextDouble() - 0.5), 1.0f);
                Vector3 up = Vector3.Transform(Vector3.UnitZ, OnSlope(n, yaw));
                n.Normalize();
                if (Vector3.Distance(up, n) > 1e-3f)
                    return string.Format("OnSlope put Z at {0}, wanted {1}", up, n);
            }

            Quaternion yawOnly = Yaw(90.0f);
            Vector3 x = Vector3.Transform(Vector3.UnitX, yawOnly);
            if (Vector3.Distance(x, Vector3.UnitY) > 1e-3f)
                return string.Format("Yaw(90) took X to {0}, wanted +Y", x);

            return null;
        }
    }
}
