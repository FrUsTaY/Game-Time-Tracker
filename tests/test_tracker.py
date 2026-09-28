import unittest
import sys
import os
import ctypes
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from tracker import GameTracker


class TestTrackerIcon(unittest.TestCase):
    """Тесты для GameTracker.get_exe_icon и проверки отсутствия утечек GDI/USER объектов"""

    def setUp(self):
        # GameTracker требует db и settings, передаем моки/None если используются только утилиты
        class DummyDB:
            pass
        class DummySettings:
            pass
        self.tracker = GameTracker(DummyDB(), DummySettings())

    def test_get_exe_icon_nonexistent(self):
        """Проверка возврата None для несуществующего пути"""
        res = self.tracker.get_exe_icon("C:\\nonexistent_game_path_12345.exe")
        self.assertIsNone(res)

    def test_get_exe_icon_empty_path(self):
        """Проверка возврата None для пустого пути"""
        res = self.tracker.get_exe_icon("")
        self.assertIsNone(res)

    def test_get_exe_icon_valid(self):
        """Проверка успешного извлечения иконки из реального исполняемого файла"""
        # sys.executable всегда существует на Windows
        res = self.tracker.get_exe_icon(sys.executable, size=32)
        if res is not None:
            self.assertIsInstance(res, Image.Image)
            self.assertEqual(res.size, (32, 32))

    def test_no_gdi_or_user_handle_leaks(self):
        """Проверка отсутствия утечек дескрипторов GDI и USER при повторном извлечении иконки"""
        # Находим гарантированный exe с иконкой
        test_exe = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "explorer.exe")
        if not os.path.exists(test_exe):
            test_exe = sys.executable

        ctypes.windll.user32.GetGuiResources.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        ctypes.windll.user32.GetGuiResources.restype = ctypes.c_uint
        hProcess = ctypes.windll.kernel32.GetCurrentProcess()

        # Прогрев (разовое выделение системных кэшей)
        self.tracker.get_exe_icon(test_exe, size=32)

        initial_user = ctypes.windll.user32.GetGuiResources(hProcess, 1)
        initial_gdi = ctypes.windll.user32.GetGuiResources(hProcess, 0)

        # Выполняем 30 итераций
        for _ in range(30):
            icon = self.tracker.get_exe_icon(test_exe, size=32)
            self.assertIsNotNone(icon)

        final_user = ctypes.windll.user32.GetGuiResources(hProcess, 1)
        final_gdi = ctypes.windll.user32.GetGuiResources(hProcess, 0)

        self.assertEqual(final_user, initial_user, f"Утечка USER объектов: было {initial_user}, стало {final_user}")
        self.assertEqual(final_gdi, initial_gdi, f"Утечка GDI объектов: было {initial_gdi}, стало {final_gdi}")


class TestTrackerSessionLifecycle(unittest.TestCase):
    """Тесты жизненного цикла сессий GameTracker: периодический сброс (flush) и корректное закрытие"""

    def setUp(self):
        from database import Database
        from settings import AppSettings

        self.db = Database(":memory:")
        self.settings = AppSettings(self.db)
        self.tracker = GameTracker(self.db, self.settings)
        self.game_id = self.db.add_game("game1.exe", "Game 1")

    def tearDown(self):
        self.tracker.stop()
        self.db.close()

    def test_flush_session(self):
        """Проверка промежуточного сохранения прогресса сессии в БД"""
        session_id = self.db.start_session(self.game_id)
        session_info = {
            'session_id': session_id,
            'current_seconds': 60,
            'last_flushed_seconds': 0,
            'initial_total_seconds': 0,
            'process_pid': 1234,
            'was_active': True
        }
        self.tracker.active_sessions[self.game_id] = session_info

        # Выполняем промежуточный сброс
        self.tracker._flush_session(self.game_id, session_info)

        # Проверяем, что last_flushed_seconds обновился
        self.assertEqual(session_info['last_flushed_seconds'], 60)

        # Проверяем базу данных
        game = self.db.get_game_by_id(self.game_id)
        self.assertEqual(game['total_seconds'], 60)

        active = self.db.get_active_sessions()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]['duration_seconds'], 60)
        self.assertIsNone(active[0]['ended_at'])

    def test_close_session_flushes_only_remaining_delta(self):
        """Проверка, что при закрытии сессии сбрасывается только оставшаяся дельта (без дублирования)"""
        session_id = self.db.start_session(self.game_id)
        session_info = {
            'session_id': session_id,
            'current_seconds': 60,
            'last_flushed_seconds': 0,
            'initial_total_seconds': 0,
            'process_pid': 1234,
            'was_active': True
        }
        self.tracker.active_sessions[self.game_id] = session_info

        # 1-й сброс на 60 сек
        self.tracker._flush_session(self.game_id, session_info)
        self.assertEqual(self.db.get_game_by_id(self.game_id)['total_seconds'], 60)

        # Прошло еще 15 секунд (всего 75)
        session_info['current_seconds'] = 75

        # Закрываем сессию
        self.tracker._close_session(self.game_id, session_info)

        # В games должно стать 75 (60 ранее + 15 дельта), а не 60 + 75 = 135
        game = self.db.get_game_by_id(self.game_id)
        self.assertEqual(game['total_seconds'], 75)

        # В sessions должно быть duration_seconds=75 и ended_at выставлен
        active = self.db.get_active_sessions()
        self.assertEqual(len(active), 0)

        with self.db.lock:
            cur = self.db.conn.cursor()
            cur.execute("SELECT ended_at, duration_seconds FROM sessions WHERE id = ?", (session_id,))
            row = cur.fetchone()
            self.assertIsNotNone(row['ended_at'])
            self.assertEqual(row['duration_seconds'], 75)

    def test_close_session_zero_duration_closes_cleanly(self):
        """Проверка, что сессия с нулевой длительностью также закрывается (ended_at выставляется)"""
        session_id = self.db.start_session(self.game_id)
        session_info = {
            'session_id': session_id,
            'current_seconds': 0,
            'last_flushed_seconds': 0,
            'initial_total_seconds': 0,
            'process_pid': 1234,
            'was_active': False
        }
        self.tracker.active_sessions[self.game_id] = session_info

        self.tracker._close_session(self.game_id, session_info)

        # Сессия должна быть закрыта (не оставаться в активных)
        self.assertEqual(len(self.db.get_active_sessions()), 0)
        with self.db.lock:
            cur = self.db.conn.cursor()
            cur.execute("SELECT ended_at, duration_seconds FROM sessions WHERE id = ?", (session_id,))
            row = cur.fetchone()
            self.assertIsNotNone(row['ended_at'])
            self.assertEqual(row['duration_seconds'], 0)


