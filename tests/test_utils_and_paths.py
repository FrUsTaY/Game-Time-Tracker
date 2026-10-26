import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import Database
from utils import get_base_dir, resource_path


class TestUtilsAndPaths(unittest.TestCase):
    def test_get_base_dir_normal(self):
        """Проверка get_base_dir в нормальном режиме работы из исходников."""
        base_dir = get_base_dir()
        self.assertTrue(os.path.isabs(base_dir))
        self.assertTrue(os.path.exists(os.path.join(base_dir, "main.py")))

    def test_get_base_dir_frozen(self):
        """Проверка get_base_dir при sys.frozen = True (PyInstaller).

        Путь собирается через os.path, поэтому тест работает и в Windows, и в CI на Linux.
        """
        fake_exe = os.path.join(tempfile.gettempdir(), "App", "GameTimeTracker.exe")
        with patch.object(sys, 'frozen', True, create=True), \
             patch.object(sys, 'executable', fake_exe):
            base_dir = get_base_dir()
            self.assertEqual(base_dir, os.path.dirname(os.path.abspath(fake_exe)))

    def test_resource_path_normal(self):
        """Проверка resource_path при нормальном запуске."""
        res = resource_path("assets/icon.png")
        self.assertTrue(os.path.isabs(res))
        self.assertTrue(os.path.exists(res))

    def test_resource_path_meipass(self):
        """Проверка resource_path в среде PyInstaller с _MEIPASS."""
        fake_temp = os.path.join(tempfile.gettempdir(), "_MEI12345")
        expected = os.path.normpath(os.path.join(fake_temp, "assets", "icon.png"))
        with patch.object(sys, 'frozen', True, create=True), \
             patch.object(sys, '_MEIPASS', fake_temp, create=True), \
             patch('os.path.exists') as mock_exists:
            # Если файл существует в _MEIPASS
            mock_exists.return_value = True
            res = resource_path("assets/icon.png")
            self.assertEqual(res, expected)

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
