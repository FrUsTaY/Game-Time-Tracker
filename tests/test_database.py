import unittest
import os
import sys
import tempfile
import sqlite3
from datetime import date, datetime, timedelta

# Добавляем родительскую директорию в sys.path для импорта database
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import Database


class TestDatabaseRenameGame(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.db = Database(db_path=self.db_path)

    def tearDown(self):
        self.db.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_rename_game_success(self):
        """Тест успешного переименования существующей игры"""
        game_id = self.db.add_game(exe_name="testgame.exe", display_name="Old Name")

        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game["display_name"], "Old Name")

        self.db.rename_game(game_id, "New Awesome Name")

        updated_game = self.db.get_game_by_id(game_id)
        self.assertEqual(updated_game["display_name"], "New Awesome Name")

    def test_rename_nonexistent_game(self):
        """Тест переименования несуществующей игры (не должно падать)"""
        try:
            self.db.rename_game(999, "Some Name")
        except Exception as e:
            self.fail(f"rename_game raised an exception for non-existent game: {e}")




class TestDatabaseAddGame(unittest.TestCase):
    def setUp(self):
        self.fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        self.db = Database(db_path=self.temp_db_path)

    def tearDown(self):
        self.db.close()
        os.close(self.fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_add_game_success(self):
        """Тест успешного добавления игры в базу данных"""
        exe_name = "test_game.exe"
        display_name = "Test Game"
        exe_path = "C:/games/test_game.exe"

        game_id = self.db.add_game(exe_name, display_name, exe_path)

        self.assertIsNotNone(game_id)
        self.assertGreater(game_id, 0)

        game = self.db.get_game_by_id(game_id)

        self.assertIsNotNone(game)
        self.assertEqual(game['exe_name'], exe_name.lower())
        self.assertEqual(game['display_name'], display_name)
        self.assertEqual(game['exe_path'], exe_path)

    def test_add_game_duplicate_exe(self):
        """Тест попытки добавления игры с уже существующим exe_name (проверка UNIQUE constraint)"""
        exe_name = "duplicate.exe"
        self.db.add_game(exe_name, "First Game")

        with self.assertRaises(sqlite3.IntegrityError):
            self.db.add_game(exe_name, "Second Game")



class TestDatabaseGetGameById(unittest.TestCase):
    def setUp(self):
        """Инициализируем in-memory базу данных перед каждым тестом"""
        self.db = Database(":memory:")

    def tearDown(self):
        """Закрываем соединение с базой данных после каждого теста"""
        self.db.close()

    def test_get_existing_game_by_id(self):
        """Тест успешного получения существующей игры по ID"""
        exe_name = "test_game.exe"
        display_name = "Test Game"
        exe_path = "C:\\Games\\test_game.exe"
        game_id = self.db.add_game(exe_name, display_name, exe_path)

        game = self.db.get_game_by_id(game_id)
        self.assertIsNotNone(game)
        self.assertEqual(game["id"], game_id)
        self.assertEqual(game["exe_name"], exe_name.lower())
        self.assertEqual(game["display_name"], display_name)
        self.assertEqual(game["exe_path"], exe_path)

    def test_get_non_existent_game_by_id(self):
        """Тест получения игры по несуществующему ID"""
        game = self.db.get_game_by_id(999)
        self.assertIsNone(game)

    def test_get_game_by_id_invalid_type(self):
        """Тест получения игры с передачей некорректного типа ID"""
        game = self.db.get_game_by_id("invalid")
        self.assertIsNone(game)

        game_id = self.db.add_game("test2.exe", "Test 2", None)
        game_str = self.db.get_game_by_id(str(game_id))
        self.assertIsNotNone(game_str)
        self.assertEqual(game_str["id"], game_id)



class TestDatabaseIncrementLaunchCount(unittest.TestCase):
    """Тесты для метода increment_launch_count"""

    def setUp(self):
        self.db = Database(db_path=":memory:")

    def tearDown(self):
        self.db.close()

    def test_increment_launch_count(self):
        """Тест увеличения счетчика запусков игры"""
        game_id = self.db.add_game("test_game.exe", "Test Game")
        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game['launch_count'], 0)

        self.db.increment_launch_count(game_id)
        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game['launch_count'], 1)

        self.db.increment_launch_count(game_id)
        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game['launch_count'], 2)

    def test_increment_launch_count_nonexistent_game(self):
        """Тест увеличения счетчика для несуществующей игры (не должно вызывать ошибку)"""
        try:
            self.db.increment_launch_count(999)
            success = True
        except Exception:
            success = False

        self.assertTrue(success)

