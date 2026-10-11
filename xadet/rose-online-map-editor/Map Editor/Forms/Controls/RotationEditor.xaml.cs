using System;
using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using Map_Editor.Engine;
using Map_Editor.Misc;
using Microsoft.Xna.Framework;

namespace Map_Editor.Forms.Controls
{
    /// <summary>
    /// Yaw / pitch / roll in degrees, each with a slider and a text field, plus
    /// the yaw snap step shared with placement. <see cref="RotationChanged"/>
    /// fires while a slider is dragged (live preview); <see cref="RotationCommitted"/>
    /// once the drag, key press or text entry is done (one undo entry).
    /// </summary>
    public partial class RotationEditor : UserControl
    {
        public static readonly float[] SNAP_STEPS = new float[] { 0.0f, 15.0f, 45.0f, 90.0f };

        public event Action<Quaternion> RotationChanged;
        public event Action<Quaternion> RotationCommitted;
        public event Action SnapStepChanged;

        private bool updating;
        private Quaternion committed = Quaternion.Identity;
        private Quaternion current = Quaternion.Identity;

        public RotationEditor()
        {
            InitializeComponent();

            foreach (System.Windows.Forms.TextBox box in new System.Windows.Forms.TextBox[] { YawBox, PitchBox, RollBox })
            {
                box.KeyDown += Box_KeyDown;
                box.LostFocus += Box_LostFocus;
            }

            int snap = 0;
            try { snap = ConfigurationManager.GetValue<int>("Placement", "YawSnap"); }
            catch { }
            if (snap < 0 || snap >= SNAP_STEPS.Length) snap = 0;
            SnapCombo.SelectedIndex = snap;
            ApplySnapToSlider();

            SetRotation(Quaternion.Identity);
        }

        public System.Windows.Forms.TextBox YawBox
        {
            get { return (System.Windows.Forms.TextBox)YawHost.Child; }
        }

        public System.Windows.Forms.TextBox PitchBox
        {
            get { return (System.Windows.Forms.TextBox)PitchHost.Child; }
        }

        public System.Windows.Forms.TextBox RollBox
        {
            get { return (System.Windows.Forms.TextBox)RollHost.Child; }
        }

        /// <summary>Applies what the degree fields hold (Enter / leaving a field do the same).</summary>
        public void CommitTyped()
        {
            ApplyBoxes();
        }

        /// <summary>The yaw step in degrees, 0 when snapping is off.</summary>
        public float SnapStep
        {
            get
            {
                int i = SnapCombo.SelectedIndex;
                return (i >= 0 && i < SNAP_STEPS.Length) ? SNAP_STEPS[i] : 0.0f;
            }
        }

        public Quaternion Rotation
        {
            get { return current; }
        }

        /// <summary>Shows a rotation without raising events.</summary>
        public void SetRotation(Quaternion rotation)
        {
            updating = true;
            try
            {
                committed = current = rotation;
                Vector3 degrees = Engine.Rotation.ToDegrees(rotation);
                YawSlider.Value = degrees.X;
                PitchSlider.Value = degrees.Y;
                RollSlider.Value = degrees.Z;
                YawBox.Text = Format(degrees.X);
                PitchBox.Text = Format(degrees.Y);
                RollBox.Text = Format(degrees.Z);
            }
            finally
            {
                updating = false;
            }
        }

        public void SetEnabled(bool enabled)
        {
            YawSlider.IsEnabled = PitchSlider.IsEnabled = RollSlider.IsEnabled = enabled;
            YawBox.Enabled = PitchBox.Enabled = RollBox.Enabled = enabled;
            ResetButton.IsEnabled = enabled;
        }

        private static string Format(float degrees)
        {
            return Math.Round(degrees, 1).ToString("0.#", CultureInfo.InvariantCulture);
        }

