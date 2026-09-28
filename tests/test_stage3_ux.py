"""
tests/test_stage3_ux.py — тесты для UX-улучшений Этапа 3 (Задачи 11–15).
"""

import unittest
from unittest.mock import MagicMock, patch
import customtkinter as ctk
from datetime import date
import os
import tempfile

from database import Database
from settings import AppSettings
from tracker import GameTracker
from ui.tab_calendar import TabCalendar, MONTHS_GENITIVE_RU
from ui.tab_games import TabGames
from app import App


class TestStage3UX(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ctk.set_appearance_mode("dark")
        cls.root = ctk.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.db = Database(self.temp_db_path)
        self.settings = AppSettings(self.db)

    def tearDown(self):
        try:
            if os.path.exists(self.temp_db_path):
                os.remove(self.temp_db_path)
        except Exception:
            pass

    def test_task11_calendar_genitive_month_formatting(self):
        """Задача 11: Месяц в деталях дня отображается в родительном падеже."""
        cal = TabCalendar(self.root, self.db)
        test_date = date(2026, 9, 28)
        cal.show_day_details(test_date)
        self.assertEqual(cal.details_title.cget("text"), "28 сентября 2026 г.")

        test_march = date(2026, 3, 15)
        cal.show_day_details(test_march)
        self.assertEqual(cal.details_title.cget("text"), "15 марта 2026 г.")
        cal.destroy()

    def test_task15_calendar_selection_border_highlight(self):
        """Задача 15: Выбранный день в сетке календаря выделяется рамкой #00d4ff."""
        cal = TabCalendar(self.root, self.db)
        cal.current_year = 2026
        cal.current_month = 9
        cal.load_month_data()

        d1 = date(2026, 9, 10)
        d2 = date(2026, 9, 20)

        # Кликаем на 10-е число
        cal.show_day_details(d1)
        self.assertEqual(cal.selected_date, d1)
        cell1, _ = cal.day_cells[d1]
        self.assertEqual(cell1.cget("border_color"), "#00d4ff")
        self.assertEqual(cell1.cget("border_width"), 2)

        # Кликаем на 20-е число — рамка у d1 должна сброситься, а у d2 появиться
        cal.show_day_details(d2)
        self.assertEqual(cal.selected_date, d2)
        cell2, _ = cal.day_cells[d2]
        self.assertEqual(cell2.cget("border_color"), "#00d4ff")
        self.assertNotEqual(cell1.cget("border_color"), "#00d4ff")
        cal.destroy()

    def test_task12_inactive_window_does_not_show_playing_status(self):
        """Задача 12: Неактивное окно игры не подсвечивается как 'Сейчас играю'."""
        self.settings.track_only_active_window = True
        tracker = GameTracker(self.db, self.settings, None)

        gid = self.db.add_game("game.exe", "Game", None)
        tracker.active_sessions[gid] = {
            'process_pid': 1234,
            'was_active': False,
            'current_seconds': 50,
            'initial_total_seconds': 0
        }

        # Когда окно не активно, is_game_currently_playing возвращает False
        with patch.object(tracker, '_get_active_window_pid', return_value=9999):
            self.assertFalse(tracker.is_game_currently_playing(gid))

        # И если was_active было True, но сейчас активен GameTimeTracker (PID 9999 != 1234)
        tracker.active_sessions[gid]['was_active'] = True
        with patch.object(tracker, '_get_active_window_pid', return_value=9999):
            self.assertFalse(tracker.is_game_currently_playing(gid))

        # А если активен PID игры (1234), возвращает True
        with patch.object(tracker, '_get_active_window_pid', return_value=1234):
            self.assertTrue(tracker.is_game_currently_playing(gid))

    def test_task13_on_window_close_notification_shown_only_once(self):
        """Задача 13: Уведомление о сворачивании в трей показывается только 1 раз за сессию."""
        tray_mock = MagicMock()
        window_mock = MagicMock()

        # Создаём минимальный объект приложения
        app_mock = MagicMock(spec=App)
        app_mock.tray = tray_mock
        app_mock.window = window_mock
        app_mock._background_notified = False

        # Первый вызов — уведомление отправляется
        App.on_window_close(app_mock)
        tray_mock.show_notification.assert_called_once_with(
            "GameTimeTracker",
            "Приложение продолжает работать в фоне"
        )
        self.assertTrue(app_mock._background_notified)
        window_mock.hide_to_tray.assert_called_once()

        # Второй и третий вызов — уведомление НЕ отправляется повторно
        App.on_window_close(app_mock)
        App.on_window_close(app_mock)
        self.assertEqual(tray_mock.show_notification.call_count, 1)

    def test_task14_prompt_and_unarchive_game_when_adding_archived(self):
        """Задача 14: При добавлении архивной игры предлагается разархивировать её."""
        gid = self.db.add_game("skyrim.exe", "Skyrim", None)
        self.db.archive_game(gid)
        self.assertTrue(self.db.get_game_by_id(gid)['is_archived'])

        games_tab = TabGames(self.root, self.db, None, self.settings)

        # Пользователь соглашается разархивировать
        with patch('tkinter.messagebox.askyesno', return_value=True), \
             patch('tkinter.messagebox.showinfo'):
            result = games_tab._add_game_by_name("skyrim.exe", "Skyrim", None, silent=False)
            self.assertTrue(result)
            self.assertFalse(self.db.get_game_by_id(gid)['is_archived'])

        # Снова отправляем в архив и проверяем отказ
        self.db.archive_game(gid)
        with patch('tkinter.messagebox.askyesno', return_value=False), \
             patch('tkinter.messagebox.showinfo'):
            result = games_tab._add_game_by_name("skyrim.exe", "Skyrim", None, silent=False)
            self.assertFalse(result)
            self.assertTrue(self.db.get_game_by_id(gid)['is_archived'])

        games_tab.destroy()


if __name__ == '__main__':
    unittest.main()
