using System;
using System.Windows;
using GameTimeTracker.Services;

namespace GameTimeTracker.Views
{
    public partial class SettingsWindow : Window
    {
        private readonly SettingsManager _settings;

        public SettingsWindow(SettingsManager settings)
        {
            InitializeComponent();
            _settings = settings;
            LoadSettings();
        }

        private void LoadSettings()
        {
            ChkAutostart.IsChecked = _settings.Autostart;
            ChkMinimizeToTray.IsChecked = _settings.MinimizeToTrayOnStart;
            
            ChkTrackOnlyActive.IsChecked = _settings.TrackOnlyActiveWindow;
            ChkPauseIdle.IsChecked = _settings.PauseWhenIdle;
            TxtIdleMinutes.Text = _settings.IdleThresholdMinutes.ToString();
            
            ChkNotifyNewGame.IsChecked = _settings.NotifyNewGame;
            ChkNotifyLongSession.IsChecked = _settings.NotifyLongSession;
            TxtLongSessionMinutes.Text = _settings.LongSessionMinutes.ToString();
        }

        private void BtnSave_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                _settings.Autostart = ChkAutostart.IsChecked ?? false;
                _settings.MinimizeToTrayOnStart = ChkMinimizeToTray.IsChecked ?? false;
                
                _settings.TrackOnlyActiveWindow = ChkTrackOnlyActive.IsChecked ?? false;
                _settings.PauseWhenIdle = ChkPauseIdle.IsChecked ?? false;

                if (int.TryParse(TxtIdleMinutes.Text, out int idleMins))
                    _settings.IdleThresholdMinutes = idleMins;

                _settings.NotifyNewGame = ChkNotifyNewGame.IsChecked ?? true;
                _settings.NotifyLongSession = ChkNotifyLongSession.IsChecked ?? true;

                if (int.TryParse(TxtLongSessionMinutes.Text, out int longSession))
                    _settings.LongSessionMinutes = longSession;

                this.Close();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Ошибка сохранения: {ex.Message}");
            }
        }

        private void BtnCancel_Click(object sender, RoutedEventArgs e)
        {
            this.Close();
        }
    }
}