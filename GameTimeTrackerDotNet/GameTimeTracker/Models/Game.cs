using System;

namespace GameTimeTracker.Models
{
    public class Game
    {
        public int Id { get; set; }
        public required string ExeName { get; set; }
        public required string DisplayName { get; set; }
        public string? ExePath { get; set; }
        public string? IconPath { get; set; }
        public int TotalSeconds { get; set; }
        public DateTime? LastLaunched { get; set; }
        public DateTime AddedAt { get; set; }
        public bool IsArchived { get; set; }
        public DateTime? ArchivedAt { get; set; }
        public int LaunchCount { get; set; }
        public int? DailyLimitMinutes { get; set; }
    }
}