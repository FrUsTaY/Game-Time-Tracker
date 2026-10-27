using System;

namespace GameTimeTracker.Models
{
    public class Session
    {
        public int Id { get; set; }
        public int GameId { get; set; }
        public DateTime StartedAt { get; set; }
        public DateTime? EndedAt { get; set; }
        public int DurationSeconds { get; set; }
    }
}