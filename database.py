"""
Модуль работы с SQLite базой данных для GameTimeTracker.
Содержит класс Database для всех операций с БД.
"""

import sqlite3
import csv
import os
from datetime import datetime, date
from typing import List, Dict, Optional, Any


class Database:
    """Класс для управления базой данных приложения"""

    def __init__(self, db_path: str = "data/gametracker.db"):
        """
        Инициализация подключения к БД и создание таблиц при необходимости

        Args:
            db_path: путь к файлу базы данных
        """
        # Создаём директорию для БД, если её нет
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        """Создание всех необходимых таблиц, если они не существуют"""
        cursor = self.conn.cursor()

        # Таблица игр
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exe_name TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                exe_path TEXT,
                icon_path TEXT,
                total_seconds INTEGER DEFAULT 0,
                last_launched TEXT,
                added_at TEXT NOT NULL,
                is_archived INTEGER DEFAULT 0,
                archived_at TEXT,
                launch_count INTEGER DEFAULT 0
            )
        ''')

        # Таблица сессий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                duration_seconds INTEGER DEFAULT 0,
                FOREIGN KEY (game_id) REFERENCES games (id) ON DELETE CASCADE
            )
        ''')

        # Таблица настроек
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')

        # Инициализация настроек по умолчанию, если таблица пуста
        cursor.execute("SELECT COUNT(*) FROM settings")
        if cursor.fetchone()[0] == 0:
            default_settings = [
                ("autostart", "false"),
                ("minimize_to_tray_on_start", "false"),
                ("track_only_active_window", "false"),
                ("notify_new_game", "true"),
                ("notify_long_session", "true"),
                ("long_session_minutes", "60"),
            ]
            cursor.executemany(
                "INSERT INTO settings (key, value) VALUES (?, ?)",
                default_settings
            )

        self.conn.commit()

    def _get_current_datetime(self) -> str:
        """Возвращает текущую дату и время в формате ISO для SQLite"""
        return datetime.now().isoformat()

    # ---------- Работа с играми ----------

    def add_game(self, exe_name: str, display_name: str, exe_path: str = None) -> int:
        """
        Добавляет новую игру в базу

        Returns:
            id добавленной игры
        """
        cursor = self.conn.cursor()
        now = self._get_current_datetime()
        cursor.execute('''
            INSERT INTO games (exe_name, display_name, exe_path, added_at)
            VALUES (?, ?, ?, ?)
        ''', (exe_name.lower(), display_name, exe_path, now))
        self.conn.commit()
        return cursor.lastrowid

    def get_all_games(self, archived: bool = False) -> List[Dict[str, Any]]:
        """
        Возвращает список игр (не архивные или архивные)

        Args:
            archived: если True — возвращаем архивные игры, иначе — активные
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM games
            WHERE is_archived = ?
            ORDER BY total_seconds DESC
        ''', (1 if archived else 0,))
        return [dict(row) for row in cursor.fetchall()]

    def get_game_by_id(self, game_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает игру по ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM games WHERE id = ?", (game_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_game_by_exe_name(self, exe_name: str) -> Optional[Dict[str, Any]]:
        """Возвращает игру по имени исполняемого файла (регистронезависимо)"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM games WHERE exe_name = ?", (exe_name.lower(),))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_game_time(self, game_id: int, seconds_to_add: int) -> None:
        """Увеличивает общее время игры на seconds_to_add"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE games
            SET total_seconds = total_seconds + ?,
                last_launched = ?
            WHERE id = ?
        ''', (seconds_to_add, self._get_current_datetime(), game_id))
        self.conn.commit()

    def increment_launch_count(self, game_id: int) -> None:
        """Увеличивает счётчик запусков игры"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE games SET launch_count = launch_count + 1 WHERE id = ?
        ''', (game_id,))
        self.conn.commit()

    def archive_game(self, game_id: int) -> None:
        """Переносит игру в архив"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE games
            SET is_archived = 1, archived_at = ?
            WHERE id = ?
        ''', (self._get_current_datetime(), game_id))
        self.conn.commit()

    def unarchive_game(self, game_id: int) -> None:
        """Возвращает игру из архива в активные"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE games
            SET is_archived = 0, archived_at = NULL
            WHERE id = ?
        ''', (game_id,))
        self.conn.commit()

    def delete_game(self, game_id: int) -> None:
        """Удаляет игру и все связанные сессии (каскадное удаление)"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM games WHERE id = ?", (game_id,))
        self.conn.commit()

    def rename_game(self, game_id: int, new_name: str) -> None:
        """Изменяет отображаемое название игры"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE games SET display_name = ? WHERE id = ?
        ''', (new_name, game_id))
        self.conn.commit()

    def update_icon_path(self, game_id: int, icon_path: str) -> None:
        """Сохраняет путь к иконке игры"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE games SET icon_path = ? WHERE id = ?
        ''', (icon_path, game_id))
        self.conn.commit()

    # ---------- Работа с сессиями ----------

    def start_session(self, game_id: int) -> int:
        """Создаёт новую сессию и возвращает её ID"""
        cursor = self.conn.cursor()
        now = self._get_current_datetime()
        cursor.execute('''
            INSERT INTO sessions (game_id, started_at)
            VALUES (?, ?)
        ''', (game_id, now))
        self.conn.commit()
        # Увеличиваем счётчик запусков
        self.increment_launch_count(game_id)
        return cursor.lastrowid

    def end_session(self, session_id: int, duration_seconds: int) -> None:
        """
        Завершает сессию, записывая длительность и время окончания
        """
        cursor = self.conn.cursor()
        now = self._get_current_datetime()
        cursor.execute('''
            UPDATE sessions
            SET ended_at = ?, duration_seconds = ?
            WHERE id = ?
        ''', (now, duration_seconds, session_id))
        self.conn.commit()

    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Возвращает все незавершённые сессии (ended_at IS NULL)"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM sessions WHERE ended_at IS NULL
        ''')
        return [dict(row) for row in cursor.fetchall()]

    def get_sessions_by_date(self, target_date: date) -> List[Dict[str, Any]]:
        """
        Возвращает все сессии за конкретную дату (по UTC дате из started_at)
        """
        start_str = target_date.isoformat() + "T00:00:00"
        end_str = target_date.isoformat() + "T23:59:59.999999"
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT s.*, g.display_name, g.exe_name
            FROM sessions s
            JOIN games g ON s.game_id = g.id
            WHERE s.started_at BETWEEN ? AND ?
            ORDER BY s.started_at
        ''', (start_str, end_str))
        return [dict(row) for row in cursor.fetchall()]

    def get_sessions_range(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """
        Возвращает все сессии в диапазоне дат (включительно)
        """
        start_str = start_date.isoformat() + "T00:00:00"
        end_str = end_date.isoformat() + "T23:59:59.999999"
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT s.*, g.display_name, g.exe_name
            FROM sessions s
            JOIN games g ON s.game_id = g.id
            WHERE s.started_at BETWEEN ? AND ?
            ORDER BY s.started_at
        ''', (start_str, end_str))
        return [dict(row) for row in cursor.fetchall()]

    # ---------- Настройки ----------

    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """Возвращает значение настройки или default, если не найдена"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        """Устанавливает значение настройки (создаёт или обновляет)"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
        ''', (key, value))
        self.conn.commit()

    # ---------- Экспорт ----------

    def export_sessions_csv(self, filepath: str) -> bool:
        """
        Экспортирует все сессии в CSV-файл.
        Возвращает True в случае успеха.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT
                    s.id,
                    g.display_name as game_name,
                    s.started_at,
                    s.ended_at,
                    s.duration_seconds
                FROM sessions s
                JOIN games g ON s.game_id = g.id
                ORDER BY s.started_at
            ''')
            rows = cursor.fetchall()

            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['ID', 'Игра', 'Начало', 'Конец', 'Длительность (сек)'])
                for row in rows:
                    writer.writerow([
                        row['id'], row['game_name'],
                        row['started_at'], row['ended_at'],
                        row['duration_seconds']
                    ])
            return True
        except Exception as e:
            print(f"Ошибка экспорта CSV: {e}")
            return False

    def close(self) -> None:
        """Закрывает соединение с БД"""
        if self.conn:
            self.conn.close()