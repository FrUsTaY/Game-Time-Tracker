using System;
using System.ComponentModel;
using System.Windows;
using GameTimeTracker.Data;
using GameTimeTracker.Services;

namespace GameTimeTracker
{
    public partial class MainWindow : Window
    {
        private DatabaseContext? _db;
        private SettingsManager? _settings;
        private TrackerService? _tracker;
        private bool _isExplicitClose = false;

        public MainWindow()
        {
            InitializeComponent();
            InitializeServices();
        }

        private void InitializeServices()
        {
            try
            {
                _db = new DatabaseContext();
                _settings = new SettingsManager(_db);
                _tracker = new TrackerService(_db, _settings);

                // Clean zombie sessions on startup
                _db.CleanupZombieSessions();

                _tracker.Start();

                // Check minimize to tray setting on startup
                if (_settings.MinimizeToTrayOnStart)
                {
                    this.WindowState = WindowState.Minimized;
                    HideToTray();
                }

                // Setup tabs
                GamesFrame.Navigate(new Views.TabGames(_db));
                StatsFrame.Navigate(new Views.TabStats(_db));
                CalendarFrame.Navigate(new Views.TabCalendar(_db));
                ArchiveFrame.Navigate(new Views.TabArchive(_db));
                AboutFrame.Navigate(new Views.TabAbout());
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Failed to initialize: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void Settings_Click(object sender, RoutedEventArgs e)
        {
            if (_settings != null)
            {
                var settingsWindow = new Views.SettingsWindow(_settings);
                settingsWindow.Owner = this;
                settingsWindow.ShowDialog();
            }
        }

        private void Window_StateChanged(object sender, EventArgs e)
        {
            if (this.WindowState == WindowState.Minimized)
            {
                HideToTray();
            }
        }

        private void HideToTray()
        {
            this.ShowInTaskbar = false;
            this.Visibility = Visibility.Hidden;
            TrayIcon.Visibility = Visibility.Visible;
        }

        private void ShowFromTray()
        {
            this.ShowInTaskbar = true;
            this.Visibility = Visibility.Visible;
            this.WindowState = WindowState.Normal;
            TrayIcon.Visibility = Visibility.Collapsed;
            this.Activate();
        }

        private void TrayIcon_TrayMouseDoubleClick(object sender, RoutedEventArgs e)
        {
            ShowFromTray();
        }

        private void MenuItem_Open_Click(object sender, RoutedEventArgs e)
        {
            ShowFromTray();
        }

        private void MenuItem_Exit_Click(object sender, RoutedEventArgs e)
        {
            _isExplicitClose = true;
            Application.Current.Shutdown();
        }

        private void Window_Closing(object sender, CancelEventArgs e)
        {
            if (!_isExplicitClose)
            {
                e.Cancel = true;
                this.WindowState = WindowState.Minimized;
                HideToTray();
            }
        }

        protected override void OnClosed(EventArgs e)
        {
            TrayIcon?.Dispose();
            _tracker?.Stop();
            _tracker?.Dispose();
            _db?.Dispose();
            base.OnClosed(e);
        }
    }
}