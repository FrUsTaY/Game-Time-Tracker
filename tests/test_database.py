import unittest
import os
import tempfile
from database import Database

class TestDatabaseRenameGame(unittest.TestCase):
    def setUp(self):
        # Используем временный файл для БД, чтобы не трогать реальную БД
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.db = Database(db_path=self.db_path)

    def tearDown(self):
        self.db.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_rename_game_success(self):
        """Тест успешного переименования существующей игры"""
        # Добавляем игру
        game_id = self.db.add_game(exe_name="testgame.exe", display_name="Old Name")

        # Проверяем, что игра добавилась с правильным именем
        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game["display_name"], "Old Name")

        # Переименовываем игру
        self.db.rename_game(game_id, "New Awesome Name")

        # Проверяем, что имя изменилось
        updated_game = self.db.get_game_by_id(game_id)
        self.assertEqual(updated_game["display_name"], "New Awesome Name")

    def test_rename_nonexistent_game(self):
        """Тест переименования несуществующей игры (не должно падать)"""
        # В SQLite UPDATE для несуществующей записи не вызывает ошибку,
        # но мы можем убедиться, что исключение не выбрасывается.
        try:
            self.db.rename_game(999, "Some Name")
        except Exception as e:
            self.fail(f"rename_game raised an exception for non-existent game: {e}")

if __name__ == '__main__':
    unittest.main()
