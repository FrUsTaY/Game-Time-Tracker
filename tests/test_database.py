import unittest
from database import Database

class TestDatabase(unittest.TestCase):
    """Тесты для класса Database"""

    def setUp(self):
        """Создает временную базу данных в памяти для каждого теста"""
        self.db = Database(":memory:")

        # Добавляем тестовую игру для связывания с сессиями
        self.game_id = self.db.add_game("test_game.exe", "Test Game", "C:\\test\\test_game.exe")

    def tearDown(self):
        """Закрывает соединение"""
        self.db.close()

    def test_get_active_sessions(self):
        """
        Тестирует метод get_active_sessions:
        1. Проверяет, что изначально список активных сессий пуст.
        2. Запускает сессию и проверяет, что она появилась в активных.
        3. Завершает сессию и проверяет, что список снова пуст.
        """
        # 1. Проверяем, что активных сессий нет
        active_sessions = self.db.get_active_sessions()
        self.assertEqual(len(active_sessions), 0)

        # 2. Начинаем сессию
        session_id = self.db.start_session(self.game_id)

        # Проверяем, что появилась одна активная сессия
        active_sessions = self.db.get_active_sessions()
        self.assertEqual(len(active_sessions), 1)
        self.assertEqual(active_sessions[0]['id'], session_id)
        self.assertEqual(active_sessions[0]['game_id'], self.game_id)
        self.assertIsNone(active_sessions[0]['ended_at'])

        # 3. Завершаем сессию
        duration = 60
        self.db.end_session(session_id, duration)

        # Проверяем, что активных сессий снова нет
        active_sessions = self.db.get_active_sessions()
        self.assertEqual(len(active_sessions), 0)

if __name__ == '__main__':
    unittest.main()
import os
import sys
import tempfile
import shutil
import sqlite3
from datetime import date, datetime, timedelta

# Добавляем родительскую директорию в sys.path для импорта database
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import Database


