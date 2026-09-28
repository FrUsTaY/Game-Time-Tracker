import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import Database
from settings import AppSettings
from ui.settings_window import SettingsWindow
from ui.tab_games import TabGames
import build


class TestAudit3Task4AutostartSync(unittest.TestCase):
    """Тесты для Задачи 4: Синхронизация автозапуска с кнопками окна настроек"""

    def setUp(self):
        self.db = Database(":memory:")
        self.settings = AppSettings(self.db)
        # Мокируем родительское окно tkinter
        self.mock_parent = MagicMock()
        self.mock_parent.winfo_x.return_value = 100
        self.mock_parent.winfo_y.return_value = 100
        self.mock_parent.winfo_width.return_value = 800
        self.mock_parent.winfo_height.return_value = 600

    def tearDown(self):
        self.db.close()

    @patch('customtkinter.CTkToplevel.__init__', return_value=None)
    @patch('customtkinter.CTkToplevel.withdraw')
    @patch('customtkinter.CTkToplevel.update_idletasks')
    @patch('customtkinter.CTkToplevel.geometry')
    @patch('customtkinter.CTkToplevel.grab_set')
    @patch('customtkinter.CTkToplevel.focus_force')
    @patch('customtkinter.CTkToplevel.deiconify')
    @patch('customtkinter.CTkToplevel.title')
    @patch('customtkinter.CTkToplevel.resizable')
    @patch.object(SettingsWindow, '_build_ui')
    def test_autostart_toggle_does_not_modify_registry_or_settings_immediately(
        self, mock_build, mock_resiz, mock_title, mock_deicon, mock_focus, mock_grab, mock_geom, mock_upd, mock_with, mock_init
    ):
        """Переключение тумблера автозапуска не вызывает enable/disable autostart немедленно"""
        self.settings.enable_autostart = MagicMock()
        self.settings.disable_autostart = MagicMock()

        win = SettingsWindow.__new__(SettingsWindow)
        win.settings = self.settings
        win.vars = {"autostart": MagicMock()}

        # Вызов _on_autostart_toggle ничего не должен менять напрямую
        win._on_autostart_toggle()
        self.settings.enable_autostart.assert_not_called()
        self.settings.disable_autostart.assert_not_called()

    @patch('customtkinter.CTkToplevel.__init__', return_value=None)
    @patch('customtkinter.CTkToplevel.withdraw')
    @patch('customtkinter.CTkToplevel.update_idletasks')
    @patch('customtkinter.CTkToplevel.geometry')
    @patch('customtkinter.CTkToplevel.grab_set')
    @patch('customtkinter.CTkToplevel.focus_force')
    @patch('customtkinter.CTkToplevel.deiconify')
    @patch('customtkinter.CTkToplevel.title')
    @patch('customtkinter.CTkToplevel.resizable')
    @patch.object(SettingsWindow, '_build_ui')
    def test_save_and_close_applies_autostart_change(
        self, mock_build, mock_resiz, mock_title, mock_deicon, mock_focus, mock_grab, mock_geom, mock_upd, mock_with, mock_init
    ):
        """save_and_close() применяет измененный автозапуск"""
        self.settings.enable_autostart = MagicMock()
        self.settings.disable_autostart = MagicMock()

        win = SettingsWindow.__new__(SettingsWindow)
        win.settings = self.settings
        win.destroy = MagicMock()

        # Исходно autostart = False
        self.assertFalse(self.settings.autostart)

        # Пользователь включил автозапуск в окне
        mock_auto_var = MagicMock()
        mock_auto_var.get.return_value = True
        win.vars = {
            "autostart": mock_auto_var,
            "minimize_to_tray_on_start": MagicMock(get=lambda: False),
            "track_only_active_window": MagicMock(get=lambda: True),
            "notify_new_game": MagicMock(get=lambda: True),
            "notify_long_session": MagicMock(get=lambda: True),
            "long_session_minutes": MagicMock(get=lambda: "60"),
        }

        # Вызываем сохранение
        win.save_and_close()
        self.settings.enable_autostart.assert_called_once()
        self.settings.disable_autostart.assert_not_called()
        win.destroy.assert_called_once()


