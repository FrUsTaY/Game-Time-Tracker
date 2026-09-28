import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import get_base_dir, resource_path
from database import Database


class TestUtilsAndPaths(unittest.TestCase):
    def test_get_base_dir_normal(self):
        """Проверка get_base_dir в нормальном режиме работы из исходников."""
        base_dir = get_base_dir()
        self.assertTrue(os.path.isabs(base_dir))
        self.assertTrue(os.path.exists(os.path.join(base_dir, "main.py")))

    def test_get_base_dir_frozen(self):
        """Проверка get_base_dir при sys.frozen = True (PyInstaller)."""
        with patch.object(sys, 'frozen', True, create=True), \
             patch.object(sys, 'executable', r'C:\App\GameTimeTracker.exe'):
            base_dir = get_base_dir()
            self.assertEqual(base_dir, r'C:\App')

    def test_resource_path_normal(self):
        """Проверка resource_path при нормальном запуске."""
        res = resource_path("assets/icon.png")
        self.assertTrue(os.path.isabs(res))
        self.assertTrue(os.path.exists(res))

    def test_resource_path_meipass(self):
        """Проверка resource_path в среде PyInstaller с _MEIPASS."""
        fake_temp = r"C:\Temp\_MEI12345"
        with patch.object(sys, 'frozen', True, create=True), \
             patch.object(sys, '_MEIPASS', fake_temp, create=True), \
             patch('os.path.exists') as mock_exists:
            # Если файл существует в _MEIPASS
            mock_exists.return_value = True
            res = resource_path("assets/icon.png")
            self.assertEqual(res, os.path.normpath(r"C:\Temp\_MEI12345\assets\icon.png"))

    def test_database_default_path_independent_of_cwd(self):
        """Проверка, что путь по умолчанию в Database всегда строится от get_base_dir()."""
        orig_cwd = os.getcwd()
        try:
            # Создаем временную директорию и переходим в неё
            temp_cwd = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tests'))
            os.chdir(temp_cwd)

            expected_default = os.path.join(get_base_dir(), "data", "gametracker.db")
            # Проверяем инициализацию без аргументов (или со старым дефолтом)
            with patch.object(Database, '_create_tables'), \
                 patch.object(Database, 'cleanup_zombie_sessions'), \
                 patch('sqlite3.connect') as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                db1 = Database()
                self.assertEqual(db1.db_path, expected_default)

                db2 = Database("data/gametracker.db")
                self.assertEqual(db2.db_path, expected_default)
        finally:
            os.chdir(orig_cwd)


if __name__ == '__main__':
    unittest.main()