class TestDatabaseGetGameByExeName(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.game_id = self.db.add_game(
            exe_name="testgame.exe",
            display_name="Test Game",
            exe_path="C:\\Games\\TestGame\\testgame.exe"
        )

    def tearDown(self):
        self.db.close()

    def test_get_game_by_exe_name_exact_match(self):
        """Проверка успешного поиска игры по точному совпадению имени файла."""
        game = self.db.get_game_by_exe_name("testgame.exe")
        self.assertIsNotNone(game)
        self.assertEqual(game['exe_name'], "testgame.exe")
        self.assertEqual(game['display_name'], "Test Game")

    def test_get_game_by_exe_name_case_insensitive(self):
        """Проверка поиска игры без учета регистра."""
        game = self.db.get_game_by_exe_name("TESTGAME.EXE")
        self.assertIsNotNone(game)
        self.assertEqual(game['exe_name'], "testgame.exe")
        self.assertEqual(game['display_name'], "Test Game")

        game_camel_case = self.db.get_game_by_exe_name("TestGame.Exe")
        self.assertIsNotNone(game_camel_case)
        self.assertEqual(game_camel_case['exe_name'], "testgame.exe")

    def test_get_game_by_exe_name_not_found(self):
        """Проверка возврата None для несуществующей игры."""
        game = self.db.get_game_by_exe_name("nonexistent.exe")
        self.assertIsNone(game)



class TestDatabaseGeneral(unittest.TestCase):
    """Общие тесты для класса Database"""

    def setUp(self):
        """Создает in-memory базу данных перед каждым тестом"""
        self.db = Database(":memory:")

    def tearDown(self):
        """Закрывает соединение с базой данных после каждого теста"""
        self.db.close()

    def test_initial_settings(self):
        """Тестирует, что база данных инициализируется с настройками по умолчанию"""
        self.assertEqual(self.db.get_setting("autostart"), "false")
        self.assertEqual(self.db.get_setting("notify_new_game"), "true")

    def test_add_and_get_game(self):
        """Тестирует добавление и получение игры"""
        game_id = self.db.add_game("testgame.exe", "Test Game", "C:/Games/testgame.exe")
        self.assertIsNotNone(game_id)

        game = self.db.get_game_by_id(game_id)
        self.assertIsNotNone(game)
        self.assertEqual(game["exe_name"], "testgame.exe")
        self.assertEqual(game["display_name"], "Test Game")
        self.assertEqual(game["exe_path"], "C:/Games/testgame.exe")

    def test_get_game_by_exe_name(self):
        """Тестирует получение игры по имени исполняемого файла"""
        self.db.add_game("tesTGame.exe", "Test Game")

        game = self.db.get_game_by_exe_name("testgame.exe")
        self.assertIsNotNone(game)
        self.assertEqual(game["exe_name"], "testgame.exe")

        game2 = self.db.get_game_by_exe_name("TESTGAME.EXE")
        self.assertIsNotNone(game2)

    def test_get_all_games(self):
        """Тестирует получение списка всех активных игр"""
        self.db.add_game("game1.exe", "Game 1")
        self.db.add_game("game2.exe", "Game 2")

        games = self.db.get_all_games()
        self.assertEqual(len(games), 2)

        self.db.archive_game(games[0]["id"])

        active_games = self.db.get_all_games(archived=False)
        self.assertEqual(len(active_games), 1)

        archived_games = self.db.get_all_games(archived=True)
        self.assertEqual(len(archived_games), 1)

    def test_update_game_time_and_launch_count(self):
        """Тестирует обновление времени в игре и количество запусков"""
        game_id = self.db.add_game("game.exe", "Game")

        self.db.update_game_time(game_id, 3600)
        self.db.increment_launch_count(game_id)
        self.db.increment_launch_count(game_id)

        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game["total_seconds"], 3600)
        self.assertEqual(game["launch_count"], 2)

    def test_archive_and_unarchive_game(self):
        """Тестирует архивацию и разархивацию игры"""
        game_id = self.db.add_game("game.exe", "Game")

        self.db.archive_game(game_id)
        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game["is_archived"], 1)

        self.db.unarchive_game(game_id)
        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game["is_archived"], 0)

    def test_delete_game(self):
        """Тестирует удаление игры и связанных сессий"""
        game_id = self.db.add_game("game.exe", "Game")
        session_id = self.db.start_session(game_id)

        self.db.delete_game(game_id)

        game = self.db.get_game_by_id(game_id)
        self.assertIsNone(game)

        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        self.assertIsNone(cursor.fetchone())

    def test_rename_game(self):
        """Тестирует переименование игры"""
        game_id = self.db.add_game("game.exe", "Game")
        self.db.rename_game(game_id, "New Game Name")

        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game["display_name"], "New Game Name")

    def test_update_icon_path(self):
        """Тестирует обновление пути к иконке игры"""
        game_id = self.db.add_game("game.exe", "Game")
        self.db.update_icon_path(game_id, "icons/game.ico")

        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game["icon_path"], "icons/game.ico")

    def test_sessions(self):
        """Тестирует запуск, завершение и получение сессий"""
        game_id = self.db.add_game("game.exe", "Game")

        session_id = self.db.start_session(game_id)

        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game["launch_count"], 1)

        active_sessions = self.db.get_active_sessions()
        self.assertEqual(len(active_sessions), 1)
        self.assertEqual(active_sessions[0]["id"], session_id)

        self.db.end_session(session_id, 3600)

        active_sessions_after = self.db.get_active_sessions()
        self.assertEqual(len(active_sessions_after), 0)

        today = date.today()
        sessions = self.db.get_sessions_by_date(today)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["duration_seconds"], 3600)
        self.assertEqual(sessions[0]["game_id"], game_id)

    def test_settings(self):
        """Тестирует установку и получение настроек"""
        self.assertEqual(self.db.get_setting("autostart"), "false")

        self.db.set_setting("autostart", "true")
        self.assertEqual(self.db.get_setting("autostart"), "true")

        self.db.set_setting("new_setting", "123")
        self.assertEqual(self.db.get_setting("new_setting"), "123")

        self.assertEqual(self.db.get_setting("non_existent", "default"), "default")

    def test_export_sessions_csv(self):
        """Тестирует экспорт сессий в CSV-файл"""
        game_id = self.db.add_game("game.exe", "Game")
        session_id = self.db.start_session(game_id)
        self.db.end_session(session_id, 1800)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp_path = tmp.name

        try:
            result = self.db.export_sessions_csv(tmp_path)
            self.assertTrue(result)

            with open(tmp_path, "r", encoding="utf-8-sig") as f:
                content = f.read()
                self.assertIn("ID,Игра,Начало,Конец,Длительность (сек)", content)
                self.assertIn("Game", content)
                self.assertIn("1800", content)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)



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


