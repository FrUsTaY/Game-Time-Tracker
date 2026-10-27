using System;
using System.Linq;
using System.Windows.Controls;
using GameTimeTracker.Data;

namespace GameTimeTracker.Views
{
    public partial class TabCalendar : Page
    {
        private readonly DatabaseContext _db;

        public TabCalendar(DatabaseContext db)
        {
            InitializeComponent();
            _db = db;
            
            ActivityCalendar.SelectedDate = DateTime.Today;
        }

        private void ActivityCalendar_SelectedDatesChanged(object sender, SelectionChangedEventArgs e)
        {
            if (ActivityCalendar.SelectedDate.HasValue)
            {
                LoadDayBreakdown(ActivityCalendar.SelectedDate.Value);
            }
        }

        private void LoadDayBreakdown(DateTime date)
        {
            TxtSelectedDate.Text = $"Активность за {date.ToString("dd MMMM yyyy")}";
            
            var breakdown = _db.GetDayBreakdown(date, includeArchived: true).Select(row => new DayActivityViewModel
            {
                GameName = row.GameName,
                DurationFormated = FormatDuration((long)row.TotalSeconds)
            }).ToList();

            if (breakdown.Any())
            {
                DayBreakdownList.ItemsSource = breakdown;
                DayBreakdownList.Visibility = System.Windows.Visibility.Visible;
                TxtNoActivity.Visibility = System.Windows.Visibility.Collapsed;
            }
            else
            {
                DayBreakdownList.ItemsSource = null;
                DayBreakdownList.Visibility = System.Windows.Visibility.Collapsed;
                TxtNoActivity.Visibility = System.Windows.Visibility.Visible;
            }
        }

        private string FormatDuration(long totalSeconds)
        {
            var ts = TimeSpan.FromSeconds(totalSeconds);
            if (ts.TotalHours >= 1)
                return $"{(int)ts.TotalHours} ч {ts.Minutes:D2} м";
            if (ts.Minutes > 0)
                return $"{ts.Minutes} м";
            return $"{ts.Seconds} с";
        }
    }

    public class DayActivityViewModel
    {
        public string GameName { get; set; } = string.Empty;
        public string DurationFormated { get; set; } = string.Empty;
    }
}