class TestDatabaseSessionsRange(unittest.TestCase):
    def setUp(self):
        # Используем in-memory базу данных для изоляции тестов
        self.db = Database(db_path=":memory:")

        # Добавляем тестовую игру
        self.game_id = self.db.add_game("test_game.exe", "Test Game")

        # Подготавливаем тестовые данные - 5 сессий в разные дни
        self.target_start_date = date(2023, 10, 15)
        self.target_end_date = date(2023, 10, 20)

        cursor = self.db.conn.cursor()

        test_sessions = [
            (self.game_id, "2023-10-14T15:30:00"),
            (self.game_id, "2023-10-15T00:00:00"),
            (self.game_id, "2023-10-17T12:00:00"),
            (self.game_id, "2023-10-20T23:59:59.999999"),
            (self.game_id, "2023-10-21T00:00:00"),
        ]

        cursor.executemany('''
            INSERT INTO sessions (game_id, started_at)
            VALUES (?, ?)
        ''', test_sessions)

        self.db.conn.commit()

    def tearDown(self):
        self.db.close()

    def test_setup_created_sessions(self):
        """Проверка, что тестовые данные успешно созданы"""
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sessions")
        count = cursor.fetchone()[0]
        self.assertEqual(count, 5)

    def test_get_sessions_range_standard(self):
        """Проверка возврата сессий в пределах заданного диапазона (включая границы)"""
        sessions = self.db.get_sessions_range(self.target_start_date, self.target_end_date)
        self.assertEqual(len(sessions), 3)

        started_dates = [s["started_at"] for s in sessions]
        self.assertIn("2023-10-15T00:00:00", started_dates)
        self.assertIn("2023-10-17T12:00:00", started_dates)
        self.assertIn("2023-10-20T23:59:59.999999", started_dates)

        for s in sessions:
            self.assertEqual(s["display_name"], "Test Game")
            self.assertEqual(s["exe_name"], "test_game.exe")

    def test_get_sessions_range_empty(self):
        """Проверка, когда в заданном диапазоне нет сессий"""
        start_date = date(2022, 1, 1)
        end_date = date(2022, 12, 31)
        sessions = self.db.get_sessions_range(start_date, end_date)
        self.assertEqual(len(sessions), 0)

    def test_get_sessions_range_inverted_dates(self):
        """Проверка, когда начальная дата больше конечной (ожидается пустой результат)"""
        sessions = self.db.get_sessions_range(self.target_end_date, self.target_start_date)
        self.assertEqual(len(sessions), 0)

    def test_get_sessions_range_single_day(self):
        """Проверка диапазона, состоящего из одного дня"""
        target_date = date(2023, 10, 17)
        sessions = self.db.get_sessions_range(target_date, target_date)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["started_at"], "2023-10-17T12:00:00")


class TestDatabaseStartSession(unittest.TestCase):
    def setUp(self):
        self.db = Database(db_path=":memory:")
        self.db.conn.execute("PRAGMA foreign_keys = ON")

    def tearDown(self):
        self.db.close()

    def test_start_session_success(self):
        game_id = self.db.add_game("test_game.exe", "Test Game")
        initial_game = self.db.get_game_by_id(game_id)
        self.assertEqual(initial_game["launch_count"], 0)

        session_id = self.db.start_session(game_id)
        self.assertIsNotNone(session_id)
        self.assertGreater(session_id, 0)

        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        session = cursor.fetchone()

        self.assertIsNotNone(session, "Запись сессии не найдена в базе данных")
        self.assertEqual(session["game_id"], game_id)
        self.assertIsNotNone(session["started_at"])
        self.assertIsNone(session["ended_at"])
        self.assertEqual(session["duration_seconds"], 0)

        updated_game = self.db.get_game_by_id(game_id)
        self.assertEqual(updated_game["launch_count"], 1, "Счетчик запусков не был увеличен")

    def test_start_session_nonexistent_game(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.start_session(9999)


class TestDatabaseUpdateTime(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.db = Database(self.db_path)

    def tearDown(self):
        self.db.close()
        os.close(self.db_fd)
        os.remove(self.db_path)

    def test_update_game_time_increases_total_seconds(self):
        game_id = self.db.add_game(exe_name="test_game.exe", display_name="Test Game")
        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game['total_seconds'], 0)

        self.db.update_game_time(game_id, 3600)
        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game['total_seconds'], 3600)

        self.db.update_game_time(game_id, 1800)
        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game['total_seconds'], 5400)

    def test_update_game_time_updates_last_launched(self):
        game_id = self.db.add_game(exe_name="test_game2.exe", display_name="Test Game 2")
        self.db.update_game_time(game_id, 3600)
        game = self.db.get_game_by_id(game_id)
        self.assertIsNotNone(game['last_launched'])

        try:
            datetime.fromisoformat(game['last_launched'])
        except ValueError:
            self.fail("last_launched should be a valid ISO format string")

    def test_update_game_time_non_existent_game(self):
        non_existent_id = 9999
        try:
            self.db.update_game_time(non_existent_id, 3600)
        except Exception as e:
            self.fail(f"update_game_time raised an exception for non-existent game: {e}")


