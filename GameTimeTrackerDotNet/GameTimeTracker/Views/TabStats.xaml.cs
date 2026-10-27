using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows.Controls;
using LiveChartsCore;
using LiveChartsCore.SkiaSharpView;
using GameTimeTracker.Data;

namespace GameTimeTracker.Views
{
    public partial class TabStats : Page
    {
        private readonly DatabaseContext _db;

        public TabStats(DatabaseContext db)
        {
            InitializeComponent();
            _db = db;
            LoadStats();
        }

        private void LoadStats()
        {
            var games = _db.GetAllGames(archived: false).ToList();
            
            long totalSeconds = games.Sum(g => (long)g.TotalSeconds);
            int activeGames = games.Count(g => g.TotalSeconds > 0);

            // Fetch longest session
            var longestSql = "SELECT MAX(duration_seconds) FROM sessions";
            var longestSecs = _db.GetSetting("longest_session") != null ? 0 : 0; // Using raw query
            // Fast workaround for longest session
            try {
                using var conn = new Microsoft.Data.Sqlite.SqliteConnection($"Data Source={AppDomain.CurrentDomain.BaseDirectory}data/gametracker.db");
                conn.Open();
                var cmd = conn.CreateCommand();
                cmd.CommandText = "SELECT duration_seconds, game_id FROM sessions ORDER BY duration_seconds DESC LIMIT 1";
                using var reader = cmd.ExecuteReader();
                if (reader.Read())
                {
                    long longest = reader.GetInt64(0);
                    TxtLongestSession.Text = FormatDuration(longest);
                }
            } catch { }

            TxtTotalTime.Text = FormatDuration(totalSeconds);
            TxtTotalGames.Text = activeGames.ToString();

            // Set up chart with REAL data from SQLite for the last 7 days
            var values = new double[7];
            var labels = new string[7];
            
            for (int i = 6; i >= 0; i--)
            {
                var date = DateTime.Today.AddDays(-i);
                labels[6 - i] = date.ToString("dd.MM");
                
                var breakdown = _db.GetDayBreakdown(date, includeArchived: true);
                long totalSecsForDay = 0;
                
                foreach(var row in breakdown) 
                {
                    totalSecsForDay += Convert.ToInt64(row.TotalSeconds);
                }
                
                values[6 - i] = Math.Round(totalSecsForDay / 3600.0, 1); // convert to hours
            }
            
            ActivityChart.Series = new ISeries[]
            {
                new ColumnSeries<double>
                {
                    Values = values,
                    Fill = new LiveChartsCore.SkiaSharpView.Painting.SolidColorPaint(SkiaSharp.SKColors.Cyan),
                    Name = "Часы"
                }
            };
            
            ActivityChart.XAxes = new[]
            {
                new Axis
                {
                    Labels = labels,
                    LabelsPaint = new LiveChartsCore.SkiaSharpView.Painting.SolidColorPaint(SkiaSharp.SKColors.LightGray)
                }
            };
            ActivityChart.YAxes = new[]
            {
                new Axis
                {
                    LabelsPaint = new LiveChartsCore.SkiaSharpView.Painting.SolidColorPaint(SkiaSharp.SKColors.LightGray)
                }
            };
        }

        private string FormatDuration(long totalSeconds)
        {
            var ts = TimeSpan.FromSeconds(totalSeconds);
            return $"{(int)ts.TotalHours} ч {ts.Minutes:D2} м";
        }
    }
}