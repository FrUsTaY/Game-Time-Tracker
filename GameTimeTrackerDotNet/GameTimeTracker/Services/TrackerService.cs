using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using GameTimeTracker.Data;

namespace GameTimeTracker.Services
{
    public class TrackerService : IDisposable
    {
        private readonly DatabaseContext _db;
        private readonly SettingsManager _settings;
        private CancellationTokenSource? _cts;
        private Task? _trackerTask;

        // Active sessions mapping: gameId -> sessionId, startTime
        private readonly ConcurrentDictionary<int, (int SessionId, DateTime StartTime)> _activeSessions;

        // WinAPI for idle detection
        [StructLayout(LayoutKind.Sequential)]
        struct LASTINPUTINFO
        {
            public uint cbSize;
            public uint dwTime;
        }

        [DllImport("user32.dll")]
        static extern bool GetLastInputInfo(ref LASTINPUTINFO plii);

        // WinAPI for active window
        [DllImport("user32.dll")]
        static extern IntPtr GetForegroundWindow();

        [DllImport("user32.dll", SetLastError = true)]
        static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

        public TrackerService(DatabaseContext db, SettingsManager settings)
        {
            _db = db;
            _settings = settings;
            _activeSessions = new ConcurrentDictionary<int, (int, DateTime)>();
        }

        public void Start()
        {
            if (_cts != null) return;
            
            _cts = new CancellationTokenSource();
            _trackerTask = Task.Run(() => RunTracker(_cts.Token));
        }

        public void Stop()
        {
            if (_cts == null) return;

            _cts.Cancel();
            try
            {
                _trackerTask?.Wait(2000); // Wait up to 2 seconds for clean shutdown
            }
            catch (AggregateException) { /* Task cancelled */ }
            catch (Exception) { /* Timeout or other error */ }

            CloseAllSessions();

            _cts.Dispose();
            _cts = null;
        }

        private async Task RunTracker(CancellationToken ct)
        {
            while (!ct.IsCancellationRequested)
            {
                try
                {
                    bool isIdle = CheckIfIdle();
                    
                    if (isIdle && _settings.PauseWhenIdle)
                    {
                        // If idle and pause is enabled, we consider no game is being played.
                        // Close all active sessions.
                        CloseAllSessions();
                        await Task.Delay(2000, ct);
                        continue;
                    }

                    // Get all tracked games from DB
                    var trackedGames = _db.GetAllGames(archived: false)
                                          .ToDictionary(g => g.ExeName.ToLower(), g => g);

                    HashSet<int> currentlyRunningGameIds = new HashSet<int>();

                    if (_settings.TrackOnlyActiveWindow)
                    {
                        var activeGameId = GetForegroundGameId(trackedGames);
                        if (activeGameId.HasValue)
                        {
                            currentlyRunningGameIds.Add(activeGameId.Value);
                        }
                    }
                    else
                    {
                        var runningIds = GetAllRunningGameIds(trackedGames);
                        foreach (var id in runningIds)
                        {
                            currentlyRunningGameIds.Add(id);
                        }
                    }

                    // Start new sessions for running games not already tracked
                    foreach (var gameId in currentlyRunningGameIds)
                    {
                        if (!_activeSessions.ContainsKey(gameId))
                        {
                            int sessionId = _db.StartSession(gameId);
                            _activeSessions[gameId] = (sessionId, DateTime.Now);
                            _db.IncrementLaunchCount(gameId);
                        }
                        else
                        {
                            // Update total seconds for existing session (+1 sec since loop is ~1s)
                            _db.UpdateGameTime(gameId, 1, updateLastLaunched: true);
                        }
                    }

                    // End sessions for games that stopped running
                    var stoppedGames = _activeSessions.Keys.Where(id => !currentlyRunningGameIds.Contains(id)).ToList();
                    foreach (var gameId in stoppedGames)
                    {
                        CloseSession(gameId);
                    }

                }
                catch (TaskCanceledException)
                {
                    break;
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"Tracker error: {ex.Message}");
                }

                await Task.Delay(1000, ct);
            }
        }

        private int? GetForegroundGameId(Dictionary<string, Models.Game> trackedGames)
        {
            IntPtr hwnd = GetForegroundWindow();
            if (hwnd == IntPtr.Zero) return null;

            GetWindowThreadProcessId(hwnd, out uint pid);
            if (pid == 0) return null;

            try
            {
                using var process = Process.GetProcessById((int)pid);
                string exeName = (process.ProcessName + ".exe").ToLower();
                
                if (trackedGames.TryGetValue(exeName, out var game))
                {
                    return game.Id;
                }
                
                // Optional: Auto-detect logic can go here (check pending notifications)
            }
            catch (Exception)
            {
                // Process died or access denied
            }
            return null;
        }

        private IEnumerable<int> GetAllRunningGameIds(Dictionary<string, Models.Game> trackedGames)
        {
            var runningIds = new HashSet<int>();
            var processes = Process.GetProcesses();
            
            foreach (var process in processes)
            {
                try
                {
                    string exeName = (process.ProcessName + ".exe").ToLower();
                    if (trackedGames.TryGetValue(exeName, out var game))
                    {
                        runningIds.Add(game.Id);
                    }
                }
                catch
                {
                    // Ignore access denied on system processes
                }
                finally
                {
                    process.Dispose();
                }
            }
            
            return runningIds;
        }

        private bool CheckIfIdle()
        {
            var lii = new LASTINPUTINFO();
            lii.cbSize = (uint)Marshal.SizeOf(typeof(LASTINPUTINFO));
            if (GetLastInputInfo(ref lii))
            {
                uint envTicks = (uint)Environment.TickCount;
                uint idleTicks = envTicks - lii.dwTime;
                
                double idleSeconds = idleTicks / 1000.0;
                return idleSeconds > (_settings.IdleThresholdMinutes * 60);
            }
            return false;
        }

        private void CloseSession(int gameId)
        {
            if (_activeSessions.TryRemove(gameId, out var sessionInfo))
            {
                int durationSeconds = (int)(DateTime.Now - sessionInfo.StartTime).TotalSeconds;
                _db.EndSession(sessionInfo.SessionId, durationSeconds);
            }
        }

        private void CloseAllSessions()
        {
            var currentKeys = _activeSessions.Keys.ToList();
            foreach (var key in currentKeys)
            {
                CloseSession(key);
            }
        }

        public void Dispose()
        {
            Stop();
        }
    }
}