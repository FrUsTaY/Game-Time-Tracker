import unittest
import tempfile
import os
import sqlite3
from datetime import datetime

from database import Database


class TestDatabaseEndSession(unittest.TestCase):
    def setUp(self):
        # Создаем временную директорию для базы данных
import sqlite3
import os
from database import Database
from datetime import datetime

class TestDatabaseStartSession(unittest.TestCase):
    def setUp(self):
        # Используем in-memory базу данных для изоляции и скорости
        self.db = Database(db_path=":memory:")
        # Явно включаем поддержку foreign keys, так как по умолчанию она может быть выключена в SQLite
        self.db.conn.execute("PRAGMA foreign_keys = ON")

    def tearDown(self):
        self.db.close()

    def test_start_session_success(self):
        # Подготовка: добавляем игру, так как foreign key требует существования игры
        game_id = self.db.add_game("test_game.exe", "Test Game")

        # Получаем начальный счетчик запусков
        initial_game = self.db.get_game_by_id(game_id)
        self.assertEqual(initial_game["launch_count"], 0)

        # Выполнение: запускаем сессию
        session_id = self.db.start_session(game_id)

        # Проверка: ID сессии должен быть положительным числом
        self.assertIsNotNone(session_id)
        self.assertGreater(session_id, 0)

        # Проверка: запись сессии добавлена в таблицу
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        session = cursor.fetchone()

        self.assertIsNotNone(session, "Запись сессии не найдена в базе данных")
        self.assertEqual(session["game_id"], game_id)
        self.assertIsNotNone(session["started_at"])
        self.assertIsNone(session["ended_at"])
        self.assertEqual(session["duration_seconds"], 0)

        # Проверка: счетчик запусков увеличен
        updated_game = self.db.get_game_by_id(game_id)
        self.assertEqual(updated_game["launch_count"], 1, "Счетчик запусков не был увеличен")

    def test_start_session_nonexistent_game(self):
        # Пробуем запустить сессию для игры, которой нет
        # Если foreign_keys включены, будет ошибка целостности
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.start_session(9999)
import tempfile
import os
from database import Database

class TestDatabase(unittest.TestCase):
    def setUp(self):
        """Создает временную базу данных для тестов."""
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
