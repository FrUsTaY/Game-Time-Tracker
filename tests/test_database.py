import unittest
import tempfile
import os
import sqlite3
from datetime import datetime

from database import Database


class TestDatabaseEndSession(unittest.TestCase):
    def setUp(self):
        # Создаем временную директорию для базы данных
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        self.db = Database(self.db_path)

        # Добавляем тестовую игру для использования в сессиях
        self.game_id = self.db.add_game("test_game.exe", "Test Game", "C:\\test_game.exe")

    def tearDown(self):
        # Закрываем соединение и удаляем временную директорию
        self.db.conn.close()
        self.temp_dir.cleanup()

    def test_end_session_success(self):
        """Тест успешного завершения существующей сессии."""
        # 1. Запускаем сессию
        session_id = self.db.start_session(self.game_id)

        # Убедимся, что сессия создалась и не имеет ended_at и duration_seconds = 0
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT ended_at, duration_seconds FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertIsNone(row['ended_at'])
        self.assertEqual(row['duration_seconds'], 0)

        # 2. Завершаем сессию
        duration = 3600 # 1 час
        self.db.end_session(session_id, duration)

        # 3. Проверяем, что сессия обновилась. Исходный код database.py имеет commit(), так что данные сохранятся.
        # Мы можем прочитать их через существующее соединение.
        cursor.execute("SELECT ended_at, duration_seconds FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()

        self.assertIsNotNone(row)
        self.assertIsNotNone(row['ended_at'])
        self.assertEqual(row['duration_seconds'], duration)

    def test_end_session_nonexistent(self):
        """Тест завершения несуществующей сессии."""
        nonexistent_session_id = 9999
        duration = 120

        # Метод не должен выбрасывать исключение при несуществующем ID
        self.db.end_session(nonexistent_session_id, duration)

        # Проверим, что в БД ничего не добавилось
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (nonexistent_session_id,))
        row = cursor.fetchone()
        self.assertIsNone(row)


if __name__ == '__main__':
    unittest.main()
