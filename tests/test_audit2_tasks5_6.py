import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import Database
from settings import AppSettings
from tracker import GameTracker
from ui.tab_about import TabAbout, APP_VERSION


class TestAudit2Task5Notifications(unittest.TestCase):
    """Тесты для Задачи 5: Реализация уведомлений о долгих сессиях и новых играх"""

    def setUp(self):
        self.db = Database(":memory:")
        self.settings = AppSettings(self.db)
        self.mock_tray = MagicMock()
        self.mock_on_notify = MagicMock()
        self.tracker = GameTracker(
            self.db,
            self.settings,
            tray=self.mock_tray,
            on_notification=self.mock_on_notify
        )

    def tearDown(self):
        self.tracker.stop()
        self.db.close()

    def test_tracker_notify_calls_tray_and_callback(self):
        """Метод notify корректно передает уведомления в tray и on_notification"""
        self.tracker.notify("Заголовок", "Сообщение")
        self.mock_on_notify.assert_called_once_with("Заголовок", "Сообщение")
        self.mock_tray.show_notification.assert_called_once_with("Заголовок", "Сообщение")

    def test_new_game_notification_sent_when_exe_not_in_library(self):
        """При обнаружении запущенного процесса, которого нет в БД, отправляется уведомление"""
        self.settings.notify_new_game = True

        mock_proc = MagicMock()
        mock_proc.info = {'pid': 9999, 'name': 'SuperNewGame.exe', 'exe': 'C:\\Games\\SuperNewGame.exe'}

        with patch('psutil.process_iter', return_value=[mock_proc]), \
             patch.object(self.tracker, '_get_active_window_pid', return_value=None):
            self.tracker._check_processes()

        self.mock_tray.show_notification.assert_called_once()
        args = self.mock_tray.show_notification.call_args[0]
        self.assertIn("supernewgame.exe", args[1].lower())
        self.mock_on_notify.assert_called_once()

    def test_new_game_notification_not_sent_when_disabled(self):
        """Если настройка notify_new_game отключена, уведомление не отправляется"""
        self.settings.notify_new_game = False

        mock_proc = MagicMock()
        mock_proc.info = {'pid': 9999, 'name': 'SuperNewGame.exe', 'exe': 'C:\\Games\\SuperNewGame.exe'}

        with patch('psutil.process_iter', return_value=[mock_proc]), \
             patch.object(self.tracker, '_get_active_window_pid', return_value=None):
            self.tracker._check_processes()

        self.mock_tray.show_notification.assert_not_called()
        self.mock_on_notify.assert_not_called()

    def test_new_game_notification_not_sent_if_game_already_in_library(self):
        """Если .exe уже зарегистрирован в базе данных, уведомление о новой игре не отправляется"""
        self.settings.notify_new_game = True
        self.db.add_game("existinggame.exe", "Existing Game")

        mock_proc = MagicMock()
        mock_proc.info = {'pid': 8888, 'name': 'existinggame.exe', 'exe': 'C:\\Games\\existinggame.exe'}

        with patch('psutil.process_iter', return_value=[mock_proc]), \
             patch.object(self.tracker, '_get_active_window_pid', return_value=None):
            self.tracker._check_processes()

        self.mock_tray.show_notification.assert_not_called()
        self.mock_on_notify.assert_not_called()

    def test_new_game_notification_not_spammed_on_subsequent_ticks(self):
        """Уведомление для одного и того же нового .exe отправляется только один раз"""
        self.settings.notify_new_game = True

        mock_proc = MagicMock()
        mock_proc.info = {'pid': 9999, 'name': 'AnotherNewGame.exe', 'exe': 'C:\\Games\\AnotherNewGame.exe'}

        with patch('psutil.process_iter', return_value=[mock_proc]), \
             patch.object(self.tracker, '_get_active_window_pid', return_value=None):
            # Первый тик — обнаружение
            self.tracker._check_processes()
            self.assertEqual(self.mock_tray.show_notification.call_count, 1)

            # Второй тик — игра все еще запущена
            self.tracker._check_processes()
            self.assertEqual(self.mock_tray.show_notification.call_count, 1)

    def test_long_session_notification_sent_when_threshold_reached(self):
        """При превышении порога времени сессии отправляется предупреждение о перерыве"""
        self.settings.notify_long_session = True
        self.settings.long_session_minutes = 60
        game_id = self.db.add_game("rpg.exe", "Epic RPG")

        session_id = self.db.start_session(game_id)
        session_info = {
            'session_id': session_id,
            'current_seconds': 3599,
            'accumulated_seconds': 3599.0,
            'last_tick_time': 1000.0,
            'last_flushed_seconds': 0,
            'initial_total_seconds': 0,
            'process_pid': 1234,
            'was_active': True,
            'long_session_notified': False
        }
        self.tracker.active_sessions[game_id] = session_info

        mock_proc = MagicMock()
        mock_proc.info = {'pid': 1234, 'name': 'rpg.exe', 'exe': 'C:\\Games\\rpg.exe'}

        with patch('psutil.process_iter', return_value=[mock_proc]), \
             patch.object(self.tracker, '_is_game_active', return_value=True), \
             patch('time.monotonic', return_value=1001.0):
            # Шаг времени +1 секунда -> current_seconds = 3600 (порог 60 мин достигнут)
            self.tracker._check_processes()

        self.assertTrue(session_info['long_session_notified'])
        self.mock_tray.show_notification.assert_called_once()
        title, msg = self.mock_tray.show_notification.call_args[0]
        self.assertEqual(title, "GameTimeTracker")
        self.assertEqual(msg, "Вы играете уже 60 минут! Пора сделать перерыв")

    def test_long_session_notification_only_sent_once_per_session(self):
        """Предупреждение о долгой сессии отправляется ровно один раз в рамках сессии"""
        self.settings.notify_long_session = True
        self.settings.long_session_minutes = 60
        game_id = self.db.add_game("rpg2.exe", "Epic RPG 2")

        session_id = self.db.start_session(game_id)
        session_info = {
            'session_id': session_id,
            'current_seconds': 3605,
            'accumulated_seconds': 3605.0,
            'last_tick_time': 1000.0,
            'last_flushed_seconds': 0,
            'initial_total_seconds': 0,
            'process_pid': 1234,
            'was_active': True,
            'long_session_notified': True  # Уже отправлялось
        }
        self.tracker.active_sessions[game_id] = session_info

        mock_proc = MagicMock()
        mock_proc.info = {'pid': 1234, 'name': 'rpg2.exe', 'exe': 'C:\\Games\\rpg2.exe'}

        with patch('psutil.process_iter', return_value=[mock_proc]), \
             patch.object(self.tracker, '_is_game_active', return_value=True), \
             patch('time.monotonic', return_value=1001.0):
            self.tracker._check_processes()

        self.mock_tray.show_notification.assert_not_called()

    def test_long_session_notification_disabled_in_settings(self):
        """Если notify_long_session отключена в настройках, напоминание не отправляется"""
        self.settings.notify_long_session = False
        self.settings.long_session_minutes = 30
        game_id = self.db.add_game("rpg3.exe", "Epic RPG 3")

        session_id = self.db.start_session(game_id)
        session_info = {
            'session_id': session_id,
            'current_seconds': 1800,
            'accumulated_seconds': 1800.0,
            'last_tick_time': 1000.0,
            'last_flushed_seconds': 0,
            'initial_total_seconds': 0,
            'process_pid': 1234,
            'was_active': True,
            'long_session_notified': False
        }
        self.tracker.active_sessions[game_id] = session_info

        mock_proc = MagicMock()
        mock_proc.info = {'pid': 1234, 'name': 'rpg3.exe', 'exe': 'C:\\Games\\rpg3.exe'}

        with patch('psutil.process_iter', return_value=[mock_proc]), \
             patch.object(self.tracker, '_is_game_active', return_value=True), \
             patch('time.monotonic', return_value=1001.0):
            self.tracker._check_processes()

        self.mock_tray.show_notification.assert_not_called()
        self.assertFalse(session_info['long_session_notified'])


