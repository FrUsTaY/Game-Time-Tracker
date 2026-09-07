import unittest
import os
import tempfile
from datetime import date
from database import Database

class TestDatabase(unittest.TestCase):
    """Тесты для класса Database"""

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

        # Поиск не зависит от регистра
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

        # Проверяем архивацию
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

        # Проверяем, что игра удалена
        game = self.db.get_game_by_id(game_id)
        self.assertIsNone(game)

        # Проверяем каскадное удаление (сессии)
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

        # Запуск сессии
        session_id = self.db.start_session(game_id)

        # Проверяем, что количество запусков увеличилось
        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game["launch_count"], 1)

        active_sessions = self.db.get_active_sessions()
        self.assertEqual(len(active_sessions), 1)
        self.assertEqual(active_sessions[0]["id"], session_id)

        # Завершение сессии
        self.db.end_session(session_id, 3600)

        active_sessions_after = self.db.get_active_sessions()
        self.assertEqual(len(active_sessions_after), 0)

        # Проверяем получение сессий за сегодня
        today = date.today()
        sessions = self.db.get_sessions_by_date(today)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["duration_seconds"], 3600)
        self.assertEqual(sessions[0]["game_id"], game_id)

    def test_settings(self):
        """Тестирует установку и получение настроек"""
        # Проверяем настройку по умолчанию
        self.assertEqual(self.db.get_setting("autostart"), "false")

        # Устанавливаем новое значение
        self.db.set_setting("autostart", "true")
        self.assertEqual(self.db.get_setting("autostart"), "true")

        # Добавляем новую настройку
        self.db.set_setting("new_setting", "123")
        self.assertEqual(self.db.get_setting("new_setting"), "123")

        # Получение несуществующей настройки
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

            # Проверяем содержимое файла
            with open(tmp_path, "r", encoding="utf-8-sig") as f:
                content = f.read()
                self.assertIn("ID,Игра,Начало,Конец,Длительность (сек)", content)
                self.assertIn("Game", content)
                self.assertIn("1800", content)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

if __name__ == "__main__":
import sqlite3
import os
from database import Database
from datetime import datetime

class TestDatabaseStartSession(unittest.TestCase):
    def setUp(self):
        # Используем in-memory базу данных для изоляции и скорости
        self.db = Database(db_path=":memory:")
        # Явно включаем поддержку foreign keys, так как по умолчанию она может быть выключена в SQLite
        self.db.conn.execute("PRAGMA foreign_keys = ON")

    def tearDown(self):
        self.db.close()

    def test_start_session_success(self):
        # Подготовка: добавляем игру, так как foreign key требует существования игры
        game_id = self.db.add_game("test_game.exe", "Test Game")

        # Получаем начальный счетчик запусков
        initial_game = self.db.get_game_by_id(game_id)
        self.assertEqual(initial_game["launch_count"], 0)

        # Выполнение: запускаем сессию
        session_id = self.db.start_session(game_id)

        # Проверка: ID сессии должен быть положительным числом
        self.assertIsNotNone(session_id)
        self.assertGreater(session_id, 0)

        # Проверка: запись сессии добавлена в таблицу
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        session = cursor.fetchone()

        self.assertIsNotNone(session, "Запись сессии не найдена в базе данных")
        self.assertEqual(session["game_id"], game_id)
        self.assertIsNotNone(session["started_at"])
        self.assertIsNone(session["ended_at"])
        self.assertEqual(session["duration_seconds"], 0)

        # Проверка: счетчик запусков увеличен
        updated_game = self.db.get_game_by_id(game_id)
        self.assertEqual(updated_game["launch_count"], 1, "Счетчик запусков не был увеличен")

    def test_start_session_nonexistent_game(self):
        # Пробуем запустить сессию для игры, которой нет
        # Если foreign_keys включены, будет ошибка целостности
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.start_session(9999)
import tempfile
import os
from database import Database

class TestDatabase(unittest.TestCase):
    def setUp(self):
        """Создает временную базу данных для тестов."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        self.db = Database(self.db_path)

        # Включаем поддержку внешних ключей в SQLite для тестов каскадного удаления
        cursor = self.db.conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        self.db.conn.commit()

    def tearDown(self):
        """Закрывает соединение с БД и удаляет временную папку."""
        self.db.close()
        self.temp_dir.cleanup()

    def test_delete_game(self):
        """Проверяет удаление игры из базы данных."""
        # 1. Добавляем игру
        game_id = self.db.add_game("test_game.exe", "Test Game", "C:\\games\\test_game.exe")

        # Убеждаемся, что игра добавилась
        game = self.db.get_game_by_id(game_id)
        self.assertIsNotNone(game)
        self.assertEqual(game["exe_name"], "test_game.exe")

        # 2. Удаляем игру
        self.db.delete_game(game_id)

        # 3. Проверяем, что игры больше нет в базе
        deleted_game = self.db.get_game_by_id(game_id)
        self.assertIsNone(deleted_game)

    def test_delete_game_cascade(self):
        """Проверяет каскадное удаление связанных сессий при удалении игры."""
        # 1. Добавляем игру
        game_id = self.db.add_game("test_cascade.exe", "Test Cascade Game")

        # 2. Добавляем сессию для этой игры
        session_id = self.db.start_session(game_id)

        # Убеждаемся, что сессия добавилась
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        session = cursor.fetchone()
        self.assertIsNotNone(session)

        # 3. Удаляем игру
        self.db.delete_game(game_id)

        # 4. Проверяем, что связанная сессия тоже удалилась
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        deleted_session = cursor.fetchone()
        self.assertIsNone(deleted_session)

if __name__ == '__main__':
    unittest.main()
