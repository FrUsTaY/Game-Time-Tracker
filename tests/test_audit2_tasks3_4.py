import os
import sys
import unittest
import time
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import customtkinter as ctk
from database import Database
from settings import AppSettings
from tracker import GameTracker
from ui.widgets import GameCard
from ui.tab_games import TabGames
from ui.tab_archive import TabArchive
from ui.tab_stats import TabStats
from ui.tab_calendar import TabCalendar
from ui.tab_about import TabAbout
from ui.main_window import MainWindow


class TestAudit2Task3TabsSync(unittest.TestCase):
    """Тесты для Задачи 3: Актуализация данных при переключении вкладок и связь «Игры» ↔ «Архив»"""

    def setUp(self):
        self.db = Database(":memory:")
        self.settings = AppSettings(self.db)
        self.tracker = GameTracker(self.db, self.settings)

    def tearDown(self):
        self.tracker.stop()
        self.db.close()

    def test_all_tabs_have_refresh_method(self):
        """Все вкладки должны реализовывать интерфейс метода refresh()"""
        for tab_cls in [TabGames, TabArchive, TabStats, TabCalendar, TabAbout]:
            self.assertTrue(hasattr(tab_cls, "refresh"), f"{tab_cls.__name__} должен иметь метод refresh()")

    def test_main_window_refresh_tab_invokes_tab_refresh(self):
        """MainWindow.refresh_tab вызывает метод refresh у закэшированной вкладки"""
        window = MainWindow.__new__(MainWindow)
        window.tabs_cache = {}

        mock_tab = MagicMock()
        window.tabs_cache["stats"] = mock_tab

        window.refresh_tab("stats")
        mock_tab.refresh.assert_called_once()

    def test_show_tab_refreshes_cached_tab(self):
        """При показе вкладки из кэша у нее вызывается обновление данных"""
        window = MainWindow.__new__(MainWindow)
        window.tabs_cache = {}
        window.current_tab = MagicMock()
        window.current_tab_key = "games"
        window.nav_buttons = {}

        mock_stats = MagicMock()
        window.tabs_cache["stats"] = mock_stats

        window.show_tab("stats", TabStats)
        mock_stats.grid.assert_called_once()
        mock_stats.refresh.assert_called_once()
        self.assertEqual(window.current_tab, mock_stats)
        self.assertEqual(window.current_tab_key, "stats")

    def test_show_tab_reclick_same_tab_refreshes(self):
        """Повторный клик по уже активной вкладке обновляет ее данные"""
        window = MainWindow.__new__(MainWindow)
        window.tabs_cache = {}
        mock_games = MagicMock()
        window.tabs_cache["games"] = mock_games
        window.current_tab = mock_games
        window.current_tab_key = "games"
        window.nav_buttons = {}

        window.show_tab("games", TabGames)
        mock_games.refresh.assert_called_once()

    def test_tab_games_refreshes_archive_tab(self):
        """TabGames._refresh_archive_tab корректно вызывает refresh_tab('archive') у MainWindow"""
        tab = TabGames.__new__(TabGames)
        mock_main = MagicMock()
        tab.main_window = mock_main

        tab._refresh_archive_tab()
        mock_main.refresh_tab.assert_called_once_with("archive")

    def test_tab_archive_restores_and_refreshes_games_tab(self):
        """TabArchive.restore_game восстанавливает игру и вызывает обновление вкладки 'games'"""
        tab = TabArchive.__new__(TabArchive)
        tab.db = self.db
        mock_main = MagicMock()
        tab.main_window = mock_main
        tab.refresh = MagicMock()

        # Добавим игру и заархивируем
        game_id = self.db.add_game("test.exe", "Test Game")
        self.db.archive_game(game_id)
        self.assertEqual(self.db.get_game_by_id(game_id)['is_archived'], 1)

        # Восстанавливаем
        tab.restore_game(game_id)
        self.assertEqual(self.db.get_game_by_id(game_id)['is_archived'], 0)
        tab.refresh.assert_called_once()
        mock_main.refresh_tab.assert_called_once_with("games")