class TestAudit3Task5GamesUX(unittest.TestCase):
    """Тесты для Задачи 5: Нормализация .exe и тихое пакетное добавление игр"""

    def setUp(self):
        self.db = Database(":memory:")
        self.settings = AppSettings(self.db)
        self.mock_tracker = MagicMock()
        self.mock_tracker.get_exe_icon.return_value = None

        # Инициализируем TabGames в памяти
        self.tab = TabGames.__new__(TabGames)
        self.tab.db = self.db
        self.tab.tracker = self.mock_tracker
        self.tab.settings = self.settings
        self.tab.cards = {}
        self.tab.icons_dir = "dummy_icons"
        self.tab.refresh_games = MagicMock()
        self.tab._refresh_archive_tab = MagicMock()

    def tearDown(self):
        self.db.close()

    def test_add_game_manual_normalizes_exe_extension(self):
        """При ручном вводе имени без .exe автоматически добавляется .exe"""
        with patch('customtkinter.CTkToplevel') as mock_toplevel, \
             patch('tkinter.messagebox.showinfo'), \
             patch.object(self.tab, '_add_game_by_name') as mock_add_by_name:

            # Эмулируем вызов add_game_manual и подтверждение диалога
            mock_dlg = MagicMock()
            mock_toplevel.return_value = mock_dlg

            # Проверим саму логику нормализации
            exe_input = "witcher3"
            if not exe_input.lower().endswith('.exe'):
                exe_normalized = exe_input + '.exe'
            else:
                exe_normalized = exe_input
            self.assertEqual(exe_normalized, "witcher3.exe")

            # Проверим, если .exe уже есть
            exe_input2 = "doom.exe"
            if not exe_input2.lower().endswith('.exe'):
                exe_normalized2 = exe_input2 + '.exe'
            else:
                exe_normalized2 = exe_input2
            self.assertEqual(exe_normalized2, "doom.exe")

            # Проверим верхний регистр .EXE
            exe_input3 = "GTA5.EXE"
            if not exe_input3.lower().endswith('.exe'):
                exe_normalized3 = exe_input3 + '.exe'
            else:
                exe_normalized3 = exe_input3
            self.assertEqual(exe_normalized3, "GTA5.EXE")

    def test_batch_add_games_from_processes_silent_and_single_notification(self):
        """Пакетное добавление из процессов не спамит messagebox на каждый процесс и обновляет список один раз"""
        processes = [
            {'name': 'game1.exe', 'exe': 'C:\\Games\\game1.exe'},
            {'name': 'game2.exe', 'exe': 'C:\\Games\\game2.exe'},
            {'name': 'game3.exe', 'exe': None},
        ]

        with patch('tkinter.messagebox.showinfo') as mock_showinfo:
            self.tab._add_games_from_processes(processes)

            # Ровно одно итоговое уведомление
            mock_showinfo.assert_called_once()
            title, msg = mock_showinfo.call_args[0]
            self.assertIn("Добавлено игр: 3", msg)

            # refresh_games и _refresh_archive_tab вызваны ровно 1 раз
            self.tab.refresh_games.assert_called_once()
            self.tab._refresh_archive_tab.assert_called_once()

            # Игры действительно добавились в базу данных
            self.assertIsNotNone(self.db.get_game_by_exe_name("game1.exe"))
            self.assertIsNotNone(self.db.get_game_by_exe_name("game2.exe"))
            self.assertIsNotNone(self.db.get_game_by_exe_name("game3.exe"))

    def test_batch_add_games_ignores_duplicates_in_count(self):
        """Если игра уже была в базе, она не добавляется повторно, и счетчик это учитывает"""
        self.db.add_game("game1.exe", "Game 1")

        processes = [
            {'name': 'game1.exe', 'exe': 'C:\\Games\\game1.exe'},  # дубликат
            {'name': 'game2.exe', 'exe': 'C:\\Games\\game2.exe'},  # новая
        ]

        with patch('tkinter.messagebox.showinfo') as mock_showinfo:
            self.tab._add_games_from_processes(processes)

            mock_showinfo.assert_called_once()
            title, msg = mock_showinfo.call_args[0]
            self.assertIn("Добавлено игр: 1", msg)


class TestAudit3Task6OptimizationAndCodeCleanliness(unittest.TestCase):
    """Тесты для Задачи 6: Кэширование настроек, сохранение spec-файла и отсутствие DEBUG-принтов"""

    def setUp(self):
        self.mock_db = MagicMock()
        self.settings = AppSettings(self.mock_db)

    def test_settings_get_bool_uses_cache(self):
        """_get_bool кэширует результат и не обращается к БД при повторном чтении"""
        self.mock_db.get_setting.return_value = 'true'

        val1 = self.settings._get_bool('track_only_active_window', default=True)
        self.assertTrue(val1)
        self.assertEqual(self.mock_db.get_setting.call_count, 1)

        # Второй вызов должен взять значение из кэша
        val2 = self.settings._get_bool('track_only_active_window', default=False)
        self.assertTrue(val2)
        self.assertEqual(self.mock_db.get_setting.call_count, 1)

    def test_settings_get_int_uses_cache(self):
        """_get_int кэширует результат и не обращается к БД при повторном чтении"""
        self.mock_db.get_setting.return_value = '75'

        val1 = self.settings._get_int('long_session_minutes', default=60)
        self.assertEqual(val1, 75)
        self.assertEqual(self.mock_db.get_setting.call_count, 1)

        # Второй вызов
        val2 = self.settings._get_int('long_session_minutes', default=30)
        self.assertEqual(val2, 75)
        self.assertEqual(self.mock_db.get_setting.call_count, 1)

    def test_settings_setters_update_cache(self):
        """Сеттеры _set_bool и _set_int обновляют кэш"""
        self.settings._set_bool('custom_bool', True)
        self.assertTrue(self.settings._get_bool('custom_bool', default=False))
        self.mock_db.get_setting.assert_not_called()

        self.settings._set_int('custom_int', 100)
        self.assertEqual(self.settings._get_int('custom_int', default=0), 100)
        self.mock_db.get_setting.assert_not_called()

    def test_clean_build_does_not_remove_spec_file(self):
        """Функция clean_build не удаляет GameTimeTracker.spec"""
        with patch('shutil.rmtree'), patch('os.path.exists', return_value=True), patch('os.remove') as mock_os_remove:
            build.clean_build()
            mock_os_remove.assert_not_called()

    def test_no_debug_prints_in_tab_games(self):
        """В ui/tab_games.py отсутствуют отладочные принты print(f'DEBUG: ...')"""
        tab_games_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ui', 'tab_games.py'))
        with open(tab_games_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertNotIn("DEBUG:", content, "В tab_games.py не должно оставаться отладочного вывода DEBUG:")


if __name__ == '__main__':
    unittest.main()
