"""
tests/test_backlog_features.py — тесты улучшений из бэклога (v1.3.0).

Покрывают:
  * индивидуальные дневные лимиты по играм (БД, миграция, уведомления трекера);
  * еженедельную сводку (агрегаты в БД + чистые функции форматирования);
  * полный экспорт/импорт данных в JSON (перенос между машинами);
  * троттлинг проверки лимитов.

Тесты не требуют Windows-специфичных модулей и GUI.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import digest
from database import SCHEMA_VERSION, Database
from settings import AppSettings
from tracker import GameTracker


class TestGameDailyLimits(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.game_id = self.db.add_game("limit.exe", "Limit Game")

    def tearDown(self):
        self.db.close()

    def test_set_and_reset_limit(self):
        self.assertIsNone(self.db.get_game_by_id(self.game_id)["daily_limit_minutes"])

        self.db.set_game_daily_limit(self.game_id, 90)
        game = self.db.get_game_by_id(self.game_id)
        self.assertEqual(game["daily_limit_minutes"], 90)

        self.db.set_game_daily_limit(self.game_id, None)
        self.assertIsNone(self.db.get_game_by_id(self.game_id)["daily_limit_minutes"])

    def test_limit_is_clamped_and_listed(self):
        self.db.set_game_daily_limit(self.game_id, 0)
        self.assertEqual(self.db.get_games_with_limits()[0]["daily_limit_minutes"], 1)

        archived_id = self.db.add_game("old.exe", "Old Game")
        self.db.set_game_daily_limit(archived_id, 30)
        self.db.archive_game(archived_id)

        active_titles = [g["display_name"] for g in self.db.get_games_with_limits()]
        self.assertEqual(active_titles, ["Limit Game"])
        all_titles = [g["display_name"] for g in self.db.get_games_with_limits(include_archived=True)]
        self.assertEqual(sorted(all_titles), ["Limit Game", "Old Game"])

    def test_game_seconds_for_day_splits_midnight_session(self):
        with self.db.lock:
            self.db.conn.execute(
                "INSERT INTO sessions (game_id, started_at, ended_at, duration_seconds) "
                "VALUES (?, ?, ?, ?)",
                (self.game_id, "2026-10-25T23:30:00", "2026-10-26T01:15:00", 6300),
            )
            self.db.conn.commit()

        self.assertEqual(self.db.get_game_seconds_for_day(self.game_id, date(2026, 10, 25)), 1800)
        self.assertEqual(self.db.get_game_seconds_for_day(self.game_id, date(2026, 10, 26)), 4500)
        self.assertEqual(self.db.get_game_seconds_for_day(999999, date(2026, 10, 26)), 0)

    def test_schema_version_is_current(self):
        self.assertEqual(self.db.get_schema_version(), SCHEMA_VERSION)
        self.assertIn("daily_limit_minutes", self.db.get_game_by_id(self.game_id))


class TestTrackerGameLimitNotifications(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.settings = AppSettings(self.db)
        self.tracker = GameTracker(self.db, self.settings)
        self.game_id = self.db.add_game("limit.exe", "Limit Game")

    def tearDown(self):
        self.tracker.stop()
        self.db.close()

    def test_no_notification_without_limit(self):
        with patch.object(GameTracker, 'notify') as notify_mock, \
                patch.object(Database, 'get_game_seconds_for_day', return_value=99999):
            self.tracker._check_game_limits()
        notify_mock.assert_not_called()

    def test_notification_only_once_per_day(self):
        self.db.set_game_daily_limit(self.game_id, 60)
        with patch.object(GameTracker, 'notify') as notify_mock, \
                patch.object(Database, 'get_game_seconds_for_day', return_value=3600):
            self.tracker._check_game_limits()
            self.tracker._check_game_limits()
        notify_mock.assert_called_once()
        self.assertIn("Limit Game", notify_mock.call_args[0][1])

    def test_no_notification_below_limit(self):
        self.db.set_game_daily_limit(self.game_id, 60)
        with patch.object(GameTracker, 'notify') as notify_mock, \
                patch.object(Database, 'get_game_seconds_for_day', return_value=3599):
            self.tracker._check_game_limits()
        notify_mock.assert_not_called()

    def test_unflushed_progress_counts_towards_limit(self):
        self.db.set_game_daily_limit(self.game_id, 1)
        self.tracker.active_sessions[self.game_id] = {
            'session_id': 1, 'current_seconds': 60, 'last_flushed_seconds': 0,
        }
        with patch.object(GameTracker, 'notify') as notify_mock, \
                patch.object(Database, 'get_game_seconds_for_day', return_value=0):
            self.tracker._check_game_limits()
        notify_mock.assert_called_once()

    def test_check_limits_is_throttled(self):
        self.settings.daily_limit_enabled = True
        with patch.object(GameTracker, '_check_daily_limit') as daily_mock, \
                patch.object(GameTracker, '_check_game_limits') as game_mock:
            self.tracker._check_limits()
            self.tracker._check_limits()  # сразу второй вызов — должен быть пропущен
        self.assertEqual(daily_mock.call_count, 1)
        self.assertEqual(game_mock.call_count, 1)


class TestWeeklyDigest(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.game_a = self.db.add_game("a.exe", "Game A")
        self.game_b = self.db.add_game("b.exe", "Game B")

    def tearDown(self):
        self.db.close()

    def _add_session(self, game_id: int, day: date, seconds: int) -> None:
        start = datetime.combine(day, datetime.min.time()).replace(hour=18)
        with self.db.lock:
            self.db.conn.execute(
                "INSERT INTO sessions (game_id, started_at, ended_at, duration_seconds) "
                "VALUES (?, ?, ?, ?)",
                (game_id, start.isoformat(),
                 (start + timedelta(seconds=seconds)).isoformat(), seconds),
            )
            self.db.conn.commit()

    def test_digest_aggregates(self):
        today = date.today()
        self._add_session(self.game_a, today, 7200)
        self._add_session(self.game_a, today - timedelta(days=2), 3600)
        self._add_session(self.game_b, today - timedelta(days=1), 1800)
        # Прошлая неделя — для расчёта динамики
        self._add_session(self.game_b, today - timedelta(days=8), 3600)

        summary = self.db.get_weekly_digest(today)
        self.assertEqual(summary['total_seconds'], 7200 + 3600 + 1800)
        self.assertEqual(summary['prev_week_seconds'], 3600)
        self.assertEqual(summary['delta_seconds'], 9000)
        self.assertEqual(summary['top_game'], "Game A")
        self.assertEqual(summary['top_game_seconds'], 10800)
        self.assertEqual(summary['active_days'], 3)
        self.assertEqual(summary['best_day'], today)

    def test_empty_digest(self):
        summary = self.db.get_weekly_digest(date.today())
        self.assertEqual(summary['total_seconds'], 0)
        self.assertEqual(summary['top_game'], "")
        self.assertIsNone(summary['best_day'])

    def test_digest_due_logic(self):
        today = date(2026, 10, 26)
        self.assertTrue(digest.is_weekly_digest_due(None, today))
        self.assertTrue(digest.is_weekly_digest_due("2026-10-19", today))
        self.assertFalse(digest.is_weekly_digest_due("2026-10-21", today))
        self.assertFalse(digest.is_weekly_digest_due("2026-11-05", today))  # дата из будущего
        self.assertFalse(digest.is_weekly_digest_due("не дата", today - timedelta(days=100))
                         is False)  # мусор трактуется как «не отправляли»

    def test_format_digest_message(self):
        message = digest.format_weekly_digest({
            'total_seconds': 45000,
            'delta_seconds': 7200,
            'top_game': 'Dota 2',
            'top_game_seconds': 21600,
            'active_days': 5,
            'streak': 6,
        })
        self.assertIn("12 ч 30 мин", message)
        self.assertIn("больше, чем на прошлой", message)
        self.assertIn("Dota 2", message)
        self.assertIn("5 из 7", message)
        self.assertIn("6 дн.", message)

    def test_format_digest_without_activity(self):
        message = digest.format_weekly_digest({'total_seconds': 0})
        self.assertIn("активности не было", message)


class TestIntegrityCheck(unittest.TestCase):
    def test_fresh_database_is_ok(self):
        db = Database(":memory:")
        try:
            self.assertTrue(db.check_integrity())
            self.assertTrue(db.check_integrity(quick=False))
        finally:
            db.close()

    def test_database_errors_are_reported_as_corruption(self):
        import sqlite3

        class BrokenConnection:
            def execute(self, *_args, **_kwargs):
                raise sqlite3.DatabaseError("database disk image is malformed")

        db = Database(":memory:")
        real_conn = db.conn
        try:
            db.conn = BrokenConnection()
            self.assertFalse(db.check_integrity())
        finally:
            db.conn = real_conn
            db.close()


class TestJsonExportImport(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "source.db")
        self.db = Database(self.db_path)
        self.game_id = self.db.add_game("game.exe", "Game", "C:\\Games\\game.exe")
        self.db.update_game_time(self.game_id, 3600)
        session_id = self.db.start_session(self.game_id)
        self.db.end_session(session_id, 1800)
        self.db.set_game_daily_limit(self.game_id, 90)
        self.db.add_ignored_process("nope.exe")
        self.export_path = os.path.join(self.tmpdir, "data.json")

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_export_creates_valid_json(self):
        self.assertTrue(self.db.export_data_json(self.export_path))
        with open(self.export_path, encoding="utf-8") as f:
            payload = json.load(f)
        self.assertEqual(payload["format"], "gametimetracker-data")
        self.assertEqual(len(payload["games"]), 1)
        self.assertEqual(len(payload["sessions"]), 1)
        self.assertEqual(payload["games"][0]["exe_name"], "game.exe")

    def test_roundtrip_restores_data(self):
        self.assertTrue(self.db.export_data_json(self.export_path))
        target = Database(":memory:")
        try:
            result = target.import_data_json(self.export_path)
            self.assertEqual(result["games"], 1)
            self.assertEqual(result["sessions"], 1)
            self.assertEqual(result["ignored"], 1)

            game = target.get_game_by_exe_name("game.exe")
            self.assertIsNotNone(game)
            self.assertEqual(game["display_name"], "Game")
            self.assertEqual(game["total_seconds"], 3600)
            self.assertEqual(game["daily_limit_minutes"], 90)
            self.assertEqual(len(target.get_active_sessions()), 0)
            self.assertTrue(target.is_process_ignored("nope.exe"))
        finally:
            target.close()

    def test_import_invalid_file_raises(self):
        bad_path = os.path.join(self.tmpdir, "bad.json")
        with open(bad_path, "w", encoding="utf-8") as f:
            f.write('{"hello": "world"}')
        with self.assertRaises(ValueError):
            self.db.import_data_json(bad_path)

        with open(bad_path, "w", encoding="utf-8") as f:
            f.write("не json")
        with self.assertRaises(ValueError):
            self.db.import_data_json(bad_path)

    def test_import_creates_backup_before_replace(self):
        self.assertTrue(self.db.export_data_json(self.export_path))
        result = self.db.import_data_json(self.export_path)  # replace=True
        self.assertIsNotNone(result["backup"])
        self.assertTrue(os.path.exists(result["backup"]))
        # Резервная копия лежит в data/backups рядом с БД
        self.assertEqual(os.path.dirname(result["backup"]),
                         os.path.join(os.path.dirname(self.db_path), "backups"))

    def test_merge_import_keeps_existing_games(self):
        self.assertTrue(self.db.export_data_json(self.export_path))
        target = Database(":memory:")
        try:
            target.add_game("keep.exe", "Keep")
            result = target.import_data_json(self.export_path, replace=False, auto_backup=False)
            self.assertEqual(result["games"], 1)  # добавлена только новая игра
            self.assertIsNotNone(target.get_game_by_exe_name("keep.exe"))
            self.assertIsNotNone(target.get_game_by_exe_name("game.exe"))
        finally:
            target.close()


class TestWeeklySummarySettings(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.settings = AppSettings(self.db)

    def tearDown(self):
        self.db.close()

    def test_defaults_and_persistence(self):
        self.assertTrue(self.settings.weekly_summary_enabled)
        self.assertIsNone(self.settings.last_weekly_summary_date)

        self.settings.weekly_summary_enabled = False
        self.settings.last_weekly_summary_date = "2026-10-20"
        self.settings.invalidate_cache()

        self.assertFalse(self.settings.weekly_summary_enabled)
        self.assertEqual(self.settings.last_weekly_summary_date, "2026-10-20")

    def test_clearing_last_summary_date(self):
        self.settings.last_weekly_summary_date = "2026-10-20"
        self.settings.last_weekly_summary_date = None
        self.settings.invalidate_cache()
        self.assertIsNone(self.settings.last_weekly_summary_date)


if __name__ == '__main__':
    unittest.main()
