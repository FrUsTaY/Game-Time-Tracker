"""
tests/test_new_features.py — тесты улучшений из аудита (v1.3.0).

Покрывают:
  * корректное отнесение сессий, пересекающих полночь, к дням;
  * новую аналитику (серии дней, среднее, сводка);
  * экспорт HTML-отчёта;
  * автоматические ротационные резервные копии;
  * миграцию схемы старых баз данных;
  * WAL-режим и безопасный busy_timeout;
  * пауза трекинга при бездействии (AFK) и дневной лимит;
  * новые настройки и форматирование длительности.

Тесты не требуют Windows-специфичных модулей и выполняются в CI на Linux.
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import SCHEMA_VERSION, Database
from settings import AppSettings
from tracker import GameTracker
from utils import format_duration


class TestDurationFormatting(unittest.TestCase):
    def test_short_style(self):
        self.assertEqual(format_duration(0), "0 сек")
        self.assertEqual(format_duration(45), "45 сек")
        self.assertEqual(format_duration(600), "10 мин")
        self.assertEqual(format_duration(3900), "1 ч 05 мин")
        self.assertEqual(format_duration(-10), "0 сек")

    def test_clock_and_hours_styles(self):
        self.assertEqual(format_duration(65, "clock"), "01:05")
        self.assertEqual(format_duration(3725, "clock"), "01:02:05")
        self.assertEqual(format_duration(5400, "hours"), "1.5 ч")

    def test_unknown_style_raises(self):
        with self.assertRaises(ValueError):
            format_duration(10, "unknown")


class TestDaySplitting(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.game_id = self.db.add_game("night.exe", "Night Game")

    def tearDown(self):
        self.db.close()

    def _insert_session(self, started_at: str, ended_at: str, duration: int) -> None:
        with self.db.lock:
            self.db.conn.execute(
                "INSERT INTO sessions (game_id, started_at, ended_at, duration_seconds) "
                "VALUES (?, ?, ?, ?)",
                (self.game_id, started_at, ended_at, duration),
            )
            self.db.conn.commit()

    def test_split_interval_basic(self):
        start = datetime(2026, 10, 25, 23, 30)
        end = datetime(2026, 10, 26, 1, 15)
        result = Database._split_interval_by_day(start, end, 6300)
        self.assertEqual(result[date(2026, 10, 25)], 1800)
        self.assertEqual(result[date(2026, 10, 26)], 4500)
        self.assertEqual(sum(result.values()), 6300)

    def test_split_interval_within_one_day(self):
        start = datetime(2026, 10, 25, 10, 0)
        end = datetime(2026, 10, 25, 12, 0)
        result = Database._split_interval_by_day(start, end, 7200)
        self.assertEqual(result, {date(2026, 10, 25): 7200})

    def test_split_interval_zero_duration(self):
        self.assertEqual(
            Database._split_interval_by_day(datetime(2026, 1, 1), datetime(2026, 1, 2), 0), {}
        )

    def test_daily_totals_assigns_after_midnight_correctly(self):
        self._insert_session("2026-10-25T23:30:00", "2026-10-26T01:15:00", 6300)
        totals = self.db.get_daily_totals(date(2026, 10, 25), date(2026, 10, 26))
        self.assertEqual(totals[date(2026, 10, 25)], 1800)
        self.assertEqual(totals[date(2026, 10, 26)], 4500)

    def test_period_excludes_out_of_range_part(self):
        """Сессия из предыдущего месяца не попадает в текущий целиком."""
        self._insert_session("2026-09-30T23:00:00", "2026-10-01T01:00:00", 7200)
        october = self.db.get_daily_totals(date(2026, 10, 1), date(2026, 10, 31))
        self.assertEqual(october, {date(2026, 10, 1): 3600})

    def test_day_breakdown_and_multiple_days(self):
        self._insert_session("2026-10-25T22:00:00", "2026-10-26T02:00:00", 14400)
        breakdown = self.db.get_day_breakdown(date(2026, 10, 26))
        self.assertEqual(breakdown, {"Night Game": 7200})

        days = self.db.get_day_breakdowns(date(2026, 10, 25), date(2026, 10, 26))
        self.assertEqual(set(days.keys()), {date(2026, 10, 25), date(2026, 10, 26)})
        self.assertEqual(days[date(2026, 10, 25)]["Night Game"], 7200)

    def test_sessions_with_null_duration_are_ignored(self):
        with self.db.lock:
            self.db.conn.execute(
                "INSERT INTO sessions (game_id, started_at, duration_seconds) VALUES (?, ?, NULL)",
                (self.game_id, "2026-10-25T10:00:00"),
            )
            self.db.conn.commit()
        self.assertEqual(self.db.get_daily_totals(date(2026, 10, 25), date(2026, 10, 25)), {})

    def test_archived_games_filter(self):
        self._insert_session("2026-10-25T10:00:00", "2026-10-25T11:00:00", 3600)
        self.db.archive_game(self.game_id)
        self.assertEqual(
            self.db.get_daily_totals(date(2026, 10, 25), date(2026, 10, 25), include_archived=False),
            {},
        )
        self.assertEqual(
            self.db.get_daily_totals(date(2026, 10, 25), date(2026, 10, 25), include_archived=True),
            {date(2026, 10, 25): 3600},
        )


class TestActivitySummary(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.game_id = self.db.add_game("game.exe", "Game")

    def tearDown(self):
        self.db.close()

    def _add_day(self, day: date, seconds: int) -> None:
        started = datetime.combine(day, datetime.min.time()).replace(hour=12)
        with self.db.lock:
            self.db.conn.execute(
                "INSERT INTO sessions (game_id, started_at, ended_at, duration_seconds) "
                "VALUES (?, ?, ?, ?)",
                (self.game_id, started.isoformat(),
                 (started + timedelta(seconds=seconds)).isoformat(), seconds),
            )
            self.db.conn.commit()

    def test_today_and_week_totals(self):
        today = date.today()
        self._add_day(today, 3600)
        self._add_day(today - timedelta(days=3), 1800)
        self._add_day(today - timedelta(days=10), 7200)

        self.assertEqual(self.db.get_today_seconds(today=today), 3600)
        summary = self.db.get_activity_summary(days=30)
        self.assertEqual(summary['today'], 3600)
        self.assertEqual(summary['week'], 5400)
        self.assertEqual(summary['active_days'], 3)
        self.assertEqual(summary['period_total'], 12600)

    def test_current_streak_counts_consecutive_days(self):
        today = date.today()
        for offset in range(4):
            self._add_day(today - timedelta(days=offset), 600)
        self.assertEqual(self.db.get_current_streak(today), 4)

    def test_streak_allows_yesterday_start(self):
        """Утром, до первого запуска игры, серия не должна обнуляться."""
        today = date.today()
        self._add_day(today - timedelta(days=1), 600)
        self._add_day(today - timedelta(days=2), 600)
        self.assertEqual(self.db.get_current_streak(today), 2)

    def test_streak_zero_without_activity(self):
        self.assertEqual(self.db.get_current_streak(date.today()), 0)

    def test_average_daily(self):
        today = date.today()
        self._add_day(today, 600)
        self._add_day(today - timedelta(days=1), 600)
        self.assertEqual(self.db.get_average_daily_seconds(days=10, today=today), 120)
        self.assertEqual(
            self.db.get_average_daily_seconds(days=10, only_active_days=True, today=today), 600
        )


class TestHtmlReportExport(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.game_id = self.db.add_game("report.exe", "Report <Game>")
        with self.db.lock:
            self.db.conn.execute(
                "INSERT INTO sessions (game_id, started_at, ended_at, duration_seconds) "
                "VALUES (?, ?, ?, ?)",
                (self.game_id, "2026-10-25T20:00:00", "2026-10-25T22:30:00", 9000),
            )
            self.db.conn.commit()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        self.db.close()
        for name in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, name))
        os.rmdir(self.tmpdir)

    def test_report_contains_summary_and_escaped_names(self):
        path = os.path.join(self.tmpdir, "report.html")
        ok = self.db.export_report_html(path, date(2026, 10, 25), date(2026, 10, 26))
        self.assertTrue(ok)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("GameTimeTracker", content)
        self.assertIn("Report &lt;Game&gt;", content)
        self.assertIn("2 ч 30 мин", content)
        self.assertIn("25.10.2026", content)

    def test_report_for_empty_period(self):
        path = os.path.join(self.tmpdir, "empty.html")
        ok = self.db.export_report_html(path, date(2020, 1, 1), date(2020, 1, 3))
        self.assertTrue(ok)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Нет данных за период", content)


class TestBackups(unittest.TestCase):
    def test_rotating_backup_keeps_only_requested_count(self):
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "test.db")
        backup_dir = os.path.join(tmpdir, "backups")
        db = Database(db_path)
        db.add_game("a.exe", "A")
        try:
            for _ in range(3):
                self.assertIsNotNone(db.create_rotating_backup(backup_dir=backup_dir, keep=2))
                # Уникальные имена копий: сдвигаем mtime, чтобы ротация была предсказуемой
                for name in os.listdir(backup_dir):
                    full = os.path.join(backup_dir, name)
                    os.utime(full, (os.path.getmtime(full) - 100, os.path.getmtime(full) - 100))
            backups = [n for n in os.listdir(backup_dir) if n.endswith(".db")]
            self.assertLessEqual(len(backups), 2)
            self.assertTrue(backups)
        finally:
            db.close()
            for name in os.listdir(backup_dir):
                os.remove(os.path.join(backup_dir, name))
            os.rmdir(backup_dir)
            for suffix in ("", "-wal", "-shm"):
                extra = db_path + suffix
                if os.path.exists(extra):
                    os.remove(extra)
            os.rmdir(tmpdir)

    def test_backup_for_memory_db_returns_none(self):
        db = Database(":memory:")
        try:
            self.assertIsNone(db.create_rotating_backup())
        finally:
            db.close()


class TestSchemaMigration(unittest.TestCase):
    def test_legacy_database_is_upgraded(self):
        """Старая БД без колонок is_archived/launch_count должна открываться."""
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "legacy.db")
        legacy = sqlite3.connect(db_path)
        legacy.executescript(
            """
            CREATE TABLE games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exe_name TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                exe_path TEXT,
                icon_path TEXT,
                total_seconds INTEGER DEFAULT 0,
                last_launched TEXT,
                added_at TEXT NOT NULL
            );
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                FOREIGN KEY (game_id) REFERENCES games (id) ON DELETE CASCADE
            );
            INSERT INTO games (exe_name, display_name, added_at)
            VALUES ('legacy.exe', 'Legacy', '2026-01-01T10:00:00');
            INSERT INTO sessions (game_id, started_at, ended_at) VALUES (1, '2026-01-01T10:00:00', '2026-01-01T11:00:00');
            """
        )
        legacy.commit()
        legacy.close()

        db = Database(db_path)
        try:
            self.assertEqual(db.get_schema_version(), SCHEMA_VERSION)
            game = db.get_game_by_exe_name("legacy.exe")
            self.assertIsNotNone(game)
            self.assertEqual(game["is_archived"], 0)
            self.assertIn("launch_count", game)
            # Старые сессии без duration_seconds не должны ронять аналитику
            self.assertEqual(db.get_today_seconds(today=date(2026, 1, 1)), 0)
            # Игра корректно архивируется после миграции
            db.archive_game(game["id"])
            self.assertTrue(db.get_all_games(archived=True))
        finally:
            db.close()
            for name in os.listdir(tmpdir):
                os.remove(os.path.join(tmpdir, name))
            os.rmdir(tmpdir)


class TestConnectionPragmas(unittest.TestCase):
    def test_wal_and_busy_timeout_enabled_for_file_db(self):
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "wal.db")
        db = Database(db_path)
        try:
            journal_mode = db.conn.execute("PRAGMA journal_mode").fetchone()[0].lower()
            self.assertEqual(journal_mode, "wal")
            busy_timeout = db.conn.execute("PRAGMA busy_timeout").fetchone()[0]
            self.assertGreaterEqual(busy_timeout, 5000)
        finally:
            db.close()
            for name in os.listdir(tmpdir):
                os.remove(os.path.join(tmpdir, name))
            os.rmdir(tmpdir)


class TestUpdateGameTimeSemantics(unittest.TestCase):
    def test_flush_does_not_overwrite_last_launched(self):
        db = Database(":memory:")
        try:
            game_id = db.add_game("g.exe", "G")
            db.conn.execute(
                "UPDATE games SET last_launched = ? WHERE id = ?", ("2026-01-01T00:00:00", game_id)
            )
            db.conn.commit()
            db.update_game_time(game_id, 60, touch_last_launched=False)
            game = db.get_game_by_id(game_id)
            self.assertEqual(game["total_seconds"], 60)
            self.assertEqual(game["last_launched"], "2026-01-01T00:00:00")

            db.update_game_time(game_id, 0)
            game = db.get_game_by_id(game_id)
            self.assertNotEqual(game["last_launched"], "2026-01-01T00:00:00")
        finally:
            db.close()


class TestNewSettings(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.settings = AppSettings(self.db)

    def tearDown(self):
        self.db.close()

    def test_defaults(self):
        self.assertFalse(self.settings.pause_when_idle)
        self.assertEqual(self.settings.idle_threshold_minutes, 5)
        self.assertFalse(self.settings.daily_limit_enabled)
        self.assertEqual(self.settings.daily_limit_minutes, 180)
        self.assertTrue(self.settings.backup_on_startup)
        self.assertEqual(self.settings.backup_keep, 7)

    def test_persistence_and_clamping(self):
        self.settings.pause_when_idle = True
        self.settings.idle_threshold_minutes = 0
        self.settings.daily_limit_minutes = 1
        self.settings.backup_keep = 0

        self.settings.invalidate_cache()
        self.assertTrue(self.settings.pause_when_idle)
        self.assertEqual(self.settings.idle_threshold_minutes, 1)
        self.assertEqual(self.settings.daily_limit_minutes, 5)
        self.assertEqual(self.settings.backup_keep, 1)


class TestTrackerIdleAndDailyLimit(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.settings = AppSettings(self.db)
        self.tracker = GameTracker(self.db, self.settings)
        self.game_id = self.db.add_game("idle.exe", "Idle Game")

    def tearDown(self):
        self.tracker.stop()
        self.db.close()

    def test_idle_disabled_by_default(self):
        with patch("tracker.get_idle_seconds", return_value=9999):
            self.assertFalse(self.tracker.is_user_idle())

    def test_idle_detected_when_enabled(self):
        self.settings.pause_when_idle = True
        self.settings.idle_threshold_minutes = 5
        with patch("tracker.get_idle_seconds", return_value=299):
            self.assertFalse(self.tracker.is_user_idle())
        with patch("tracker.get_idle_seconds", return_value=300):
            self.assertTrue(self.tracker.is_user_idle())

    def test_idle_api_unavailable_does_not_pause(self):
        self.settings.pause_when_idle = True
        with patch("tracker.get_idle_seconds", return_value=None):
            self.assertFalse(self.tracker.is_user_idle())

    def test_live_today_seconds_includes_unflushed_progress(self):
        with self.db.lock:
            self.db.conn.execute(
                "INSERT INTO sessions (game_id, started_at, duration_seconds) VALUES (?, ?, ?)",
                (self.game_id, datetime.now().isoformat(), 120),
            )
            self.db.conn.commit()
        self.tracker.active_sessions[self.game_id] = {
            'session_id': 1, 'current_seconds': 300, 'last_flushed_seconds': 120,
        }
        self.assertEqual(self.tracker.get_live_today_seconds(), 300)

    def test_daily_limit_notifies_only_once_per_day(self):
        self.settings.daily_limit_enabled = True
        self.settings.daily_limit_minutes = 60
        with patch.object(GameTracker, 'notify') as notify_mock, \
                patch.object(GameTracker, 'get_live_today_seconds', return_value=3600):
            self.tracker._check_daily_limit()
            self.tracker._check_daily_limit()
        notify_mock.assert_called_once()
        self.assertIn("лимит", notify_mock.call_args[0][1])

    def test_daily_limit_not_triggered_below_threshold(self):
        self.settings.daily_limit_enabled = True
        self.settings.daily_limit_minutes = 60
        with patch.object(GameTracker, 'notify') as notify_mock, \
                patch.object(GameTracker, 'get_live_today_seconds', return_value=3599):
            self.tracker._check_daily_limit()
        notify_mock.assert_not_called()

    def test_daily_limit_disabled_by_default(self):
        with patch.object(GameTracker, 'notify') as notify_mock, \
                patch.object(GameTracker, 'get_live_today_seconds', return_value=99999):
            self.tracker._check_daily_limit()
        notify_mock.assert_not_called()


if __name__ == '__main__':
    unittest.main()
