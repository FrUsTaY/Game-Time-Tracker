import unittest
import sqlite3
import sys
import os
from datetime import date, timedelta

# Добавляем родительскую директорию в sys.path для импорта database
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import Database

class TestDatabaseSessionsRange(unittest.TestCase):
    def setUp(self):
        # Используем in-memory базу данных для изоляции тестов
        self.db = Database(db_path=":memory:")

        # Добавляем тестовую игру
        self.game_id = self.db.add_game("test_game.exe", "Test Game")

        # Подготавливаем тестовые данные - 5 сессий в разные дни
        # Допустим, целевой диапазон: 2023-10-15 по 2023-10-20
        self.target_start_date = date(2023, 10, 15)
        self.target_end_date = date(2023, 10, 20)

        cursor = self.db.conn.cursor()

        # Данные: [(game_id, started_at)]
        test_sessions = [
            # До целевого диапазона (2023-10-14)
            (self.game_id, "2023-10-14T15:30:00"),
            # На нижней границе (2023-10-15)
            (self.game_id, "2023-10-15T00:00:00"),
            # Внутри диапазона (2023-10-17)
            (self.game_id, "2023-10-17T12:00:00"),
            # На верхней границе (2023-10-20)
            (self.game_id, "2023-10-20T23:59:59.999999"),
            # После целевого диапазона (2023-10-21)
            (self.game_id, "2023-10-21T00:00:00"),
        ]

        cursor.executemany('''
            INSERT INTO sessions (game_id, started_at)
            VALUES (?, ?)
        ''', test_sessions)

        self.db.conn.commit()

    def tearDown(self):
        self.db.close()

    def test_setup_created_sessions(self):
        """Проверка, что тестовые данные успешно созданы"""
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sessions")
        count = cursor.fetchone()[0]
        self.assertEqual(count, 5)

    def test_get_sessions_range_standard(self):
        """Проверка возврата сессий в пределах заданного диапазона (включая границы)"""
        sessions = self.db.get_sessions_range(self.target_start_date, self.target_end_date)

        # Должно вернуться ровно 3 сессии (15, 17, 20 числа)
        self.assertEqual(len(sessions), 3)

        # Проверяем даты, чтобы убедиться, что вернулись нужные сессии
        started_dates = [s["started_at"] for s in sessions]
        self.assertIn("2023-10-15T00:00:00", started_dates)
        self.assertIn("2023-10-17T12:00:00", started_dates)
        self.assertIn("2023-10-20T23:59:59.999999", started_dates)

        # Проверяем наличие дополнительных полей из JOIN (display_name, exe_name)
        for s in sessions:
            self.assertEqual(s["display_name"], "Test Game")
            self.assertEqual(s["exe_name"], "test_game.exe")

    def test_get_sessions_range_empty(self):
        """Проверка, когда в заданном диапазоне нет сессий"""
        # Ищем сессии в 2022 году (там их нет)
        start_date = date(2022, 1, 1)
        end_date = date(2022, 12, 31)

        sessions = self.db.get_sessions_range(start_date, end_date)

        # Ожидаем пустой список
        self.assertEqual(len(sessions), 0)

    def test_get_sessions_range_inverted_dates(self):
        """Проверка, когда начальная дата больше конечной (ожидается пустой результат)"""
        sessions = self.db.get_sessions_range(self.target_end_date, self.target_start_date)

        # Ожидаем пустой список, так как start_date > end_date
        self.assertEqual(len(sessions), 0)

    def test_get_sessions_range_single_day(self):
        """Проверка диапазона, состоящего из одного дня"""
        # Ищем сессии только 17 числа (должна быть 1 сессия)
        target_date = date(2023, 10, 17)
        sessions = self.db.get_sessions_range(target_date, target_date)

        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["started_at"], "2023-10-17T12:00:00")

if __name__ == '__main__':
    unittest.main()
