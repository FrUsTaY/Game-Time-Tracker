import unittest
import os
import tempfile
import shutil

from database import Database

class TestDatabase(unittest.TestCase):
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
        # 1. Добавляем новую игру в базу
        game_id = self.db.add_game(
            exe_name="testgame.exe",
            display_name="Test Game",
            exe_path="C:\\games\\testgame.exe"
        )

        # Убеждаемся, что по умолчанию игра не в архиве
        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game['is_archived'], 0)
        self.assertIsNone(game['archived_at'])

        # 2. Архивируем игру
        self.db.archive_game(game_id)

        # Проверяем, что игра успешно переведена в архив
        archived_game = self.db.get_game_by_id(game_id)
        self.assertEqual(archived_game['is_archived'], 1)
        self.assertIsNotNone(archived_game['archived_at'])

        # 3. Вызываем целевой метод: разархивируем игру
        self.db.unarchive_game(game_id)

        # 4. Проверяем, что игра снова активна и дата архивации сброшена
        unarchived_game = self.db.get_game_by_id(game_id)
        self.assertEqual(unarchived_game['is_archived'], 0)
        self.assertIsNone(unarchived_game['archived_at'])

if __name__ == '__main__':
    unittest.main()
