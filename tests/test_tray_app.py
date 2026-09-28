import unittest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import App
from tray import SystemTray


class TestTrayAndAppExit(unittest.TestCase):
    """Тесты потокобезопасности вызовов из трея и корректности выхода из приложения"""

    def setUp(self):
        # Создаем экземпляр App без вызова __init__
        self.app = App.__new__(App)
        self.app._is_exiting = False
        self.app.window = MagicMock()
        self.app.tracker = MagicMock()
        self.app.tray = MagicMock()
        self.app.db = MagicMock()

    def test_show_window_dispatches_via_after(self):
        """show_window перенаправляет вызов в главный поток через window.after"""
        self.app.show_window()
        self.app.window.after.assert_called_once_with(0, self.app.window.show_window)

    def test_open_settings_dispatches_via_after(self):
        """open_settings перенаправляет вызов в главный поток через window.after"""
        self.app.open_settings()
        self.app.window.after.assert_called_once_with(0, self.app.window.open_settings)

    def test_exit_app_dispatches_via_after(self):
        """exit_app перенаправляет вызов _perform_exit в главный поток через window.after"""
        self.app.exit_app()
        self.app.window.after.assert_called_once_with(0, self.app._perform_exit)

    def test_perform_exit_sequence(self):
        """_perform_exit останавливает трекер, трей, БД, закрывает окно и вызывает sys.exit"""
        order = []
        self.app.tracker.stop.side_effect = lambda: order.append('tracker')
        self.app.tray.stop.side_effect = lambda: order.append('tray')
        self.app.db.close.side_effect = lambda: order.append('db')
        self.app.window.quit.side_effect = lambda: order.append('quit')
        self.app.window.destroy.side_effect = lambda: order.append('destroy')

        with patch('sys.exit') as mock_exit:
            mock_exit.side_effect = lambda code: order.append(f'exit_{code}')
            self.app._perform_exit()

            # Проверяем строгий порядок завершения
            expected_order = ['tracker', 'tray', 'db', 'quit', 'destroy', 'exit_0']
            self.assertEqual(order, expected_order)
            self.assertTrue(self.app._is_exiting)

    def test_perform_exit_idempotent(self):
        """Повторный вызов _perform_exit не выполняет закрытие повторно"""
        self.app._is_exiting = True
        with patch('sys.exit') as mock_exit:
            self.app._perform_exit()
            self.app.tracker.stop.assert_not_called()
            self.app.tray.stop.assert_not_called()
            self.app.db.close.assert_not_called()
            mock_exit.assert_not_called()

    def test_tray_menu_callbacks_accept_optional_args(self):
        """Колбэки трея безопасно вызываются как с аргументами pystray (icon, item), так и без них"""
        mock_open = MagicMock()
        mock_settings = MagicMock()
        mock_exit = MagicMock()

        tray = SystemTray.__new__(SystemTray)
        tray.on_open = mock_open
        tray.on_settings = mock_settings
        tray.on_exit = mock_exit

        # Имитируем вызов pystray с двумя аргументами (icon, item)
        dummy_icon = MagicMock()
        dummy_item = MagicMock()

        tray._on_open(dummy_icon, dummy_item)
        mock_open.assert_called_once_with()

        tray._on_settings(dummy_icon, dummy_item)
        mock_settings.assert_called_once_with()

        tray._on_exit(dummy_icon, dummy_item)
        mock_exit.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