class TestDatabaseArchiveGame(unittest.TestCase):
    def setUp(self):
        """Создаем in-memory базу данных перед каждым тестом"""
        self.db = Database(":memory:")

    def tearDown(self):
        """Закрываем соединение после каждого теста"""
        self.db.close()

    def test_archive_game(self):
        """Тест архивации игры и получения списка архивированных игр"""
        game_id = self.db.add_game("test_game.exe", "Test Game", "C:\\test\\test_game.exe")

        active_games = self.db.get_all_games(archived=False)
        self.assertEqual(len(active_games), 1)
        self.assertEqual(active_games[0]['id'], game_id)
        self.assertEqual(active_games[0]['is_archived'], 0)
        self.assertIsNone(active_games[0]['archived_at'])

        archived_games = self.db.get_all_games(archived=True)
        self.assertEqual(len(archived_games), 0)

        self.db.archive_game(game_id)

        active_games_after = self.db.get_all_games(archived=False)
        self.assertEqual(len(active_games_after), 0)

        archived_games_after = self.db.get_all_games(archived=True)
        self.assertEqual(len(archived_games_after), 1)

        archived_game = archived_games_after[0]
        self.assertEqual(archived_game['id'], game_id)
        self.assertEqual(archived_game['is_archived'], 1)
        self.assertIsNotNone(archived_game['archived_at'])

        self.db.unarchive_game(game_id)

        active_games_final = self.db.get_all_games(archived=False)
        self.assertEqual(len(active_games_final), 1)
        self.assertEqual(active_games_final[0]['id'], game_id)
        self.assertEqual(active_games_final[0]['is_archived'], 0)
        self.assertIsNone(active_games_final[0]['archived_at'])

        archived_games_final = self.db.get_all_games(archived=True)
        self.assertEqual(len(archived_games_final), 0)


class TestDatabaseEndSessionAndDelete(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        self.db = Database(self.db_path)
        self.game_id = self.db.add_game("test_game.exe", "Test Game", "C:\\test_game.exe")
        cursor = self.db.conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        self.db.conn.commit()

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_end_session_success(self):
        session_id = self.db.start_session(self.game_id)
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT ended_at, duration_seconds FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertIsNone(row['ended_at'])
        self.assertEqual(row['duration_seconds'], 0)

        duration = 3600
        self.db.end_session(session_id, duration)

        cursor.execute("SELECT ended_at, duration_seconds FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertIsNotNone(row['ended_at'])
        self.assertEqual(row['duration_seconds'], duration)

    def test_end_session_nonexistent(self):
        nonexistent_session_id = 9999
        duration = 120
        self.db.end_session(nonexistent_session_id, duration)
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (nonexistent_session_id,))
        row = cursor.fetchone()
        self.assertIsNone(row)

    def test_delete_game(self):
        game_id = self.db.add_game("test_game2.exe", "Test Game 2", "C:\\games\\test_game2.exe")
        game = self.db.get_game_by_id(game_id)
        self.assertIsNotNone(game)
        self.assertEqual(game["exe_name"], "test_game2.exe")

        self.db.delete_game(game_id)
        deleted_game = self.db.get_game_by_id(game_id)
        self.assertIsNone(deleted_game)

    def test_delete_game_cascade(self):
        game_id = self.db.add_game("test_cascade.exe", "Test Cascade Game")
        session_id = self.db.start_session(game_id)

        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        session = cursor.fetchone()
        self.assertIsNotNone(session)

        self.db.delete_game(game_id)

        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        deleted_session = cursor.fetchone()
        self.assertIsNone(deleted_session)


if __name__ == '__main__':
    unittest.main()
