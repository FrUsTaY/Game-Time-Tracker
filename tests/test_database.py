import unittest
import os
import tempfile
from database import Database

class TestDatabase(unittest.TestCase):
    """Тесты для класса Database"""

    def setUp(self):
        """Настройка перед каждым тестом"""
        # Создаем временный файл для базы данных
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.db_fd)

        # Инициализируем базу данных
        self.db = Database(self.db_path)

    def tearDown(self):
        """Очистка после каждого теста"""
        self.db.close()
        # Удаляем временный файл
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_increment_launch_count(self):
        """Тест увеличения счетчика запусков игры"""
        # 1. Добавляем новую игру
        game_id = self.db.add_game("test_game.exe", "Test Game")

        # 2. Проверяем начальное значение (должно быть 0)
        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game['launch_count'], 0)

        # 3. Увеличиваем счетчик и проверяем
        self.db.increment_launch_count(game_id)
        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game['launch_count'], 1)

        # 4. Увеличиваем еще раз и проверяем
        self.db.increment_launch_count(game_id)
        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game['launch_count'], 2)

    def test_increment_launch_count_nonexistent_game(self):
        """Тест увеличения счетчика для несуществующей игры (не должно вызывать ошибку)"""
        # Метод не должен вызывать исключений
        try:
            self.db.increment_launch_count(999)
            success = True
        except Exception:
            success = False

        self.assertTrue(success)

if __name__ == '__main__':
    unittest.main()
