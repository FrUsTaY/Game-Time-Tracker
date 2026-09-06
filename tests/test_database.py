import unittest
import tempfile
import os
import sqlite3
from database import Database

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
        # Добавляем игры
        game1_id = self.db.add_game("game1.exe", "Game 1")
        game2_id = self.db.add_game("game2.exe", "Game 2")
        game3_id = self.db.add_game("game3.exe", "Game 3")

        # Отправляем одну в архив
        self.db.archive_game(game2_id)

        # Проверяем активные игры
        active_games = self.db.get_all_games(archived=False)
        self.assertEqual(len(active_games), 2)
        active_exe_names = {game["exe_name"] for game in active_games}
        self.assertEqual(active_exe_names, {"game1.exe", "game3.exe"})

        # Проверяем архивные игры
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

if __name__ == '__main__':
    unittest.main()