class TestTrackerActiveWindow(unittest.TestCase):
    """Тесты проверки активности окна игры и безопасности от Unicode сбоев"""

    def setUp(self):
        from database import Database
        from settings import AppSettings

        self.db = Database(":memory:")
        self.settings = AppSettings(self.db)
        self.tracker = GameTracker(self.db, self.settings)

    def tearDown(self):
        self.tracker.stop()
        self.db.close()

    def test_is_game_active_track_only_disabled(self):
        """Если отслеживание только активного окна выключено, всегда возвращается True"""
        self.settings.track_only_active_window = False
        self.assertTrue(self.tracker._is_game_active(1, 100, None))
        self.assertTrue(self.tracker._is_game_active(1, 100, 999))

    def test_is_game_active_direct_pid_match(self):
        """Прямое совпадение PID процесса игры и активного окна"""
        self.settings.track_only_active_window = True
        self.assertTrue(self.tracker._is_game_active(1, 1234, 1234))

    def test_is_game_active_in_game_pids(self):
        """Активный PID найден в списке известных PID процесса игры"""
        self.settings.track_only_active_window = True
        self.assertTrue(self.tracker._is_game_active(1, 1234, 5678, game_pids=[1234, 5678]))

    def test_is_game_active_none_pid(self):
        """Если активный PID None, возвращается False при track_only=True"""
        self.settings.track_only_active_window = True
        self.assertFalse(self.tracker._is_game_active(1, 1234, None))

    def test_is_game_active_unrelated_pid(self):
        """Чужой PID возвращает False"""
        self.settings.track_only_active_window = True
        self.assertFalse(self.tracker._is_game_active(1, 1234, 9999, game_pids=[1234]))

    def test_get_active_window_pid_handles_exceptions_cleanly(self):
        """_get_active_window_pid возвращает None при ошибках без падений"""
        from unittest.mock import patch
        with patch('win32gui.GetForegroundWindow', side_effect=RuntimeError("GDI error")):
            pid = self.tracker._get_active_window_pid()
            self.assertIsNone(pid)

        with patch('win32gui.GetForegroundWindow', return_value=0):
            pid = self.tracker._get_active_window_pid()
            self.assertIsNone(pid)

    def test_unicode_titles_do_not_crash_active_window_check(self):
        """Проверка, что окна с Unicode и эмодзи в заголовках не ломают трекинг"""
        from unittest.mock import patch
        # Имитируем окно с эмодзи и иероглифами в заголовке
        with patch('win32gui.GetForegroundWindow', return_value=99999), \
             patch('win32process.GetWindowThreadProcessId', return_value=(1, 4321)):
            pid = self.tracker._get_active_window_pid()
            self.assertEqual(pid, 4321)
            # Проверяем, что _is_game_active успешно определяет совпадение PID
            is_active = self.tracker._is_game_active(1, 4321, pid)
            self.assertTrue(is_active)


class TestMainWindowExit(unittest.TestCase):
    """Тест передачи управления on_exit при выходе через MainWindow.quit_app"""

    def test_quit_app_calls_on_exit(self):
        from unittest.mock import MagicMock
        from ui.main_window import MainWindow

        mock_exit = MagicMock()
        # Создаем окно с dummy параметрами
        window = MainWindow.__new__(MainWindow)
        window.on_exit = mock_exit

        # Вызываем quit_app
        window.quit_app()

        mock_exit.assert_called_once()


if __name__ == '__main__':
    unittest.main()
