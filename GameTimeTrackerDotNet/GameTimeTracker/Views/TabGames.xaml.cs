using System;
using System.Linq;
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

        private void LoadGames()
        {
            var games = _db.GetAllGames(archived: false).Select(g => new GameViewModel
            {
                Id = g.Id,
                DisplayName = g.DisplayName,
                ExeName = g.ExeName,
                LaunchCount = g.LaunchCount,
                TotalSecondsFormated = FormatDuration(g.TotalSeconds)
            }).ToList();

            GamesList.ItemsSource = games;
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