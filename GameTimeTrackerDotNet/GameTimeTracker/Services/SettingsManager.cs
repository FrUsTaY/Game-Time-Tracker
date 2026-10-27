using System;
using System.Collections.Generic;
using Microsoft.Win32;
using GameTimeTracker.Data;

namespace GameTimeTracker.Services
{
    public class SettingsManager
    {
        private readonly DatabaseContext _db;
        private readonly Dictionary<string, object> _cache;

        public SettingsManager(DatabaseContext db)
        {
            _db = db;
            _cache = new Dictionary<string, object>();
        }

        public void InvalidateCache(string? key = null)
        {
            if (string.IsNullOrEmpty(key))
            {
                _cache.Clear();
            }
            else
            {
                _cache.Remove(key);
            }
        }

        private bool GetBool(string key, bool defaultValue)
        {
            if (_cache.TryGetValue(key, out var cachedValue))
            {
                return (bool)cachedValue;
            }

            string? val = _db.GetSetting(key);
            if (val == null)
            {
                _cache[key] = defaultValue;
                return defaultValue;
            }

            bool res = val.ToLower() == "true";
            _cache[key] = res;
            return res;
        }

        private void SetBool(string key, bool value)
        {
            _db.SetSetting(key, value ? "true" : "false");
            _cache[key] = value;
        }

        private int GetInt(string key, int defaultValue)
        {
            if (_cache.TryGetValue(key, out var cachedValue))
            {
                return (int)cachedValue;
            }

            string? val = _db.GetSetting(key);
            if (val == null || !int.TryParse(val, out int res))
            {
                _cache[key] = defaultValue;
                return defaultValue;
            }

            _cache[key] = res;
            return res;
        }

        private void SetInt(string key, int value)
        {
            _db.SetSetting(key, value.ToString());
            _cache[key] = value;
        }

        private string? GetString(string key, string? defaultValue = null)
        {
            if (_cache.TryGetValue(key, out var cachedValue))
            {
                return (string?)cachedValue;
            }

            string? val = _db.GetSetting(key);
            string? res = val ?? defaultValue;
            _cache[key] = res;
            return res;
        }

        private void SetString(string key, string? value)
        {
            _db.SetSetting(key, value ?? "");
            _cache[key] = value;
        }

        // --- Autostart (Registry) ---

        private void EnableAutostart()
        {
            try
            {
                using RegistryKey? key = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Run", true);
                if (key != null)
                {
                    // For single-file apps, Location is empty. We use Process.GetCurrentProcess().MainModule.FileName
                    string? processPath = System.Diagnostics.Process.GetCurrentProcess().MainModule?.FileName;
                    if (!string.IsNullOrEmpty(processPath))
                    {
                        string appPath = $"\"{processPath}\"";
                        key.SetValue("GameTimeTracker", appPath);
                        SetBool("autostart", true);
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error enabling autostart: {ex.Message}");
            }
        }

        private void DisableAutostart()
        {
            try
            {
                using RegistryKey? key = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Run", true);
                if (key != null)
                {
                    key.DeleteValue("GameTimeTracker", false);
                    SetBool("autostart", false);
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error disabling autostart: {ex.Message}");
            }
        }

        public bool IsAutostartEnabledRegistry()
        {
            try
            {
                using RegistryKey? key = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Run", false);
                if (key != null)
                {
                    return key.GetValue("GameTimeTracker") != null;
                }
            }
            catch
            {
                // Ignore
            }
            return false;
        }

        // --- Properties ---

        public bool Autostart
        {
            get => GetBool("autostart", false);
            set
            {
                if (value) EnableAutostart();
                else DisableAutostart();
            }
        }

        public bool MinimizeToTrayOnStart
        {
            get => GetBool("minimize_to_tray_on_start", false);
            set => SetBool("minimize_to_tray_on_start", value);
        }

        public bool TrackOnlyActiveWindow
        {
            get => GetBool("track_only_active_window", true);
            set => SetBool("track_only_active_window", value);
        }

        public bool NotifyNewGame
        {
            get => GetBool("notify_new_game", true);
            set => SetBool("notify_new_game", value);
        }

        public bool NotifyLongSession
        {
            get => GetBool("notify_long_session", true);
            set => SetBool("notify_long_session", value);
        }

        public int LongSessionMinutes
        {
            get => GetInt("long_session_minutes", 60);
            set => SetInt("long_session_minutes", Math.Max(1, value));
        }

        public bool PauseWhenIdle
        {
            get => GetBool("pause_when_idle", false);
            set => SetBool("pause_when_idle", value);
        }

        public int IdleThresholdMinutes
        {
            get => GetInt("idle_threshold_minutes", 5);
            set => SetInt("idle_threshold_minutes", Math.Max(1, value));
        }

        public bool DailyLimitEnabled
        {
            get => GetBool("daily_limit_enabled", false);
            set => SetBool("daily_limit_enabled", value);
        }

        public int DailyLimitMinutes
        {
            get => GetInt("daily_limit_minutes", 180);
            set => SetInt("daily_limit_minutes", Math.Max(5, value));
        }

        public bool BackupOnStartup
        {
            get => GetBool("backup_on_startup", true);
            set => SetBool("backup_on_startup", value);
        }

        public int BackupKeep
        {
            get => GetInt("backup_keep", 7);
            set => SetInt("backup_keep", Math.Max(1, value));
        }
    }
}