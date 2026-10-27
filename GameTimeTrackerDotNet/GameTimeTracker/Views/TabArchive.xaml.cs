using System;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using GameTimeTracker.Data;

namespace GameTimeTracker.Views
{
    public partial class TabArchive : Page
    {
        private readonly DatabaseContext _db;

        public TabArchive(DatabaseContext db)
        {
            InitializeComponent();
            _db = db;
            LoadArchive();
        }

        public void LoadArchive()
        {
            var archivedGames = _db.GetAllGames(archived: true).Select(g => new ArchivedGameViewModel
            {
                Id = g.Id,
                DisplayName = g.DisplayName,
                ExeName = g.ExeName,
                ArchivedAtFormated = g.ArchivedAt?.ToString("dd.MM.yyyy HH:mm") ?? "Неизвестно"
            }).ToList();

            ArchiveList.ItemsSource = archivedGames;
        }

        private void BtnUnarchive_Click(object sender, RoutedEventArgs e)
        {
            if (sender is Button btn && btn.CommandParameter is int gameId)
            {
                _db.UnarchiveGame(gameId);
                LoadArchive();
                MessageBox.Show("Игра восстановлена из архива!", "Успех", MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }
    }

    public class ArchivedGameViewModel
    {
        public int Id { get; set; }
        public string DisplayName { get; set; } = string.Empty;
        public string ExeName { get; set; } = string.Empty;
        public string ArchivedAtFormated { get; set; } = string.Empty;
    }
}