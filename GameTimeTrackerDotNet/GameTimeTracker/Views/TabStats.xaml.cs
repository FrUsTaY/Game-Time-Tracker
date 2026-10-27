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
                    Labels = labels
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