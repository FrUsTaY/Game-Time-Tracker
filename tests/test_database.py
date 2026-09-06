import unittest
from database import Database

class TestDatabase(unittest.TestCase):
    """Тесты для класса Database"""

    def setUp(self):
        """Создает временную базу данных в памяти для каждого теста"""
        self.db = Database(":memory:")

        # Добавляем тестовую игру для связывания с сессиями
        self.game_id = self.db.add_game("test_game.exe", "Test Game", "C:\\test\\test_game.exe")

    def tearDown(self):
        """Закрывает соединение"""
        self.db.close()

    def test_get_active_sessions(self):
        """
        Тестирует метод get_active_sessions:
        1. Проверяет, что изначально список активных сессий пуст.
        2. Запускает сессию и проверяет, что она появилась в активных.
        3. Завершает сессию и проверяет, что список снова пуст.
        """
        # 1. Проверяем, что активных сессий нет
        active_sessions = self.db.get_active_sessions()
        self.assertEqual(len(active_sessions), 0)

        # 2. Начинаем сессию
        session_id = self.db.start_session(self.game_id)

        # Проверяем, что появилась одна активная сессия
        active_sessions = self.db.get_active_sessions()
        self.assertEqual(len(active_sessions), 1)
        self.assertEqual(active_sessions[0]['id'], session_id)
        self.assertEqual(active_sessions[0]['game_id'], self.game_id)
        self.assertIsNone(active_sessions[0]['ended_at'])

        # 3. Завершаем сессию
        duration = 60
        self.db.end_session(session_id, duration)

        # Проверяем, что активных сессий снова нет
        active_sessions = self.db.get_active_sessions()
        self.assertEqual(len(active_sessions), 0)

if __name__ == '__main__':
    unittest.main()