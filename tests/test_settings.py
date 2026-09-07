import sys
import unittest
from unittest.mock import MagicMock, patch

# Мокаем winreg до импорта settings, чтобы модуль мог загрузиться на Linux (где winreg отсутствует)
sys.modules['winreg'] = MagicMock()

import settings
from settings import AppSettings

class TestAppSettings(unittest.TestCase):

    def setUp(self):
        # Создаем мок базы данных для каждого теста
        self.mock_db = MagicMock()
        self.app_settings = AppSettings(db=self.mock_db)

    # --- Тесты внутренних методов (_get_bool, _set_bool, _get_int, _set_int) ---

    def test_get_bool_true(self):
        self.mock_db.get_setting.return_value = 'true'
        result = self.app_settings._get_bool('some_key', default=False)
        self.assertTrue(result)
        self.mock_db.get_setting.assert_called_once_with('some_key')

    def test_get_bool_false(self):
        self.mock_db.get_setting.return_value = 'false'
        result = self.app_settings._get_bool('some_key', default=True)
        self.assertFalse(result)

    def test_get_bool_default(self):
        self.mock_db.get_setting.return_value = None
        result = self.app_settings._get_bool('missing_key', default=True)
        self.assertTrue(result)

    def test_set_bool(self):
        self.app_settings._set_bool('some_key', True)
        self.mock_db.set_setting.assert_called_once_with('some_key', 'true')
        self.assertEqual(self.app_settings._cache['some_key'], True)

        self.mock_db.set_setting.reset_mock()
        self.app_settings._set_bool('other_key', False)
        self.mock_db.set_setting.assert_called_once_with('other_key', 'false')
        self.assertEqual(self.app_settings._cache['other_key'], False)

    def test_get_int_valid(self):
        self.mock_db.get_setting.return_value = '42'
        result = self.app_settings._get_int('some_key', default=10)
        self.assertEqual(result, 42)
        self.mock_db.get_setting.assert_called_once_with('some_key')

    def test_get_int_invalid_returns_default(self):
        self.mock_db.get_setting.return_value = 'not_a_number'
        result = self.app_settings._get_int('some_key', default=10)
        self.assertEqual(result, 10)

    def test_get_int_missing_returns_default(self):
        self.mock_db.get_setting.return_value = None
        result = self.app_settings._get_int('missing_key', default=10)
        self.assertEqual(result, 10)

    def test_set_int(self):
        self.app_settings._set_int('some_key', 42)
        self.mock_db.set_setting.assert_called_once_with('some_key', '42')
        self.assertEqual(self.app_settings._cache['some_key'], 42)

    # --- Тесты для методов автозапуска (mocking winreg) ---

    @patch('settings.winreg')
    @patch('settings.sys')
    def test_enable_autostart_frozen(self, mock_sys, mock_winreg):
        mock_sys.frozen = True
        mock_sys.executable = 'C:\\path\\to\\app.exe'

        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key

        self.app_settings.enable_autostart()

        mock_winreg.OpenKey.assert_called_once()
        mock_winreg.SetValueEx.assert_called_once_with(
            mock_key, "GameTimeTracker", 0, mock_winreg.REG_SZ, 'C:\\path\\to\\app.exe'
        )
        mock_winreg.CloseKey.assert_called_once_with(mock_key)
        self.mock_db.set_setting.assert_called_with('autostart', 'true')

    @patch('settings.winreg')
    @patch('settings.sys')
    @patch('settings.os.path.abspath')
    def test_enable_autostart_script(self, mock_abspath, mock_sys, mock_winreg):
        mock_sys.frozen = False
        mock_sys.executable = 'C:\\python\\python.exe'
        mock_abspath.return_value = 'C:\\path\\to\\main.py'

        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key

        self.app_settings.enable_autostart()

        mock_winreg.OpenKey.assert_called_once()
        expected_path = f'"C:\\python\\python.exe" "C:\\path\\to\\main.py"'
        mock_winreg.SetValueEx.assert_called_once_with(
            mock_key, "GameTimeTracker", 0, mock_winreg.REG_SZ, expected_path
        )
        mock_winreg.CloseKey.assert_called_once_with(mock_key)
        self.mock_db.set_setting.assert_called_with('autostart', 'true')

    @patch('settings.winreg')
    def test_disable_autostart(self, mock_winreg):
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key

        self.app_settings.disable_autostart()

        mock_winreg.OpenKey.assert_called_once()
        mock_winreg.DeleteValue.assert_called_once_with(mock_key, "GameTimeTracker")
        mock_winreg.CloseKey.assert_called_once_with(mock_key)
        self.mock_db.set_setting.assert_called_with('autostart', 'false')

    @patch('settings.winreg')
    @patch('builtins.print')
    def test_enable_autostart_exception(self, mock_print, mock_winreg):
        mock_winreg.OpenKey.side_effect = Exception("Some error")
        self.app_settings.enable_autostart()
        mock_print.assert_called_once()
        self.assertIn("Ошибка включения автозапуска:", mock_print.call_args[0][0])
        self.mock_db.set_setting.assert_not_called()

    @patch('settings.winreg')
    def test_disable_autostart_file_not_found(self, mock_winreg):
        # Если ключа нет, DeleteValue или OpenKey могут выкинуть FileNotFoundError
        mock_winreg.OpenKey.side_effect = FileNotFoundError()

        # Не должно выбрасывать исключение
        self.app_settings.disable_autostart()
        mock_winreg.OpenKey.assert_called_once()
        # В случае ошибки удаления настройки в БД не обновляются
        self.mock_db.set_setting.assert_not_called()

    @patch('settings.winreg')
    @patch('builtins.print')
    def test_disable_autostart_exception(self, mock_print, mock_winreg):
        mock_winreg.OpenKey.side_effect = Exception("Some error")
        self.app_settings.disable_autostart()
        mock_print.assert_called_once()
        self.assertIn("Ошибка отключения автозапуска:", mock_print.call_args[0][0])
        self.mock_db.set_setting.assert_not_called()

    @patch('settings.winreg')
    def test_is_autostart_enabled_true(self, mock_winreg):
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key

        result = self.app_settings.is_autostart_enabled()

        self.assertTrue(result)
        mock_winreg.OpenKey.assert_called_once()
        mock_winreg.QueryValueEx.assert_called_once_with(mock_key, "GameTimeTracker")
        mock_winreg.CloseKey.assert_called_once_with(mock_key)

    @patch('settings.winreg')
    def test_is_autostart_enabled_false(self, mock_winreg):
        mock_winreg.OpenKey.side_effect = FileNotFoundError()

        result = self.app_settings.is_autostart_enabled()

        self.assertFalse(result)

    @patch('settings.winreg')
    def test_is_autostart_enabled_exception(self, mock_winreg):
        mock_winreg.OpenKey.side_effect = Exception("Some error")

        result = self.app_settings.is_autostart_enabled()

        self.assertFalse(result)

    # --- Тесты для свойств (properties) ---

    def test_property_autostart_getter(self):
        self.mock_db.get_setting.return_value = 'true'
        self.assertTrue(self.app_settings.autostart)
        self.mock_db.get_setting.assert_called_with('autostart')

    @patch.object(AppSettings, 'enable_autostart')
    @patch.object(AppSettings, 'disable_autostart')
    def test_property_autostart_setter(self, mock_disable, mock_enable):
        self.app_settings.autostart = True
        mock_enable.assert_called_once()
        mock_disable.assert_not_called()

        mock_enable.reset_mock()

        self.app_settings.autostart = False
        mock_disable.assert_called_once()
        mock_enable.assert_not_called()

    def test_property_minimize_to_tray_on_start(self):
        self.mock_db.get_setting.return_value = 'true'
        self.assertTrue(self.app_settings.minimize_to_tray_on_start)

        self.app_settings.minimize_to_tray_on_start = False
        self.mock_db.set_setting.assert_called_with('minimize_to_tray_on_start', 'false')

    def test_property_track_only_active_window(self):
        self.mock_db.get_setting.return_value = 'false'
        self.assertFalse(self.app_settings.track_only_active_window)

        self.app_settings.track_only_active_window = True
        self.mock_db.set_setting.assert_called_with('track_only_active_window', 'true')

    def test_property_notify_new_game(self):
        self.mock_db.get_setting.return_value = 'true'
        self.assertTrue(self.app_settings.notify_new_game)

        self.app_settings.notify_new_game = False
        self.mock_db.set_setting.assert_called_with('notify_new_game', 'false')

    def test_property_notify_long_session(self):
        self.mock_db.get_setting.return_value = 'true'
        self.assertTrue(self.app_settings.notify_long_session)

        self.app_settings.notify_long_session = False
        self.mock_db.set_setting.assert_called_with('notify_long_session', 'false')

    def test_property_long_session_minutes(self):
        self.mock_db.get_setting.return_value = '90'
        self.assertEqual(self.app_settings.long_session_minutes, 90)

        self.app_settings.long_session_minutes = 120
        self.mock_db.set_setting.assert_called_with('long_session_minutes', '120')

    def test_property_long_session_minutes_min_value(self):
        # Если устанавливаем значение меньше 1, должно установиться 1
        self.app_settings.long_session_minutes = 0
        self.mock_db.set_setting.assert_called_with('long_session_minutes', '1')

        self.app_settings.long_session_minutes = -5
        self.mock_db.set_setting.assert_called_with('long_session_minutes', '1')

    def test_save_all(self):
        # Метод ничего не делает, но мы убеждаемся, что он не падает
        self.app_settings.save_all()

if __name__ == '__main__':
    unittest.main()
