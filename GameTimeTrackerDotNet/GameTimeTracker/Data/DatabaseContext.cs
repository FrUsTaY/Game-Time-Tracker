using System;
using System.Collections.Generic;
using System.Data;
using System.IO;
using Microsoft.Data.Sqlite;
using Dapper;

namespace GameTimeTracker.Data
{
    public class DatabaseContext : IDisposable
    {
        private readonly string _dbPath;
        private readonly SqliteConnection _connection;
        private static readonly int SCHEMA_VERSION = 3;

        public DatabaseContext(string? dbPath = null)
        {
            if (string.IsNullOrEmpty(dbPath) || dbPath == "data/gametracker.db")
            {
                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                dbPath = Path.Combine(baseDir, "data", "gametracker.db");
            }

            _dbPath = dbPath;
            string? dbDir = Path.GetDirectoryName(_dbPath);
            if (!string.IsNullOrEmpty(dbDir) && !Directory.Exists(dbDir))
            {
                Directory.CreateDirectory(dbDir);
            }

            _connection = new SqliteConnection($"Data Source={_dbPath}");
            _connection.Open();

            ConfigureConnection();
            CreateTables();
            MigrateSchema();
            CreateIndexes();
        }

        private void ConfigureConnection()
        {
            _connection.Execute("PRAGMA foreign_keys = ON");
            _connection.Execute("PRAGMA busy_timeout = 5000");
            
            if (_dbPath != ":memory:")
            {
                try
                {
                    _connection.Execute("PRAGMA journal_mode = WAL");
                    _connection.Execute("PRAGMA synchronous = NORMAL");
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"Failed to enable WAL: {ex.Message}");
                }
            }
        }