        private void ApplySnapToSlider()
        {
            float step = SnapStep;
            YawSlider.IsSnapToTickEnabled = step > 0.0f;
            YawSlider.TickFrequency = step > 0.0f ? step : 1.0;
            YawSlider.SmallChange = step > 0.0f ? step : 1.0;
            YawSlider.LargeChange = step > 0.0f ? step : 15.0;
            PitchSlider.SmallChange = RollSlider.SmallChange = 1.0;
            PitchSlider.LargeChange = RollSlider.LargeChange = 15.0;
        }

        private void FromSliders(bool commit)
        {
            if (updating)
                return;

            updating = true;
            try
            {
                YawBox.Text = Format((float)YawSlider.Value);
                PitchBox.Text = Format((float)PitchSlider.Value);
                RollBox.Text = Format((float)RollSlider.Value);
            }
            finally
            {
                updating = false;
            }

            current = Engine.Rotation.FromDegrees((float)YawSlider.Value, (float)PitchSlider.Value, (float)RollSlider.Value);
            if (RotationChanged != null)
                RotationChanged(current);
            if (commit)
                Commit();
        }

        private void Commit()
        {
            if (current == committed)
                return;
            committed = current;
            if (RotationCommitted != null)
                RotationCommitted(current);
        }

        private void Slider_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
        {
            FromSliders(false);
        }

        private void Slider_PreviewMouseUp(object sender, MouseButtonEventArgs e)
        {
            Commit();
        }

        private void Slider_PreviewKeyUp(object sender, KeyEventArgs e)
        {
            Commit();
        }

        private void Box_KeyDown(object sender, System.Windows.Forms.KeyEventArgs e)
        {
            if (e.KeyCode == System.Windows.Forms.Keys.Enter)
            {
                ApplyBoxes();
                e.SuppressKeyPress = true;
                e.Handled = true;
            }
            else if (e.KeyCode == System.Windows.Forms.Keys.Escape)
            {
                SetRotation(committed);
                e.SuppressKeyPress = true;
                e.Handled = true;
            }
        }

        private void Box_LostFocus(object sender, EventArgs e)
        {
            ApplyBoxes();
        }

        private void ApplyBoxes()
        {
            if (updating)
                return;

            float yaw, pitch, roll;
            if (!TryParse(YawBox.Text, (float)YawSlider.Value, out yaw) ||
                !TryParse(PitchBox.Text, (float)PitchSlider.Value, out pitch) ||
                !TryParse(RollBox.Text, (float)RollSlider.Value, out roll))
            {
                SetRotation(current);
                return;
            }

            yaw = Engine.Rotation.Wrap(yaw);
            pitch = Engine.Rotation.Wrap(pitch);
            roll = Engine.Rotation.Wrap(roll);

            updating = true;
            try
            {
                YawSlider.Value = yaw;
                PitchSlider.Value = pitch;
                RollSlider.Value = roll;
            }
            finally
            {
                updating = false;
            }
            FromSliders(true);
        }

        private static bool TryParse(string text, float fallback, out float value)
        {
            text = (text ?? string.Empty).Trim().Replace("°", string.Empty);
            if (text.Length == 0)
            {
                value = fallback;
                return true;
            }
            return float.TryParse(text, NumberStyles.Float, CultureInfo.InvariantCulture, out value) ||
                   float.TryParse(text, NumberStyles.Float, CultureInfo.CurrentCulture, out value);
        }

        private void Reset_Click(object sender, RoutedEventArgs e)
        {
            updating = true;
            try
            {
                YawSlider.Value = 0;
                PitchSlider.Value = 0;
                RollSlider.Value = 0;
            }
            finally
            {
                updating = false;
            }
            FromSliders(true);
        }

        private void SnapCombo_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            if (YawSlider == null)
                return;
            ApplySnapToSlider();
            try
            {
                ConfigurationManager.SetValue("Placement", "YawSnap", SnapCombo.SelectedIndex);
                ConfigurationManager.SaveConfig();
            }
            catch
            {
            }
            if (SnapStepChanged != null)
                SnapStepChanged();
        }
    }
}
