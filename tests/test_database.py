import unittest
import sqlite3
import os
import sys

# Добавляем родительскую директорию в sys.path, чтобы можно было импортировать database
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import Database

class TestDatabaseGetGameByExeName(unittest.TestCase):
    def setUp(self):
        # Используем in-memory базу данных для тестов
        self.db = Database(":memory:")

        # Добавляем тестовую игру
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
        # В БД сохраняется testgame.exe (по логке add_game, которая делает .lower())
        # Проверяем поиск с другим регистром
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

if __name__ == '__main__':
    unittest.main()