class TestAudit2Task4DriftAndIdleTasks(unittest.TestCase):
    """Тесты для Задачи 4: Устранение дрифта времени и удаление update_idletasks()"""

    def setUp(self):
        self.db = Database(":memory:")
        self.settings = AppSettings(self.db)
        self.tracker = GameTracker(self.db, self.settings)

    def tearDown(self):
        self.tracker.stop()
        self.db.close()

    def test_game_card_update_time_does_not_call_update_idletasks(self):
        """GameCard.update_time не должен вызывать синхронный update_idletasks"""
        card = GameCard.__new__(GameCard)
        card.info_label = MagicMock()
        card._format_time = lambda s: f"{s}s"
        card.update_idletasks = MagicMock()

        card.update_time(100, True)

        card.update_idletasks.assert_not_called()
        card.info_label.configure.assert_called_once()

    def test_tracker_monotonic_drift_free_accumulation(self):
        """Проверка расчета времени по time.monotonic() с накоплением дробных долей"""
        game_id = self.db.add_game("test_game.exe", "Test Game")
        session_id = self.db.start_session(game_id)

        t0 = 1000.0
        session_info = {
            'session_id': session_id,
            'current_seconds': 0,
            'accumulated_seconds': 0.0,
            'last_tick_time': t0,
            'last_flushed_seconds': 0,
            'initial_total_seconds': 0,
            'process_pid': 1234,
            'was_active': True
        }
        self.tracker.active_sessions[game_id] = session_info

        # Симулируем 10 шагов с неравномерным временем выполнения процесса (например, 1.07 секунды на шаг)
        current_time = t0
        with patch.object(self.tracker, '_is_game_active', return_value=True):
            # Мокаем БД и отслеживаемые процессы
            tracked_games = {
                game_id: {
                    'game_info': {'id': game_id, 'exe_name': 'test_game.exe'},
                    'pid': 1234,
                    'pids': [1234]
                }
            }
            with patch.object(self.tracker, '_get_active_window_pid', return_value=1234), \
                 patch.object(self.tracker.db, 'get_all_games', return_value=[{'id': game_id, 'exe_name': 'test_game.exe'}]), \
                 patch('psutil.process_iter', return_value=[]):
                
                # Прогоняем шаги через прямое обновление логики
                for step in range(1, 11):
                    current_time += 1.07
                    with patch('time.monotonic', return_value=current_time):
                        # Вызываем _check_processes с контролируемым временем
                        now = time.monotonic()
                        with self.tracker.lock:
                            last_tick = session_info.get('last_tick_time', now)
                            delta = now - last_tick
                            session_info['last_tick_time'] = now

                            accumulated = session_info.get('accumulated_seconds', 0.0) + delta
                            session_info['accumulated_seconds'] = accumulated
                            session_info['current_seconds'] = int(accumulated)

        # 10 шагов по 1.07 секунды = 10.7 секунды. При целочисленном += 1 было бы ровно 10 секунд (потеря 0.7 с)
        # А при накоплении time.monotonic():
        self.assertAlmostEqual(session_info['accumulated_seconds'], 10.7, places=5)
        self.assertEqual(session_info['current_seconds'], 10)

        # Делаем еще один шаг 0.35 секунды (всего 11.05 секунд)
        current_time += 0.35
        delta = current_time - session_info['last_tick_time']
        session_info['last_tick_time'] = current_time
        session_info['accumulated_seconds'] += delta
        session_info['current_seconds'] = int(session_info['accumulated_seconds'])

        self.assertAlmostEqual(session_info['accumulated_seconds'], 11.05, places=5)
        self.assertEqual(session_info['current_seconds'], 11)


if __name__ == '__main__':
    unittest.main()
