"""
Модуль работы с SQLite базой данных для GameTimeTracker.
Содержит класс Database для всех операций с БД.
"""

import csv
import html
import json
import logging
import os
import sqlite3
import threading
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from utils import format_duration, get_base_dir

logger = logging.getLogger(__name__)

# Версия схемы БД. Увеличивается при изменении структуры таблиц,
# чтобы существующие базы данных можно было аккуратно мигрировать.
SCHEMA_VERSION = 3


class Database:
    """Класс для управления базой данных приложения"""

    def __init__(self, db_path: Optional[str] = None):
        """
        Инициализация подключения к БД и создание таблиц при необходимости

        Args:
            db_path: путь к файлу базы данных
        """
        if db_path is None or db_path == "data/gametracker.db":
            db_path = os.path.join(get_base_dir(), "data", "gametracker.db")

        self.lock = threading.RLock()

        # Создаём директорию для БД, если её нет (для :memory: пути не будет)
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self.db_path = db_path
        self._is_memory = db_path == ":memory:" or db_path.startswith("file::memory:")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._configure_connection()
        self._create_tables()
        self._migrate_schema()
        self._create_indexes()
        self.cleanup_zombie_sessions()

    def _configure_connection(self) -> None:
        """
        Настраивает соединение SQLite для надёжной параллельной работы.

        * foreign_keys — каскадное удаление сессий вместе с игрой;
        * busy_timeout — вместо мгновенной ошибки «database is locked» SQLite
          ждёт до 5 секунд, пока другой поток/процесс освободит блокировку;
        * WAL — позволяет читать базу во время записи (UI не «замирает»,
          пока трекер сбрасывает прогресс);
        * synchronous=NORMAL — безопасный компромисс между скоростью и
          устойчивостью к сбоям при работе в режиме WAL.
        """
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA busy_timeout = 5000")
        if not self._is_memory:
            try:
                self.conn.execute("PRAGMA journal_mode = WAL")
                self.conn.execute("PRAGMA synchronous = NORMAL")
            except sqlite3.DatabaseError as e:  # pragma: no cover - редкие ФС
                logger.warning("Не удалось включить WAL-режим: %s", e)

    def _create_tables(self) -> None:
        """Создание всех необходимых таблиц, если они не существуют"""
        with self.lock:
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

            # Таблица игнорируемых процессов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ignored_processes (
                    exe_name TEXT PRIMARY KEY,
                    ignored_at TEXT NOT NULL
                )
            ''')

            # Таблица ожидающих уведомлений об обнаруженных играх
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pending_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exe_name TEXT NOT NULL UNIQUE,
                    exe_path TEXT,
                    detected_at TEXT NOT NULL
                )
            ''')

            # Индексы для ускорения выборок по датам и сессиям
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON sessions (started_at)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sessions_game_id ON sessions (game_id)
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

    def _create_indexes(self) -> None:
        """Создаёт индексы, зависящие от колонок, добавленных миграциями."""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_ended_at ON sessions (ended_at)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_games_is_archived ON games (is_archived)"
            )
            self.conn.commit()

    # ---------- Версионирование схемы ----------

    def _column_exists(self, table: str, column: str) -> bool:
        """Проверяет наличие колонки в таблице."""
        cursor = self.conn.execute(f"PRAGMA table_info({table})")
        return any(row[1] == column for row in cursor.fetchall())

    def _ensure_column(self, table: str, column: str, definition: str) -> bool:
        """Добавляет колонку, если её нет (миграция старых баз данных)."""
        if self._column_exists(table, column):
            return False
        self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        logger.info("Миграция БД: добавлена колонка %s.%s", table, column)
        return True

    def get_schema_version(self) -> int:
        """Возвращает версию схемы БД (PRAGMA user_version)."""
        row = self.conn.execute("PRAGMA user_version").fetchone()
        return int(row[0]) if row else 0

    def _migrate_schema(self) -> None:
        """
        Приводит схему существующей базы к актуальной версии.

        `CREATE TABLE IF NOT EXISTS` не добавляет новые колонки в уже
        существующие таблицы, поэтому апгрейд со старых версий приложения
        без миграций приводил бы к ошибкам «no such column».
        """
        with self.lock:
            changed = False
            # v1 -> v2: колонки, появившиеся в более поздних версиях приложения
            changed |= self._ensure_column("games", "is_archived", "INTEGER DEFAULT 0")
            changed |= self._ensure_column("games", "archived_at", "TEXT")
            changed |= self._ensure_column("games", "launch_count", "INTEGER DEFAULT 0")
            # v3: индивидуальный дневной лимит для конкретной игры (NULL — без лимита)
            changed |= self._ensure_column("games", "daily_limit_minutes", "INTEGER")
            changed |= self._ensure_column("sessions", "duration_seconds", "INTEGER DEFAULT 0")

            if self.get_schema_version() < SCHEMA_VERSION:
                self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                changed = True

            if changed:
                self.conn.commit()
                logger.info("Схема БД обновлена до версии %s", SCHEMA_VERSION)

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
        with self.lock:
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
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT * FROM games
                WHERE is_archived = ?
                ORDER BY total_seconds DESC
            ''', (1 if archived else 0,))
            return [dict(row) for row in cursor.fetchall()]

    def get_game_by_id(self, game_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает игру по ID"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM games WHERE id = ?", (game_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_game_by_exe_name(self, exe_name: str) -> Optional[Dict[str, Any]]:
        """Возвращает игру по имени исполняемого файла (регистронезависимо)"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM games WHERE exe_name = ?", (exe_name.lower(),))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_game_time(self, game_id: int, seconds_to_add: int,
                         touch_last_launched: bool = True) -> None:
        """
        Увеличивает общее время игры на seconds_to_add.

        Args:
            touch_last_launched: обновлять ли дату последнего запуска. При
                периодическом сбросе прогресса (каждые 60 секунд) дату трогать
                не нужно — иначе «Последний запуск» всегда показывает «сейчас».
        """
        with self.lock:
            cursor = self.conn.cursor()
            if touch_last_launched:
                cursor.execute('''
                    UPDATE games
                    SET total_seconds = total_seconds + ?,
                        last_launched = ?
                    WHERE id = ?
                ''', (seconds_to_add, self._get_current_datetime(), game_id))
            else:
                cursor.execute('''
                    UPDATE games
                    SET total_seconds = total_seconds + ?
                    WHERE id = ?
                ''', (seconds_to_add, game_id))
            self.conn.commit()

    def increment_launch_count(self, game_id: int) -> None:
        """Увеличивает счётчик запусков игры"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE games SET launch_count = launch_count + 1 WHERE id = ?
            ''', (game_id,))
            self.conn.commit()

    def archive_game(self, game_id: int) -> None:
        """Переносит игру в архив"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE games
                SET is_archived = 1, archived_at = ?
                WHERE id = ?
            ''', (self._get_current_datetime(), game_id))
            self.conn.commit()

    def unarchive_game(self, game_id: int) -> None:
        """Возвращает игру из архива в активные"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE games
                SET is_archived = 0, archived_at = NULL
                WHERE id = ?
            ''', (game_id,))
            self.conn.commit()

    def delete_game(self, game_id: int) -> None:
        """Удаляет игру и все связанные сессии (каскадное удаление)"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM games WHERE id = ?", (game_id,))
            self.conn.commit()

    def rename_game(self, game_id: int, new_name: str) -> None:
        """Изменяет отображаемое название игры"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE games SET display_name = ? WHERE id = ?
            ''', (new_name, game_id))
            self.conn.commit()

    def update_icon_path(self, game_id: int, icon_path: str) -> None:
        """Сохраняет путь к иконке игры"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE games SET icon_path = ? WHERE id = ?
            ''', (icon_path, game_id))
            self.conn.commit()

    def set_game_daily_limit(self, game_id: int, minutes: Optional[int]) -> None:
        """
        Задаёт индивидуальный дневной лимит игры в минутах.

        Args:
            minutes: минуты (>= 1) или None, чтобы снять лимит.
        """
        with self.lock:
            if minutes is None:
                self.conn.execute(
                    "UPDATE games SET daily_limit_minutes = NULL WHERE id = ?", (game_id,)
                )
            else:
                self.conn.execute(
                    "UPDATE games SET daily_limit_minutes = ? WHERE id = ?",
                    (max(int(minutes), 1), game_id),
                )
            self.conn.commit()

    def get_games_with_limits(self, include_archived: bool = False) -> List[Dict[str, Any]]:
        """Возвращает игры, для которых задан индивидуальный дневной лимит."""
        with self.lock:
            query = '''
                SELECT id, display_name, exe_name, daily_limit_minutes
                FROM games
                WHERE daily_limit_minutes IS NOT NULL AND daily_limit_minutes > 0
            '''
            if not include_archived:
                query += ' AND is_archived = 0'
            query += ' ORDER BY display_name'
            rows = self.conn.execute(query).fetchall()
            return [dict(row) for row in rows]

    def get_game_seconds_for_day(self, game_id: int, target_date: date) -> int:
        """Игровое время конкретной игры за день (с делением сессий через полночь)."""
        total = 0
        for session in self._get_sessions_overlapping(target_date, target_date, True):
            if session.get('game_id') != game_id:
                continue
            start, end, duration = self._session_bounds(session)
            total += self._split_interval_by_day(start, end, duration).get(target_date, 0)
        return total

    # ---------- Итоги недели ----------

    def get_weekly_digest(self, today: Optional[date] = None,
                          include_archived: bool = True) -> Dict[str, Any]:
        """
        Сводка за последние 7 дней для еженедельного уведомления.

        Returns:
            Словарь: total_seconds, prev_week_seconds, delta_seconds,
            top_game, top_game_seconds, active_days, streak, best_day,
            best_day_seconds, period_start, period_end.
        """
        period_end = today or date.today()
        period_start = period_end - timedelta(days=6)
        daily = self.get_daily_totals(period_start, period_end, include_archived)
        total = sum(daily.values())

        prev_start = period_start - timedelta(days=7)
        prev_total = self.get_period_total_seconds(
            prev_start, period_start - timedelta(days=1), include_archived
        )

        game_totals: Dict[str, int] = {}
        for day_map in self.get_day_breakdowns(period_start, period_end, include_archived).values():
            for name, seconds in day_map.items():
                game_totals[name] = game_totals.get(name, 0) + seconds
        top_game, top_seconds = ("", 0)
        if game_totals:
            top_game, top_seconds = max(game_totals.items(), key=lambda item: item[1])

        best_day = max(daily.items(), key=lambda item: item[1]) if daily else (None, 0)

        return {
            'total_seconds': total,
            'prev_week_seconds': prev_total,
            'delta_seconds': total - prev_total,
            'top_game': top_game,
            'top_game_seconds': top_seconds,
            'active_days': sum(1 for secs in daily.values() if secs > 0),
            'streak': self.get_current_streak(period_end, include_archived),
            'best_day': best_day[0],
            'best_day_seconds': best_day[1],
            'period_start': period_start,
            'period_end': period_end,
        }

    # ---------- Работа с сессиями ----------

    def start_session(self, game_id: int) -> int:
        """Создаёт новую сессию и возвращает её ID"""
        with self.lock:
            cursor = self.conn.cursor()
            now = self._get_current_datetime()
            cursor.execute('''
                INSERT INTO sessions (game_id, started_at)
                VALUES (?, ?)
            ''', (game_id, now))
            self.conn.commit()
            last_id = cursor.lastrowid
            # Увеличиваем счётчик запусков
            self.increment_launch_count(game_id)
            return last_id

    def end_session(self, session_id: int, duration_seconds: int) -> None:
        """
        Завершает сессию, записывая длительность и время окончания
        """
        with self.lock:
            cursor = self.conn.cursor()
            now = self._get_current_datetime()
            cursor.execute('''
                UPDATE sessions
                SET ended_at = ?, duration_seconds = ?
                WHERE id = ?
            ''', (now, duration_seconds, session_id))
            self.conn.commit()

    def update_session_duration(self, session_id: int, duration_seconds: int) -> None:
        """Обновляет текущую длительность активной сессии без установки ended_at"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE sessions
                SET duration_seconds = ?
                WHERE id = ?
            ''', (duration_seconds, session_id))
            self.conn.commit()

    def cleanup_zombie_sessions(self) -> int:
        """
        Закрывает незавершённые («зомби») сессии от предыдущих некорректных завершений работы.
        Если duration_seconds > 0, вычисляет ended_at от started_at.
        Если duration_seconds <= 0 или NULL, устанавливает ended_at = started_at, duration_seconds = 0.
        Возвращает количество закрытых сессий.
        """
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE sessions
                SET ended_at = CASE
                    WHEN duration_seconds > 0 THEN COALESCE(strftime('%Y-%m-%dT%H:%M:%S', datetime(started_at, '+' || duration_seconds || ' seconds')), started_at)
                    ELSE started_at
                END,
                duration_seconds = CASE
                    WHEN duration_seconds > 0 THEN duration_seconds
                    ELSE 0
                END
                WHERE ended_at IS NULL
            ''')
            affected = cursor.rowcount
            self.conn.commit()
            return affected

    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Возвращает все незавершённые сессии (ended_at IS NULL)"""
        with self.lock:
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
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT s.*, g.display_name, g.exe_name
                FROM sessions s
                JOIN games g ON s.game_id = g.id
                WHERE s.started_at BETWEEN ? AND ?
                ORDER BY s.started_at
            ''', (start_str, end_str))
            return [dict(row) for row in cursor.fetchall()]

    def get_sessions_range(self, start_date: date, end_date: date, include_archived: bool = True) -> List[Dict[str, Any]]:
        """
        Возвращает все сессии в диапазоне дат (включительно)
        """
        start_str = start_date.isoformat() + "T00:00:00"
        end_str = end_date.isoformat() + "T23:59:59.999999"
        with self.lock:
            cursor = self.conn.cursor()
            query = '''
                SELECT s.*, g.display_name, g.exe_name
                FROM sessions s
                JOIN games g ON s.game_id = g.id
                WHERE s.started_at BETWEEN ? AND ?
            '''
            if not include_archived:
                query += ' AND g.is_archived = 0'
            query += ' ORDER BY s.started_at'
            cursor.execute(query, (start_str, end_str))
            return [dict(row) for row in cursor.fetchall()]

    def get_longest_session(self, include_archived: bool = True) -> Optional[Dict[str, Any]]:
        """Возвращает самую длинную сессию с информацией об игре"""
        with self.lock:
            cursor = self.conn.cursor()
            query = '''
                SELECT s.duration_seconds, g.display_name, s.started_at
                FROM sessions s
                JOIN games g ON s.game_id = g.id
                WHERE s.duration_seconds IS NOT NULL
            '''
            if not include_archived:
                query += ' AND g.is_archived = 0'
            query += ' ORDER BY s.duration_seconds DESC LIMIT 1'
            cursor.execute(query)
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_best_day(self, include_archived: bool = True) -> Optional[Dict[str, Any]]:
        """Возвращает день с наибольшим суммарным игровым временем"""
        with self.lock:
            cursor = self.conn.cursor()
            query = '''
                SELECT DATE(s.started_at) as day, SUM(s.duration_seconds) as total
                FROM sessions s
                JOIN games g ON s.game_id = g.id
                WHERE s.duration_seconds IS NOT NULL
            '''
            if not include_archived:
                query += ' AND g.is_archived = 0'
            query += ' GROUP BY day ORDER BY total DESC LIMIT 1'
            cursor.execute(query)
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_games_session_stats(self, include_archived: bool = False) -> List[Dict[str, Any]]:
        """Возвращает статистику сессий по играм (количество сессий и среднее время)"""
        with self.lock:
            cursor = self.conn.cursor()
            where_clause = "WHERE s.duration_seconds IS NOT NULL"
            if not include_archived:
                where_clause += " AND g.is_archived = 0"
            cursor.execute(f'''
                SELECT g.display_name, g.is_archived, COUNT(s.id) as session_count, AVG(s.duration_seconds) as avg_sec
                FROM games g
                LEFT JOIN sessions s ON g.id = s.game_id
                {where_clause}
                GROUP BY g.id
                ORDER BY avg_sec DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]

    # ---------- Игнорируемые процессы ----------

    def add_ignored_process(self, exe_name: str) -> None:
        """Добавляет имя исполняемого файла в список игнорируемых"""
        if not exe_name:
            return
        with self.lock:
            cursor = self.conn.cursor()
            now = self._get_current_datetime()
            cursor.execute('''
                INSERT OR REPLACE INTO ignored_processes (exe_name, ignored_at)
                VALUES (?, ?)
            ''', (exe_name.lower(), now))
            self.conn.commit()

    def remove_ignored_process(self, exe_name: str) -> None:
        """Удаляет исполняемый файл из списка игнорируемых"""
        if not exe_name:
            return
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM ignored_processes WHERE exe_name = ?", (exe_name.lower(),))
            self.conn.commit()

    def get_ignored_processes(self) -> List[Dict[str, Any]]:
        """Возвращает список всех игнорируемых процессов"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM ignored_processes ORDER BY exe_name ASC")
            return [dict(row) for row in cursor.fetchall()]

    def is_process_ignored(self, exe_name: str) -> bool:
        """Проверяет, находится ли процесс в списке игнорируемых"""
        if not exe_name:
            return False
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT 1 FROM ignored_processes WHERE exe_name = ?", (exe_name.lower(),))
            return cursor.fetchone() is not None

    # ---------- Ожидающие уведомления ----------

    def add_pending_notification(self, exe_name: str, exe_path: Optional[str] = None) -> None:
        """Сохраняет ожидающее уведомление о новом процессе"""
        if not exe_name:
            return
        with self.lock:
            cursor = self.conn.cursor()
            now = self._get_current_datetime()
            cursor.execute('''
                INSERT OR REPLACE INTO pending_notifications (exe_name, exe_path, detected_at)
                VALUES (?, ?, ?)
            ''', (exe_name.lower(), exe_path, now))
            self.conn.commit()

    def remove_pending_notification(self, exe_name: str) -> None:
        """Удаляет уведомление для процесса"""
        if not exe_name:
            return
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM pending_notifications WHERE exe_name = ?", (exe_name.lower(),))
            self.conn.commit()

    def get_pending_notifications(self) -> List[Dict[str, Any]]:
        """Возвращает все ожидающие уведомления"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM pending_notifications ORDER BY id DESC")
            return [dict(row) for row in cursor.fetchall()]

    def clear_pending_notifications(self) -> None:
        """Очищает все ожидающие уведомления"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM pending_notifications")
            self.conn.commit()

    # ---------- Настройки ----------

    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """Возвращает значение настройки или default, если не найдена"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        """Устанавливает значение настройки (создаёт или обновляет)"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
            ''', (key, value))
            self.conn.commit()

    # ---------- Аналитика по дням ----------
    #
    # Важно: сессия может пересекать полночь (например, 23:30 → 01:15).
    # Раньше такие сессии целиком относились к дню старта, из-за чего
    # календарь и график активности «съезжали». Методы ниже делят
    # длительность сессии по фактическим дням пропорционально пересечению.

    @staticmethod
    def _split_interval_by_day(start: datetime, end: datetime,
                               total_seconds: int) -> Dict[date, int]:
        """
        Делит total_seconds между календарными днями интервала [start, end).

        Сумма значений в результате всегда равна floor(total_seconds)
        (остаток от округления отдаётся последнему дню).
        """
        total_seconds = max(int(total_seconds or 0), 0)
        if total_seconds == 0:
            return {}
        if end <= start:
            return {start.date(): total_seconds}

        weights: Dict[date, float] = {}
        cursor = start
        while cursor < end:
            next_midnight = datetime.combine(cursor.date() + timedelta(days=1), time.min)
            segment_end = min(end, next_midnight)
            weights[cursor.date()] = weights.get(cursor.date(), 0.0) + \
                (segment_end - cursor).total_seconds()
            cursor = segment_end

        window = (end - start).total_seconds()
        days = list(weights.items())
        result: Dict[date, int] = {}
        allocated = 0
        for day, weight in days[:-1]:
            value = int(total_seconds * weight / window)
            if value:
                result[day] = value
                allocated += value
        last_day = days[-1][0]
        result[last_day] = result.get(last_day, 0) + (total_seconds - allocated)
        return {day: secs for day, secs in result.items() if secs}

    @staticmethod
    def _session_bounds(session: Dict[str, Any]) -> Tuple[datetime, datetime, int]:
        """Возвращает (начало, конец, длительность) сессии."""
        duration = max(int(session.get('duration_seconds') or 0), 0)
        try:
            start = datetime.fromisoformat(session['started_at'])
        except (KeyError, TypeError, ValueError):
            start = datetime.now()
        end = None
        if session.get('ended_at'):
            try:
                end = datetime.fromisoformat(session['ended_at'])
            except (TypeError, ValueError):
                end = None
        if end is None or end <= start:
            end = start + timedelta(seconds=duration)
        return start, end, duration

    def _get_sessions_overlapping(self, start_date: date, end_date: date,
                                  include_archived: bool = True) -> List[Dict[str, Any]]:
        """Возвращает сессии, которые хотя бы частично попадают в диапазон дат."""
        start_str = start_date.isoformat() + "T00:00:00"
        end_str = end_date.isoformat() + "T23:59:59.999999"
        with self.lock:
            cursor = self.conn.cursor()
            query = '''
                SELECT s.*, g.display_name, g.exe_name, g.is_archived
                FROM sessions s
                JOIN games g ON s.game_id = g.id
                WHERE s.duration_seconds > 0
                  AND s.started_at <= ?
                  AND (s.ended_at IS NULL OR s.ended_at >= ?)
            '''
            if not include_archived:
                query += ' AND g.is_archived = 0'
            query += ' ORDER BY s.started_at'
            cursor.execute(query, (end_str, start_str))
            return [dict(row) for row in cursor.fetchall()]

    def get_daily_totals(self, start_date: date, end_date: date,
                         include_archived: bool = True) -> Dict[date, int]:
        """
        Возвращает суммарное игровое время по дням диапазона (включительно).

        В отличие от простой группировки по `started_at`, длительность сессий,
        пересекающих полночь, распределяется между днями корректно.
        """
        totals: Dict[date, int] = {}
        if end_date < start_date:
            return totals
        for session in self._get_sessions_overlapping(start_date, end_date, include_archived):
            start, end, duration = self._session_bounds(session)
            for day, seconds in self._split_interval_by_day(start, end, duration).items():
                if start_date <= day <= end_date:
                    totals[day] = totals.get(day, 0) + seconds
        return totals

    def get_day_breakdowns(self, start_date: date, end_date: date,
                           include_archived: bool = True) -> Dict[date, Dict[str, int]]:
        """
        Возвращает разбивку времени по дням и играм за период одним проходом.

        Используется календарём, чтобы не выполнять отдельный запрос на каждый
        день месяца.
        """
        result: Dict[date, Dict[str, int]] = {}
        if end_date < start_date:
            return result
        for session in self._get_sessions_overlapping(start_date, end_date, include_archived):
            start, end, duration = self._session_bounds(session)
            name = session.get('display_name') or session.get('exe_name') or 'Неизвестная игра'
            for day, seconds in self._split_interval_by_day(start, end, duration).items():
                if start_date <= day <= end_date:
                    day_map = result.setdefault(day, {})
                    day_map[name] = day_map.get(name, 0) + seconds
        return result

    def get_top_games(self, start_date: date, end_date: date, limit: int = 5,
                      include_archived: bool = False) -> List[Dict[str, Any]]:
        """
        Возвращает топ игр по времени **за указанный период**.

        В отличие от сортировки `games.total_seconds` (время за всё время),
        здесь учитываются только сессии, попавшие в диапазон, причём сессии,
        пересекающие полночь, делятся по дням корректно.

        Returns:
            Список словарей с id, display_name, exe_name, is_archived,
            seconds и share (доля от суммарного времени периода, 0..1),
            отсортированный по убыванию времени.
        """
        totals: Dict[int, Dict[str, Any]] = {}
        if end_date < start_date:
            return []
        for session in self._get_sessions_overlapping(start_date, end_date, include_archived):
            start, end, duration = self._session_bounds(session)
            in_period = sum(
                seconds for day, seconds in self._split_interval_by_day(start, end, duration).items()
                if start_date <= day <= end_date
            )
            if in_period <= 0:
                continue
            game_id = session['game_id']
            entry = totals.setdefault(game_id, {
                'id': game_id,
                'display_name': session.get('display_name') or session.get('exe_name'),
                'exe_name': session.get('exe_name'),
                'is_archived': bool(session.get('is_archived')),
                'seconds': 0,
            })
            entry['seconds'] += in_period

        overall = sum(entry['seconds'] for entry in totals.values())
        result = sorted(totals.values(), key=lambda item: item['seconds'], reverse=True)
        for entry in result:
            entry['share'] = (entry['seconds'] / overall) if overall else 0.0
        return result[:max(limit, 1)] if limit else result

    def get_day_breakdown(self, target_date: date,
                          include_archived: bool = True) -> Dict[str, int]:
        """Возвращает разбивку игрового времени за день по названиям игр."""
        return self.get_day_breakdowns(target_date, target_date, include_archived).get(target_date, {})

    def get_period_total_seconds(self, start_date: date, end_date: date,
                                 include_archived: bool = True) -> int:
        """Суммарное игровое время за период (с корректным делением сессий по дням)."""
        return sum(self.get_daily_totals(start_date, end_date, include_archived).values())

    def get_today_seconds(self, include_archived: bool = True,
                          today: Optional[date] = None) -> int:
        """Игровое время за сегодня."""
        target = today or date.today()
        return self.get_period_total_seconds(target, target, include_archived)

    def get_active_days_count(self, start_date: date, end_date: date,
                              include_archived: bool = True) -> int:
        """Количество дней в периоде, в которые была игровая активность."""
        return sum(1 for secs in self.get_daily_totals(start_date, end_date, include_archived).values()
                   if secs > 0)

    def get_current_streak(self, reference_date: Optional[date] = None,
                           include_archived: bool = True,
                           max_days: int = 3650) -> int:
        """
        Длина текущей серии дней подряд с игровой активностью.

        Серия считается продолжающейся, если активность была сегодня или
        вчера (вчера — чтобы серия не обнулялась утром до первого запуска игры).
        """
        reference = reference_date or date.today()
        start = reference - timedelta(days=max_days)
        totals = self.get_daily_totals(start, reference, include_archived)
        if not totals.get(reference) and not totals.get(reference - timedelta(days=1)):
            return 0
        day = reference if totals.get(reference) else reference - timedelta(days=1)
        streak = 0
        while totals.get(day):
            streak += 1
            day -= timedelta(days=1)
        return streak

    def get_average_daily_seconds(self, days: int = 30, include_archived: bool = True,
                                  only_active_days: bool = False,
                                  today: Optional[date] = None) -> int:
        """Среднее игровое время в день за последние `days` дней."""
        end = today or date.today()
        start = end - timedelta(days=max(days, 1) - 1)
        totals = self.get_daily_totals(start, end, include_archived)
        if only_active_days:
            values = [secs for secs in totals.values() if secs > 0]
            divisor = len(values) or 1
            return int(sum(values) / divisor)
        return int(sum(totals.values()) / max(days, 1))

    def get_activity_summary(self, days: int = 30,
                             include_archived: bool = True) -> Dict[str, int]:
        """
        Сводка активности для карточек статистики.

        Returns:
            Словарь с ключами today, week, avg_daily, streak, active_days, period_total.
        """
        today = date.today()
        period_start = today - timedelta(days=max(days, 1) - 1)
        totals = self.get_daily_totals(period_start, today, include_archived)
        week_start = today - timedelta(days=6)
        return {
            'today': totals.get(today, 0),
            'week': sum(secs for day, secs in totals.items() if day >= week_start),
            'avg_daily': int(sum(totals.values()) / max(days, 1)),
            'streak': self.get_current_streak(today, include_archived),
            'active_days': sum(1 for secs in totals.values() if secs > 0),
            'period_total': sum(totals.values()),
        }

    # ---------- Полный экспорт / импорт (JSON) ----------

    DATA_FORMAT = "gametimetracker-data"
    DATA_FORMAT_VERSION = 1

    def export_data_json(self, filepath: str) -> bool:
        """
        Экспортирует все данные приложения в JSON-файл.

        В отличие от CSV-экспорта (только история сессий), JSON содержит полный
        снимок: игры с накопленным временем, сессии и список игнорируемых
        процессов — файл можно перенести на другой компьютер и импортировать.
        """
        try:
            with self.lock:
                games = [dict(row) for row in self.conn.execute(
                    "SELECT * FROM games ORDER BY id"
                ).fetchall()]
                sessions = [dict(row) for row in self.conn.execute(
                    "SELECT * FROM sessions ORDER BY id"
                ).fetchall()]
                ignored = [dict(row) for row in self.conn.execute(
                    "SELECT * FROM ignored_processes ORDER BY exe_name"
                ).fetchall()]

            payload = {
                "format": self.DATA_FORMAT,
                "format_version": self.DATA_FORMAT_VERSION,
                "schema_version": self.get_schema_version(),
                "exported_at": self._get_current_datetime(),
                "games": games,
                "sessions": sessions,
                "ignored_processes": ignored,
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            logger.info("Данные экспортированы в JSON: %s", filepath)
            return True
        except Exception as e:
            logger.exception("Ошибка экспорта JSON: %s", e)
            return False

    def import_data_json(self, filepath: str, replace: bool = True,
                         auto_backup: bool = True) -> Dict[str, Any]:
        """
        Импортирует данные из JSON-файла, созданного `export_data_json`.

        Args:
            filepath: путь к JSON-файлу.
            replace: True — заменить текущие игры и сессии, False — добавить новые.
            auto_backup: создать резервную копию текущей БД перед заменой.

        Returns:
            Сводка импорта: games, sessions, ignored, backup.

        Raises:
            ValueError: если файл не является экспортом GameTimeTracker.
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise ValueError(f"Не удалось прочитать файл: {e}") from e

        if not isinstance(payload, dict) or payload.get("format") != self.DATA_FORMAT:
            raise ValueError("Файл не является экспортом GameTimeTracker")
        if int(payload.get("format_version", 0)) > self.DATA_FORMAT_VERSION:
            raise ValueError("Файл создан более новой версией приложения")

        games = payload.get("games") or []
        sessions = payload.get("sessions") or []
        ignored = payload.get("ignored_processes") or []

        backup_path = None
        if auto_backup and replace:
            backup_path = self.create_rotating_backup()

        imported_games = 0
        imported_sessions = 0
        imported_ignored = 0

        with self.lock:
            try:
                with self.conn:  # транзакция: при ошибке всё откатится
                    if replace:
                        self.conn.execute("DELETE FROM sessions")
                        self.conn.execute("DELETE FROM games")
                        self.conn.execute("DELETE FROM ignored_processes")

                    id_map: Dict[int, int] = {}
                    for game in games:
                        exe_name = str(game.get("exe_name") or "").strip().lower()
                        if not exe_name:
                            continue
                        display_name = str(game.get("display_name") or exe_name)
                        existing = None if replace else self.conn.execute(
                            "SELECT id FROM games WHERE exe_name = ?", (exe_name,)
                        ).fetchone()
                        if existing:
                            id_map[int(game.get("id", 0))] = int(existing[0])
                            continue
                        cursor = self.conn.execute(
                            '''
                            INSERT INTO games (
                                exe_name, display_name, exe_path, icon_path, total_seconds,
                                last_launched, added_at, is_archived, archived_at,
                                launch_count, daily_limit_minutes
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''',
                            (
                                exe_name,
                                display_name,
                                game.get("exe_path"),
                                None,  # пути к иконкам не переносимы между машинами
                                int(game.get("total_seconds") or 0),
                                game.get("last_launched"),
                                game.get("added_at") or self._get_current_datetime(),
                                int(game.get("is_archived") or 0),
                                game.get("archived_at"),
                                int(game.get("launch_count") or 0),
                                game.get("daily_limit_minutes"),
                            ),
                        )
                        if game.get("id") is not None:
                            id_map[int(game["id"])] = int(cursor.lastrowid)
                        imported_games += 1

                    for session in sessions:
                        old_game_id = session.get("game_id")
                        new_game_id = id_map.get(int(old_game_id)) if old_game_id is not None else None
                        if new_game_id is None:
                            continue
                        self.conn.execute(
                            '''
                            INSERT INTO sessions (game_id, started_at, ended_at, duration_seconds)
                            VALUES (?, ?, ?, ?)
                            ''',
                            (
                                new_game_id,
                                session.get("started_at") or self._get_current_datetime(),
                                session.get("ended_at"),
                                int(session.get("duration_seconds") or 0),
                            ),
                        )
                        imported_sessions += 1

                    for item in ignored:
                        exe_name = str(item.get("exe_name") or "").strip().lower()
                        if not exe_name:
                            continue
                        self.conn.execute(
                            "INSERT OR REPLACE INTO ignored_processes (exe_name, ignored_at) "
                            "VALUES (?, ?)",
                            (exe_name, item.get("ignored_at") or self._get_current_datetime()),
                        )
                        imported_ignored += 1
            except Exception:
                logger.exception("Ошибка импорта JSON, изменения откачены")
                raise

        logger.info(
            "Импорт JSON завершён: игр %s, сессий %s, игноров %s",
            imported_games, imported_sessions, imported_ignored,
        )
        return {
            "games": imported_games,
            "sessions": imported_sessions,
            "ignored": imported_ignored,
            "backup": backup_path,
        }

    # ---------- Экспорт ----------

    def _sanitize_csv_value(self, value: Any) -> Any:
        """
        Очищает значение от возможных CSV-инъекций.
        Если строка начинается с =, +, -, или @, добавляет одинарную кавычку.
        """
        if isinstance(value, str) and value and value[0] in ('=', '+', '-', '@'):
            return f"'{value}"
        return value

    def export_sessions_csv(self, filepath: str) -> bool:
        """
        Экспортирует все сессии в CSV-файл.
        Возвращает True в случае успеха.
        """
        try:
            with self.lock:
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
                        self._sanitize_csv_value(row['id']),
                        self._sanitize_csv_value(row['game_name']),
                        self._sanitize_csv_value(row['started_at']),
                        self._sanitize_csv_value(row['ended_at']),
                        self._sanitize_csv_value(row['duration_seconds'])
                    ])
            return True
        except Exception as e:
            logger.exception("Ошибка экспорта CSV: %s", e)
            return False

    def export_report_html(self, filepath: str, start_date: date, end_date: date,
                           include_archived: bool = True) -> bool:
        """
        Экспортирует красивый автономный HTML-отчёт за период.

        В отличие от CSV, отчёт содержит сводку, разбивку по играм и по дням,
        его удобно отправить или открыть в браузере без Excel.
        Возвращает True в случае успеха.
        """
        try:
            daily = self.get_daily_totals(start_date, end_date, include_archived)
            game_totals: Dict[str, int] = {}
            for session in self._get_sessions_overlapping(start_date, end_date, include_archived):
                start, end, duration = self._session_bounds(session)
                name = session.get('display_name') or session.get('exe_name') or 'Неизвестная игра'
                for day, seconds in self._split_interval_by_day(start, end, duration).items():
                    if start_date <= day <= end_date:
                        game_totals[name] = game_totals.get(name, 0) + seconds

            total = sum(daily.values())
            active_days = sum(1 for secs in daily.values() if secs > 0)
            period_days = (end_date - start_date).days + 1
            longest = None
            with self.lock:
                cursor = self.conn.cursor()
                query = '''
                    SELECT s.duration_seconds, g.display_name
                    FROM sessions s JOIN games g ON s.game_id = g.id
                    WHERE s.duration_seconds > 0 AND s.started_at <= ?
                      AND (s.ended_at IS NULL OR s.ended_at >= ?)
                '''
                if not include_archived:
                    query += ' AND g.is_archived = 0'
                query += ' ORDER BY s.duration_seconds DESC LIMIT 1'
                cursor.execute(query, (end_date.isoformat() + "T23:59:59.999999",
                                       start_date.isoformat() + "T00:00:00"))
                row = cursor.fetchone()
                longest = dict(row) if row else None

            max_day = max(daily.values()) if daily else 0
            rows_games = "".join(
                f"<tr><td>{html.escape(name)}</td>"
                f"<td class='num'>{format_duration(secs)}</td>"
                f"<td class='num'>{secs / 3600:.1f} ч</td>"
                f"<td class='num'>{(secs / total * 100) if total else 0:.1f}%</td></tr>"
                for name, secs in sorted(game_totals.items(), key=lambda kv: kv[1], reverse=True)
            ) or "<tr><td colspan='4'>Нет данных за период</td></tr>"

            rows_days = ""
            day = start_date
            while day <= end_date:
                secs = daily.get(day, 0)
                width = (secs / max_day * 100) if max_day else 0
                rows_days += (
                    f"<tr><td>{day.strftime('%d.%m.%Y')}</td>"
                    f"<td class='num'>{format_duration(secs)}</td>"
                    f"<td><div class='bar' style='width:{width:.1f}%'></div></td></tr>"
                )
                day += timedelta(days=1)

            longest_html = "—"
            if longest and longest.get('duration_seconds'):
                longest_html = (f"{html.escape(str(longest.get('display_name') or ''))} — "
                                f"{format_duration(longest['duration_seconds'])}")

            document = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>GameTimeTracker — отчёт {start_date} — {end_date}</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin: 0; padding: 32px; background: #0d0d0d; color: #e0e0e0;
         font-family: 'Segoe UI', Arial, sans-serif; }}
  h1 {{ color: #00d4ff; margin: 0 0 4px; font-size: 26px; }}
  h2 {{ color: #7b2fff; font-size: 18px; margin-top: 32px; }}
  .sub {{ color: #888; margin-bottom: 24px; }}
  .cards {{ display: flex; flex-wrap: wrap; gap: 16px; }}
  .card {{ flex: 1 1 160px; background: #1a1a2e; border: 1px solid #2a2a4e;
           border-radius: 12px; padding: 16px; }}
  .card .cap {{ color: #888; font-size: 12px; text-transform: uppercase; }}
  .card .val {{ color: #00d4ff; font-size: 22px; font-weight: 700; margin-top: 6px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
  th, td {{ padding: 8px 10px; border-bottom: 1px solid #2a2a4e; text-align: left; }}
  th {{ color: #7b2fff; font-size: 13px; }}
  td.num {{ text-align: right; font-family: Consolas, monospace; color: #00d4ff; }}
  .bar {{ height: 10px; min-width: 2px; border-radius: 5px;
          background: linear-gradient(90deg, #00d4ff, #7b2fff); }}
  footer {{ margin-top: 32px; color: #666; font-size: 12px; }}
</style>
</head>
<body>
  <h1>🎮 GameTimeTracker</h1>
  <div class="sub">Отчёт за период: {start_date.strftime('%d.%m.%Y')} — {end_date.strftime('%d.%m.%Y')}
    ({period_days} дн.){' · с архивом' if include_archived else ''}</div>
  <div class="cards">
    <div class="card"><div class="cap">Всего за период</div><div class="val">{format_duration(total)}</div></div>
    <div class="card"><div class="cap">Активных дней</div><div class="val">{active_days} из {period_days}</div></div>
    <div class="card"><div class="cap">Среднее в день</div><div class="val">{format_duration(total // period_days)}</div></div>
    <div class="card"><div class="cap">Самая долгая сессия</div><div class="val" style="font-size:15px">{longest_html}</div></div>
  </div>
  <h2>🏆 Игры за период</h2>
  <table>
    <tr><th>Игра</th><th class="num">Время</th><th class="num">Часы</th><th class="num">Доля</th></tr>
    {rows_games}
  </table>
  <h2>📅 Активность по дням</h2>
  <table>
    <tr><th>Дата</th><th class="num">Время</th><th>График</th></tr>
    {rows_days}
  </table>
  <footer>Отчёт сформирован {datetime.now().strftime('%d.%m.%Y %H:%M')} · GameTimeTracker</footer>
</body>
</html>
"""
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(document)
            return True
        except Exception as e:
            logger.exception("Ошибка экспорта HTML-отчёта: %s", e)
            return False

    def backup_database(self, target_path: str) -> None:
        """
        Создаёт резервную копию базы данных через SQLite Online Backup API.

        Args:
            target_path: путь к целевому файлу резервной копии
        """
        target_dir = os.path.dirname(target_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)

        with self.lock:
            backup_conn = sqlite3.connect(target_path)
            try:
                self.conn.backup(backup_conn)
            finally:
                backup_conn.close()


    def check_integrity(self, quick: bool = True) -> bool:
        """
        Проверяет целостность базы данных (PRAGMA quick_check / integrity_check).

        Выполняется при запуске приложения, чтобы вовремя заметить повреждение
        файла БД (например, после отключения электричества) и подсказать
        пользователю про резервные копии.

        Returns:
            True, если SQLite сообщает «ok».
        """
        pragma = "quick_check" if quick else "integrity_check"
        with self.lock:
            try:
                row = self.conn.execute(f"PRAGMA {pragma}").fetchone()
            except sqlite3.DatabaseError as e:
                logger.error("Проверка целостности БД не удалась: %s", e)
                return False
        return bool(row) and str(row[0]).strip().lower() == "ok"

    def create_rotating_backup(self, backup_dir: Optional[str] = None,
                               keep: int = 7) -> Optional[str]:
        """
        Создаёт автоматическую резервную копию базы и удаляет устаревшие копии.

        Args:
            backup_dir: каталог для копий (по умолчанию `data/backups`).
            keep: сколько последних копий хранить.

        Returns:
            Путь к созданной копии или None (для in-memory БД / при ошибке).
        """
        if self._is_memory:
            return None
        try:
            target_dir = backup_dir or os.path.join(
                os.path.dirname(self.db_path) or get_base_dir(), "backups"
            )
            os.makedirs(target_dir, exist_ok=True)
            filename = f"gametracker_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            target_path = os.path.join(target_dir, filename)
            self.backup_database(target_path)

            backups = sorted(
                (os.path.join(target_dir, name) for name in os.listdir(target_dir)
                 if name.startswith("gametracker_") and name.endswith(".db")),
                key=os.path.getmtime,
                reverse=True,
            )
            for stale in backups[max(int(keep), 1):]:
                try:
                    os.remove(stale)
                except OSError:
                    pass
            logger.info("Создана резервная копия БД: %s", target_path)
            return target_path
        except Exception as e:
            logger.exception("Ошибка создания резервной копии: %s", e)
            return None

    def close(self) -> None:
        """Закрывает соединение с БД"""
        with self.lock:
            if self.conn:
                self.conn.close()