        private void CreateTables()
        {
            _connection.Execute(@"
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exe_name TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    exe_path TEXT,
                    icon_path TEXT,
                    total_seconds INTEGER DEFAULT 0,
                    last_launched TEXT,
                    added_at TEXT NOT NULL,
                    is_archived INTEGER DEFAULT 0,
                    archived_at TEXT,
                    launch_count INTEGER DEFAULT 0,
                    daily_limit_minutes INTEGER
                )
            ");

            _connection.Execute(@"
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    duration_seconds INTEGER DEFAULT 0,
                    FOREIGN KEY (game_id) REFERENCES games (id) ON DELETE CASCADE
                )
            ");

            _connection.Execute(@"
                CREATE TABLE IF NOT EXISTS ignored_processes (
                    exe_name TEXT PRIMARY KEY,
                    ignored_at TEXT NOT NULL
                )
            ");

            _connection.Execute(@"
                CREATE TABLE IF NOT EXISTS pending_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exe_name TEXT NOT NULL UNIQUE,
                    exe_path TEXT,
                    detected_at TEXT NOT NULL
                )
            ");

            _connection.Execute(@"
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            ");

            var count = _connection.ExecuteScalar<int>("SELECT COUNT(*) FROM settings");
            if (count == 0)
            {
                var defaultSettings = new List<dynamic>
                {
                    new { Key = "autostart", Value = "false" },
                    new { Key = "minimize_to_tray_on_start", Value = "false" },
                    new { Key = "track_only_active_window", Value = "false" },
                    new { Key = "notify_new_game", Value = "true" },
                    new { Key = "notify_long_session", Value = "true" },
                    new { Key = "long_session_minutes", Value = "60" }
                };

                _connection.Execute("INSERT INTO settings (key, value) VALUES (@Key, @Value)", defaultSettings);
            }
        }

        private void CreateIndexes()
        {
            _connection.Execute("CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON sessions (started_at)");
            _connection.Execute("CREATE INDEX IF NOT EXISTS idx_sessions_game_id ON sessions (game_id)");
            _connection.Execute("CREATE INDEX IF NOT EXISTS idx_sessions_ended_at ON sessions (ended_at)");
            _connection.Execute("CREATE INDEX IF NOT EXISTS idx_games_is_archived ON games (is_archived)");
        }

        private void MigrateSchema()
        {
            var userVersion = _connection.ExecuteScalar<int>("PRAGMA user_version");
            if (userVersion < SCHEMA_VERSION)
            {
                // In a full implementation, we would check for column existence and alter tables
                // For simplicity here, the CreateTables query already has the final schema if created fresh.
                // If upgrading, we would implement _ensure_column logic.
                
                _connection.Execute($"PRAGMA user_version = {SCHEMA_VERSION}");
            }
        }

        public string? GetSetting(string key)
        {
            return _connection.ExecuteScalar<string>("SELECT value FROM settings WHERE key = @Key", new { Key = key });
        }

        public void SetSetting(string key, string value)
        {
            var sql = @"
                INSERT INTO settings (key, value) VALUES (@Key, @Value)
                ON CONFLICT(key) DO UPDATE SET value = @Value;
            ";
            _connection.Execute(sql, new { Key = key, Value = value });
        }

        // --- Game Methods ---

        public IEnumerable<Game> GetAllGames(bool archived = false)
        {
            var sql = "SELECT * FROM games WHERE is_archived = @IsArchived ORDER BY total_seconds DESC";
            return _connection.Query<Game>(sql, new { IsArchived = archived ? 1 : 0 });
        }

        public Game? GetGameById(int gameId)
        {
            return _connection.QueryFirstOrDefault<Game>("SELECT * FROM games WHERE id = @Id", new { Id = gameId });
        }

        public Game? GetGameByExeName(string exeName)
        {
            return _connection.QueryFirstOrDefault<Game>("SELECT * FROM games WHERE exe_name = @ExeName", new { ExeName = exeName.ToLower() });
        }

        public void UpdateGameTime(int gameId, int secondsToAdd, bool updateLastLaunched = true)
        {
            var sql = @"
                UPDATE games 
                SET total_seconds = total_seconds + @SecondsToAdd
                " + (updateLastLaunched ? ", last_launched = @Now" : "") + @"
                WHERE id = @Id
            ";
            _connection.Execute(sql, new { Id = gameId, SecondsToAdd = secondsToAdd, Now = DateTime.Now.ToString("O") });
        }

        public void IncrementLaunchCount(int gameId)
        {
            _connection.Execute("UPDATE games SET launch_count = launch_count + 1 WHERE id = @Id", new { Id = gameId });
        }

        public void ArchiveGame(int gameId)
        {
            _connection.Execute("UPDATE games SET is_archived = 1, archived_at = @Now WHERE id = @Id", new { Id = gameId, Now = DateTime.Now.ToString("O") });
        }

        public void UnarchiveGame(int gameId)
        {
            _connection.Execute("UPDATE games SET is_archived = 0, archived_at = NULL WHERE id = @Id", new { Id = gameId });
        }

        public void DeleteGame(int gameId)
        {
            _connection.Execute("DELETE FROM games WHERE id = @Id", new { Id = gameId });
        }
        
        // --- Session Methods ---

        public int StartSession(int gameId)
        {
            var sql = @"
                INSERT INTO sessions (game_id, started_at) VALUES (@GameId, @StartedAt);
                SELECT last_insert_rowid();
            ";
            return _connection.ExecuteScalar<int>(sql, new { GameId = gameId, StartedAt = DateTime.Now.ToString("O") });
        }

        public void EndSession(int sessionId, int durationSeconds)
        {
            var sql = "UPDATE sessions SET ended_at = @EndedAt, duration_seconds = @Duration WHERE id = @Id";
            _connection.Execute(sql, new { Id = sessionId, EndedAt = DateTime.Now.ToString("O"), Duration = durationSeconds });
        }

        public void CleanupZombieSessions()
        {
            // If ended_at is null but application closed improperly
            var sql = "UPDATE sessions SET ended_at = started_at WHERE ended_at IS NULL";
            _connection.Execute(sql);
        }

        public IEnumerable<dynamic> GetDayBreakdown(DateTime targetDate, bool includeArchived = true)
        {
            var dateStr = targetDate.ToString("yyyy-MM-dd");
            var sql = @"
                SELECT g.display_name as GameName, SUM(s.duration_seconds) as TotalSeconds
                FROM sessions s
                JOIN games g ON s.game_id = g.id
                WHERE s.started_at LIKE @DatePrefix
            ";
            
            if (!includeArchived)
                sql += " AND g.is_archived = 0";
                
            sql += " GROUP BY g.id ORDER BY TotalSeconds DESC";
            
            return _connection.Query(sql, new { DatePrefix = dateStr + "%" });
        }
        
        public void AddIgnoredProcess(string exeName)
        {
            _connection.Execute(
                "INSERT OR REPLACE INTO ignored_processes (exe_name, ignored_at) VALUES (@ExeName, @Now)", 
                new { ExeName = exeName.ToLower(), Now = DateTime.Now.ToString("O") }
            );
        }

        public bool IsProcessIgnored(string exeName)
        {
            return _connection.ExecuteScalar<int>("SELECT COUNT(*) FROM ignored_processes WHERE exe_name = @ExeName", new { ExeName = exeName.ToLower() }) > 0;
        }

        public void AddPendingNotification(string exeName, string? exePath)
        {
            _connection.Execute(
                "INSERT OR IGNORE INTO pending_notifications (exe_name, exe_path, detected_at) VALUES (@ExeName, @ExePath, @Now)",
                new { ExeName = exeName.ToLower(), ExePath = exePath, Now = DateTime.Now.ToString("O") }
            );
        }

        public void RemovePendingNotification(string exeName)
        {
            _connection.Execute("DELETE FROM pending_notifications WHERE exe_name = @ExeName", new { ExeName = exeName.ToLower() });
        }

        public void Dispose()
        public int AddGame(string exeName, string displayName, string? exePath)
        {
            var sql = @"
                INSERT INTO games (exe_name, display_name, exe_path, added_at)
                VALUES (@ExeName, @DisplayName, @ExePath, @AddedAt);
                SELECT last_insert_rowid();
            ";

            return _connection.ExecuteScalar<int>(sql, new 
            {
                ExeName = exeName.ToLower(),
                DisplayName = displayName,
                ExePath = exePath,
                AddedAt = DateTime.Now.ToString("O") // ISO 8601
            });
        }

        // Add more methods here corresponding to database.py

        public void Dispose()
        {
            _connection?.Close();
            _connection?.Dispose();
        }
    }
}