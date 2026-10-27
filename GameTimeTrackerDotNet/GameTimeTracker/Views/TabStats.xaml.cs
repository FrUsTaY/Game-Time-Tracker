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
            
            // Dummy logic representing DB stats calculation for UI 
            long totalSeconds = games.Sum(g => g.TotalSeconds);
            int activeGames = games.Count(g => g.TotalSeconds > 0);

            TxtTotalTime.Text = FormatDuration(totalSeconds);
            TxtTotalGames.Text = activeGames.ToString();

            // Set up chart
            var dummyData = new double[] { 1.2, 0.5, 3.4, 2.1, 0, 4.5, 2.0 };
            
            ActivityChart.Series = new ISeries[]
            {
                new ColumnSeries<double>
                {
                    Values = dummyData,
                    Fill = new LiveChartsCore.SkiaSharpView.Painting.SolidColorPaint(SkiaSharp.SKColors.Cyan)
                }
            };
            
            ActivityChart.XAxes = new[]
            {
                new Axis
                {
                    Labels = new[] { "Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс" }
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