import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import customtkinter as ctk

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import Database
from settings import AppSettings
from tracker import GameTracker
from ui.main_window import MainWindow, NotificationsDialog
from ui.tab_games import AddNewGameDialog
from tray import SystemTray


class TestNotificationAndDialogBugs(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.settings = AppSettings(self.db)
        self.tracker = GameTracker(self.db, self.settings)

    def tearDown(self):
        self.tracker.stop()
        self.db.close()

    def test_bug1_tray_message_handlers_captures_balloon_click(self):
        """Проверяет, что custom_on_notify регистрируется в _message_handlers и обрабатывает клик (1029)."""
        clicked = []
        tray = SystemTray(
            icon_path="assets/icon.png",
            on_open=MagicMock(),
            on_settings=MagicMock(),
            on_exit=MagicMock(),
            on_notification_click=lambda: clicked.append(True)
        )

        mock_icon = MagicMock()
        orig_notify = MagicMock()
        orig_notify.__name__ = "_on_notify"
        mock_icon._on_notify = orig_notify
        # Эмулируем словарь _message_handlers pystray
        WM_NOTIFY = 0x40b
        mock_icon._message_handlers = {WM_NOTIFY: orig_notify}

        with patch('pystray.Icon', return_value=mock_icon):
            tray._run()

        # Проверяем, что в _message_handlers теперь установлен наш custom_on_notify (а не старый orig_notify)
        installed_handler = mock_icon._message_handlers[WM_NOTIFY]
        self.assertNotEqual(installed_handler, orig_notify)

        # Симулируем клик по системному уведомлению (lparam = 1029 / 0x0405)
        installed_handler(0, 1029)
        self.assertEqual(len(clicked), 1)

        # Симулируем клик с NOTIFYICON_VERSION_4 (LOWORD = 1029)
        installed_handler(0, (1 << 16) | 1029)
        self.assertEqual(len(clicked), 2)

    def test_bug1_open_detected_game_from_notification_syncs_db(self):
        """Проверяет, что при клике на уведомление окно обновляет список из БД и открывает добавление игры."""
        window = MainWindow(self.db, self.tracker, self.settings)
        window.withdraw()

        # Добавляем уведомление в БД (как это делает трекер)
        self.db.add_pending_notification("newgame.exe", "C:\\Games\\newgame.exe")

        window.show_window = MagicMock()
        window.prompt_add_new_game = MagicMock()

        window.open_detected_game_from_notification()

        window.show_window.assert_called_once()
        window.prompt_add_new_game.assert_called_once_with("newgame.exe", "C:\\Games\\newgame.exe")
        window.destroy()

    def test_bug2_notifications_dialog_has_transient_and_lift(self):
        """Проверяет, что NotificationsDialog при создании привязан transient к родителю и вызывает lift()."""
        window = MainWindow(self.db, self.tracker, self.settings)
        window.withdraw()

        with patch.object(NotificationsDialog, 'transient') as mock_transient, \
             patch.object(NotificationsDialog, 'lift') as mock_lift:
            dialog = NotificationsDialog(
                window, self.db, self.tracker,
                on_add_game=MagicMock(),
                on_remove_notification=MagicMock()
            )
            mock_transient.assert_called_once_with(window)
            self.assertTrue(mock_lift.called)
            dialog.destroy()

        window.destroy()

    def test_bug2_show_notifications_window_first_and_second_click(self):
        """Проверяет вызов окна уведомлений: первый клик создает и поднимает, второй клик поднимает существующее."""
        window = MainWindow(self.db, self.tracker, self.settings)
        window.withdraw()

        window.show_notifications_window()
        self.assertIsNotNone(window._notifications_window)
        first_dlg = window._notifications_window

        with patch.object(first_dlg, 'lift') as mock_lift, \
             patch.object(first_dlg, 'focus_force') as mock_focus:
            window.show_notifications_window()
            mock_lift.assert_called_once()
            mock_focus.assert_called_once()
            self.assertIs(window._notifications_window, first_dlg)

        first_dlg._on_close()
        self.assertIsNone(window._notifications_window)
        window.destroy()

    def test_add_new_game_dialog_has_transient_and_lift(self):
        """Проверяет, что AddNewGameDialog привязан к родителю через transient и поднимается на передний план."""
        window = MainWindow(self.db, self.tracker, self.settings)
        window.withdraw()

        with patch.object(AddNewGameDialog, 'transient') as mock_transient, \
             patch.object(AddNewGameDialog, 'lift') as mock_lift:
            dialog = AddNewGameDialog(
                window,
                exe_name="test.exe",
                exe_path=None,
                tracker=self.tracker,
                on_confirm=MagicMock()
            )
            mock_transient.assert_called_once_with(window)
            self.assertTrue(mock_lift.called)
            dialog.destroy()

        window.destroy()


if __name__ == '__main__':
    unittest.main()
