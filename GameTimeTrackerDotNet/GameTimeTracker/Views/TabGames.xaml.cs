using System;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using GameTimeTracker.Data;

namespace GameTimeTracker.Views
{
    public partial class TabGames : Page
    {
        private readonly DatabaseContext _db;

        public TabGames(DatabaseContext db)
        {
            InitializeComponent();
            _db = db;
            LoadGames();
        }

        private void LoadGames(string searchQuery = "")
        {
            var games = _db.GetAllGames(archived: false).Select(g => new GameViewModel
            {
                Id = g.Id,
                DisplayName = g.DisplayName ?? "Unknown",
                ExeName = g.ExeName ?? "unknown.exe",
                LaunchCount = g.LaunchCount,
                TotalSecondsFormated = FormatDuration(g.TotalSeconds)
            });

            if (!string.IsNullOrWhiteSpace(searchQuery) && !searchQuery.Equals("поиск игр...", StringComparison.OrdinalIgnoreCase))
            {
                searchQuery = searchQuery.ToLower();
                games = games.Where(g => g.DisplayName.ToLower().Contains(searchQuery) || g.ExeName.ToLower().Contains(searchQuery));
            }

            GamesList.ItemsSource = games.ToList();
        }

        private void SearchBox_GotFocus(object sender, RoutedEventArgs e)
        {
            if (SearchBox.Text == "Поиск игр...")
            {
                SearchBox.Text = "";
            }
        }

        private void SearchBox_LostFocus(object sender, RoutedEventArgs e)
        {
            if (string.IsNullOrWhiteSpace(SearchBox.Text))
            {
                SearchBox.Text = "Поиск игр...";
            }
        }

        private void SearchBox_TextChanged(object sender, TextChangedEventArgs e)
        {
            if (SearchBox.Text != "Поиск игр...")
            {
                LoadGames(SearchBox.Text);
            }
        }

        private void BtnAddGame_Click(object sender, RoutedEventArgs e)
        {
            var dialog = new Microsoft.Win32.OpenFileDialog
            {
                Filter = "Исполняемые файлы (*.exe)|*.exe|Все файлы (*.*)|*.*",
                Title = "Выберите игру или программу для отслеживания"
            };

            if (dialog.ShowDialog() == true)
            {
                string path = dialog.FileName;
                string exeName = System.IO.Path.GetFileName(path);
                string displayName = System.IO.Path.GetFileNameWithoutExtension(path);

                if (_db.GetGameByExeName(exeName) != null)
                {
                    MessageBox.Show("Эта игра уже добавлена!", "Внимание", MessageBoxButton.OK, MessageBoxImage.Warning);
                    return;
                }

                _db.AddGame(exeName, displayName, path);
                LoadGames(SearchBox.Text);
            }
        }

        private void MenuArchive_Click(object sender, RoutedEventArgs e)
        {
            if (sender is MenuItem item && item.CommandParameter is GameViewModel game)
            {
                _db.ArchiveGame(game.Id);
                LoadGames(SearchBox.Text);
            }
        }

        private void MenuDelete_Click(object sender, RoutedEventArgs e)
        {
            if (sender is MenuItem item && item.CommandParameter is GameViewModel game)
            {
                if (MessageBox.Show($"Точно удалить игру '{game.DisplayName}' и всю её статистику?", "Подтверждение", MessageBoxButton.YesNo, MessageBoxImage.Question) == MessageBoxResult.Yes)
                {
                    _db.DeleteGame(game.Id);
                    LoadGames(SearchBox.Text);
                }
            }
        }

        private string FormatDuration(int totalSeconds)
        {
            var ts = TimeSpan.FromSeconds(totalSeconds);
            if (ts.TotalHours >= 1)
                return $"{(int)ts.TotalHours} ч {ts.Minutes:D2} м";
            if (ts.Minutes > 0)
                return $"{ts.Minutes} м {ts.Seconds:D2} с";
            return $"{ts.Seconds} с";
        }
    }

    public class GameViewModel
    {
        public int Id { get; set; }
        public string DisplayName { get; set; } = string.Empty;
        public string ExeName { get; set; } = string.Empty;
        public int LaunchCount { get; set; }
        public string TotalSecondsFormated { get; set; } = string.Empty;
    }
}