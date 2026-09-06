import unittest
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
