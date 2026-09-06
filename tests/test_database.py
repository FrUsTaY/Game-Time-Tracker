import unittest
import os
import sys

# Добавляем родительскую директорию в sys.path, чтобы можно было импортировать database
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import Database

class TestDatabase(unittest.TestCase):
    def setUp(self):
        """Создаем in-memory базу данных перед каждым тестом"""
        self.db = Database(":memory:")

    def tearDown(self):
        """Закрываем соединение после каждого теста"""
        self.db.close()

    def test_archive_game(self):
        """Тест архивации игры и получения списка архивированных игр"""
        # 1. Добавляем игру
        game_id = self.db.add_game("test_game.exe", "Test Game", "C:\\test\\test_game.exe")

        # 2. Проверяем, что она появилась в активных играх
        active_games = self.db.get_all_games(archived=False)
        self.assertEqual(len(active_games), 1)
        self.assertEqual(active_games[0]['id'], game_id)
        self.assertEqual(active_games[0]['is_archived'], 0)
        self.assertIsNone(active_games[0]['archived_at'])

        # 3. Проверяем, что архив пуст
        archived_games = self.db.get_all_games(archived=True)
        self.assertEqual(len(archived_games), 0)

        # 4. Архивируем игру
        self.db.archive_game(game_id)

        # 5. Проверяем, что игра пропала из активных
        active_games_after = self.db.get_all_games(archived=False)
        self.assertEqual(len(active_games_after), 0)

        # 6. Проверяем, что игра появилась в архиве
        archived_games_after = self.db.get_all_games(archived=True)
        self.assertEqual(len(archived_games_after), 1)

        archived_game = archived_games_after[0]
        self.assertEqual(archived_game['id'], game_id)
        self.assertEqual(archived_game['is_archived'], 1)
        self.assertIsNotNone(archived_game['archived_at'])

        # 7. Проверяем разархивацию (unarchive_game), так как это логически связанный метод
        self.db.unarchive_game(game_id)

        # Проверяем возвращение игры в активные
        active_games_final = self.db.get_all_games(archived=False)
        self.assertEqual(len(active_games_final), 1)
        self.assertEqual(active_games_final[0]['id'], game_id)
        self.assertEqual(active_games_final[0]['is_archived'], 0)
        self.assertIsNone(active_games_final[0]['archived_at'])

        # Проверяем, что архив снова пуст
        archived_games_final = self.db.get_all_games(archived=True)
        self.assertEqual(len(archived_games_final), 0)

if __name__ == '__main__':
    unittest.main()
