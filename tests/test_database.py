import unittest
import os
import tempfile
from datetime import datetime
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
        # Create a temporary file for the database to keep tests isolated
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.db = Database(self.db_path)

    def tearDown(self):
        self.db.close()
        os.close(self.db_fd)
        os.remove(self.db_path)

    def test_update_game_time_increases_total_seconds(self):
        game_id = self.db.add_game(exe_name="test_game.exe", display_name="Test Game")

        # Initial check
        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game['total_seconds'], 0)

        # Update time
        self.db.update_game_time(game_id, 3600)

        # Check if time was updated correctly
        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game['total_seconds'], 3600)

        # Add more time
        self.db.update_game_time(game_id, 1800)
        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game['total_seconds'], 5400)

    def test_update_game_time_updates_last_launched(self):
        game_id = self.db.add_game(exe_name="test_game2.exe", display_name="Test Game 2")

        # Update time
        self.db.update_game_time(game_id, 3600)

        # Check if last_launched was updated
        game = self.db.get_game_by_id(game_id)
        self.assertIsNotNone(game['last_launched'])

        try:
            datetime.fromisoformat(game['last_launched'])
        except ValueError:
            self.fail("last_launched should be a valid ISO format string")

    def test_update_game_time_non_existent_game(self):
        non_existent_id = 9999
        # Ensure it does not raise an exception
        try:
            self.db.update_game_time(non_existent_id, 3600)
        except Exception as e:
            self.fail(f"update_game_time raised an exception for non-existent game: {e}")
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