class TestAudit2Task6SpecAndVersion(unittest.TestCase):
    """Тесты для Задачи 6: Исправление путей в .spec и синхронизация версий в TabAbout"""

    def test_spec_file_has_relative_icon_path(self):
        """В GameTimeTracker.spec путь к иконке должен быть относительным ('assets/app.ico')"""
        spec_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'GameTimeTracker.spec'))
        self.assertTrue(os.path.exists(spec_path), "GameTimeTracker.spec должен существовать")

        with open(spec_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn("icon=['assets/app.ico']", content)
        self.assertNotIn("C:/Users", content)
        self.assertNotIn("C:\\Users", content)

    def test_tab_about_version_constant_and_check_updates(self):
        """TabAbout использует константу актуальной версии v1.1.1 в UI и диалоге обновлений"""
        self.assertEqual(APP_VERSION, "v1.1.1")
        self.assertEqual(TabAbout.APP_VERSION, "v1.1.1")

        tab = TabAbout.__new__(TabAbout)
        with patch('tkinter.messagebox.showinfo') as mock_info:
            tab.check_updates()
            mock_info.assert_called_once()
            title, msg = mock_info.call_args[0]
            self.assertEqual(title, "Проверка обновлений")
            self.assertIn("v1.1.1", msg)
            self.assertNotIn("v1.0.0", msg)


if __name__ == '__main__':
    unittest.main()
