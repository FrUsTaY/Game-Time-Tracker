import unittest
import sqlite3
import os
import sys
import tempfile

# Добавляем родительскую директорию в sys.path, чтобы можно было импортировать модули из корня
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import Database

class TestDatabaseAddGame(unittest.TestCase):
    def setUp(self):
        # Используем временный файл для базы данных, чтобы изолировать тесты
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

        # Вызываем метод add_game
        game_id = self.db.add_game(exe_name, display_name, exe_path)

        # Проверяем, что ID вернулся (должно быть больше 0)
        self.assertIsNotNone(game_id)
        self.assertGreater(game_id, 0)

        # Получаем игру из БД по ID для проверки
        game = self.db.get_game_by_id(game_id)

        # Проверяем корректность сохраненных данных
        self.assertIsNotNone(game)
        self.assertEqual(game['exe_name'], exe_name.lower())
        self.assertEqual(game['display_name'], display_name)
        self.assertEqual(game['exe_path'], exe_path)

    def test_add_game_duplicate_exe(self):
        """Тест попытки добавления игры с уже существующим exe_name (проверка UNIQUE constraint)"""
        exe_name = "duplicate.exe"

        # Добавляем первую игру
        self.db.add_game(exe_name, "First Game")

        # Пытаемся добавить вторую игру с тем же exe_name и ожидаем IntegrityError
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.add_game(exe_name, "Second Game")

if __name__ == '__main__':
    unittest.main()