class TestDatabaseUnarchiveGame(unittest.TestCase):
    def setUp(self):
        """Создаем временную директорию и инициализируем базу данных для тестов"""
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_gametracker.db")
        self.db = Database(self.db_path)

    def tearDown(self):
        """Закрываем базу данных и удаляем временные файлы после теста"""
        self.db.close()
        shutil.rmtree(self.test_dir)

    def test_unarchive_game(self):
        """Тест проверяет корректность работы метода unarchive_game"""
        game_id = self.db.add_game(
            exe_name="testgame.exe",
            display_name="Test Game",
            exe_path="C:\\games\\testgame.exe"
        )

        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game['is_archived'], 0)
        self.assertIsNone(game['archived_at'])

        self.db.archive_game(game_id)

        archived_game = self.db.get_game_by_id(game_id)
        self.assertEqual(archived_game['is_archived'], 1)
        self.assertIsNotNone(archived_game['archived_at'])

        self.db.unarchive_game(game_id)

        unarchived_game = self.db.get_game_by_id(game_id)
        self.assertEqual(unarchived_game['is_archived'], 0)
        self.assertIsNone(unarchived_game['archived_at'])


class TestDatabaseGetAllGames(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        self.db = Database(self.db_path)

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_get_all_games_empty(self):
        """Тест пустого списка игр"""
        games = self.db.get_all_games()
        self.assertEqual(games, [])
        games_archived = self.db.get_all_games(archived=True)
        self.assertEqual(games_archived, [])

    def test_get_all_games_active_and_archived(self):
        """Тест получения активных и архивных игр"""
        game1_id = self.db.add_game("game1.exe", "Game 1")
        game2_id = self.db.add_game("game2.exe", "Game 2")
        game3_id = self.db.add_game("game3.exe", "Game 3")

        self.db.archive_game(game2_id)

        active_games = self.db.get_all_games(archived=False)
        self.assertEqual(len(active_games), 2)
        active_exe_names = {game["exe_name"] for game in active_games}
        self.assertEqual(active_exe_names, {"game1.exe", "game3.exe"})

        archived_games = self.db.get_all_games(archived=True)
        self.assertEqual(len(archived_games), 1)
        self.assertEqual(archived_games[0]["exe_name"], "game2.exe")
        self.assertEqual(archived_games[0]["is_archived"], 1)

    def test_get_all_games_structure(self):
        """Тест структуры возвращаемого словаря"""
        game_id = self.db.add_game("test_game.exe", "Test Game", "C:\\test_game.exe")
        games = self.db.get_all_games()
        self.assertEqual(len(games), 1)

        game = games[0]
        self.assertEqual(game["id"], game_id)
        self.assertEqual(game["exe_name"], "test_game.exe")
        self.assertEqual(game["display_name"], "Test Game")
        self.assertEqual(game["exe_path"], "C:\\test_game.exe")
        self.assertEqual(game["is_archived"], 0)
        self.assertIn("added_at", game)
        self.assertIn("total_seconds", game)
        self.assertEqual(game["total_seconds"], 0)


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


class TestDatabaseStatsMethods(unittest.TestCase):
    """Тесты для статистических методов класса Database"""

    def setUp(self):
        self.db = Database(":memory:")
        self.game1_id = self.db.add_game("game1.exe", "Game One")
        self.game2_id = self.db.add_game("game2.exe", "Game Two")

    def tearDown(self):
        self.db.close()

    def test_empty_stats(self):
        """Проверка статистических методов при отсутствии сессий"""
        self.assertIsNone(self.db.get_longest_session())
        self.assertIsNone(self.db.get_best_day())
        self.assertEqual(self.db.get_games_session_stats(), [])

    def test_get_longest_session(self):
        """Проверка возврата самой длинной сессии"""
        s1 = self.db.start_session(self.game1_id)
        self.db.end_session(s1, 1200)

        s2 = self.db.start_session(self.game2_id)
        self.db.end_session(s2, 3600)

        longest = self.db.get_longest_session()
        self.assertIsNotNone(longest)
        self.assertEqual(longest["duration_seconds"], 3600)
        self.assertEqual(longest["display_name"], "Game Two")

    def test_get_best_day(self):
        """Проверка возврата самого активного дня"""
        s1 = self.db.start_session(self.game1_id)
        self.db.end_session(s1, 1000)

        s2 = self.db.start_session(self.game2_id)
        self.db.end_session(s2, 2000)

        best_day = self.db.get_best_day()
        self.assertIsNotNone(best_day)
        self.assertEqual(best_day["total"], 3000)
        self.assertIsNotNone(best_day["day"])

    def test_get_games_session_stats(self):
        """Проверка возврата статистики сессий по играм"""
        s1 = self.db.start_session(self.game1_id)
        self.db.end_session(s1, 1000)
        s2 = self.db.start_session(self.game1_id)
        self.db.end_session(s2, 2000)

        s3 = self.db.start_session(self.game2_id)
        self.db.end_session(s3, 600)

        stats = self.db.get_games_session_stats()
        self.assertEqual(len(stats), 2)
        # Отсортировано по avg_sec DESC: game1 (1500), game2 (600)
        self.assertEqual(stats[0]["display_name"], "Game One")
        self.assertEqual(stats[0]["session_count"], 2)
        self.assertAlmostEqual(stats[0]["avg_sec"], 1500.0)

        self.assertEqual(stats[1]["display_name"], "Game Two")
        self.assertEqual(stats[1]["session_count"], 1)
        self.assertAlmostEqual(stats[1]["avg_sec"], 600.0)


class TestDatabaseThreadSafety(unittest.TestCase):
    """Тесты на потокобезопасность класса Database"""

    def setUp(self):
        self.db = Database(":memory:")
        self.game_id = self.db.add_game("test_thread.exe", "Thread Test Game")

    def tearDown(self):
        self.db.close()

    def test_concurrent_read_write(self):
        """Проверка одновременного чтения и записи из нескольких потоков"""
        import threading

        errors = []
        iterations = 50

        def writer_task():
            try:
                for i in range(iterations):
                    sid = self.db.start_session(self.game_id)
                    self.db.update_game_time(self.game_id, 10)
                    self.db.end_session(sid, 10)
                    self.db.set_setting(f"key_{threading.get_ident()}", str(i))
            except Exception as e:
                errors.append(e)

        def reader_task():
            try:
                for _ in range(iterations):
                    self.db.get_all_games()
                    self.db.get_active_sessions()
                    self.db.get_longest_session()
                    self.db.get_best_day()
                    self.db.get_games_session_stats()
                    self.db.get_setting("autostart")
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(4):
            threads.append(threading.Thread(target=writer_task))
            threads.append(threading.Thread(target=reader_task))

        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=10.0)
            self.assertFalse(t.is_alive(), "Поток не завершился вовремя (возможен дедлок)")

        self.assertEqual(len(errors), 0, f"Ошибки в потоках: {errors}")

    def test_update_session_duration(self):
        """Проверка промежуточного обновления длительности сессии (in-flight update)"""
        sid = self.db.start_session(self.game_id)
        # Проверяем, что сессия активна и duration_seconds = 0
        active = self.db.get_active_sessions()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]['duration_seconds'], 0)
        self.assertIsNone(active[0]['ended_at'])

        # Обновляем промежуточную длительность
        self.db.update_session_duration(sid, 120)
        active = self.db.get_active_sessions()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]['duration_seconds'], 120)
        self.assertIsNone(active[0]['ended_at'])

    def test_cleanup_zombie_sessions_zero_duration(self):
        """Проверка очистки зомби-сессий с нулевой длительностью"""
        # Создаем активную сессию без завершения
        sid = self.db.start_session(self.game_id)
        active_before = self.db.get_active_sessions()
        self.assertEqual(len(active_before), 1)

        # Вызываем очистку зомби-сессий
        cleaned = self.db.cleanup_zombie_sessions()
        self.assertEqual(cleaned, 1)

        # Проверяем, что активных сессий не осталось
        active_after = self.db.get_active_sessions()
        self.assertEqual(len(active_after), 0)

        # Проверяем запись в таблице sessions
        with self.db.lock:
            cur = self.db.conn.cursor()
            cur.execute("SELECT started_at, ended_at, duration_seconds FROM sessions WHERE id = ?", (sid,))
            row = cur.fetchone()
            self.assertEqual(row['started_at'], row['ended_at'])
            self.assertEqual(row['duration_seconds'], 0)

    def test_cleanup_zombie_sessions_flushed_duration(self):
        """Проверка очистки зомби-сессий с частично сохранённой длительностью (>0)"""
        # Создаем сессию и имитируем периодический сброс 180 секунд
        sid = self.db.start_session(self.game_id)
        self.db.update_session_duration(sid, 180)

        cleaned = self.db.cleanup_zombie_sessions()
        self.assertEqual(cleaned, 1)

        with self.db.lock:
            cur = self.db.conn.cursor()
            cur.execute("SELECT started_at, ended_at, duration_seconds FROM sessions WHERE id = ?", (sid,))
            row = cur.fetchone()
            # Длительность должна сохраниться
            self.assertEqual(row['duration_seconds'], 180)
            self.assertIsNotNone(row['ended_at'])
            self.assertNotEqual(row['started_at'], row['ended_at'])

    def test_cleanup_zombie_sessions_on_init(self):
        """Проверка автоматической очистки зомби-сессий при инициализации Database"""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "zombie_test.db")
        try:
            # 1-й запуск приложения: сессия создана, но приложение аварийно закрыто
            db1 = Database(db_path)
            gid = db1.add_game("zombie.exe", "Zombie Game")
            sid = db1.start_session(gid)
            db1.update_session_duration(sid, 60)
            db1.close()

            # 2-й запуск приложения: при создании Database зомби-сессии должны очиститься
            db2 = Database(db_path)
            active = db2.get_active_sessions()
            self.assertEqual(len(active), 0)

            with db2.lock:
                cur = db2.conn.cursor()
                cur.execute("SELECT ended_at, duration_seconds FROM sessions WHERE id = ?", (sid,))
                row = cur.fetchone()
                self.assertIsNotNone(row['ended_at'])
                self.assertEqual(row['duration_seconds'], 60)
            db2.close()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_backup_database(self):
        """Проверка Online Backup API базы данных"""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "original.db")
        backup_path = os.path.join(temp_dir, "backup_sub", "backup.db")
        try:
            db = Database(db_path)
            gid = db.add_game("game_backup.exe", "Game for Backup")
            db.update_game_time(gid, 500)
            db.set_setting("backup_test_key", "backup_value")

            # Выполняем бэкап
            db.backup_database(backup_path)

            self.assertTrue(os.path.exists(backup_path))

            # Проверяем целостность и данные файла бэкапа
            backup_db = Database(backup_path)
            games = backup_db.get_all_games()
            self.assertEqual(len(games), 1)
            self.assertEqual(games[0]['display_name'], "Game for Backup")
            self.assertEqual(games[0]['total_seconds'], 500)
            self.assertEqual(backup_db.get_setting("backup_test_key"), "backup_value")

            backup_db.close()
            db.close()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_sessions_indexes(self):
        """Проверка наличия индексов idx_sessions_started_at и idx_sessions_game_id и их использования в EXPLAIN QUERY PLAN"""
        with self.db.lock:
            cur = self.db.conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'sessions'")
            indexes = [row[0] for row in cur.fetchall()]
            self.assertIn("idx_sessions_started_at", indexes)
            self.assertIn("idx_sessions_game_id", indexes)

            # Проверяем query plan для выборки по started_at
            cur.execute("EXPLAIN QUERY PLAN SELECT * FROM sessions WHERE started_at BETWEEN ? AND ?", ("2026-01-01", "2026-01-02"))
            plan_started_at = " ".join(row[3] for row in cur.fetchall())
            self.assertIn("idx_sessions_started_at", plan_started_at)

            # Проверяем query plan для выборки по game_id
            cur.execute("EXPLAIN QUERY PLAN SELECT * FROM sessions WHERE game_id = ?", (1,))
            plan_game_id = " ".join(row[3] for row in cur.fetchall())
            self.assertIn("idx_sessions_game_id", plan_game_id)


if __name__ == '__main__':
    unittest.main()

