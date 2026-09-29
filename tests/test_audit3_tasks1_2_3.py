import os
import sys
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import customtkinter as ctk
from database import Database
from settings import AppSettings
from tracker import GameTracker, is_system_process, SYSTEM_EXCLUDE_EXES
from ui.tab_stats import TabStats
from ui.tab_calendar import TabCalendar


class TestAudit3Task1SafeDuration(unittest.TestCase):
    """Тесты для Задачи 1: Защита от краша при duration_seconds = NULL (None)"""

    @classmethod
    def setUpClass(cls):
        cls.root = ctk.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.update()
        except Exception:
            pass
        cls.root.destroy()

    def setUp(self):
        self.db = Database(":memory:")
        self.game_id = self.db.add_game("testgame.exe", "Test Game")

    def tearDown(self):
        self.db.close()

    def test_tab_stats_with_none_duration_session(self):
        """Проверка, что TabStats не падает с TypeError при duration_seconds = None"""
        # Создаем незавершенную сессию напрямую в БД с duration_seconds = NULL
        with self.db.lock:
            cur = self.db.conn.cursor()
            cur.execute(
                "INSERT INTO sessions (game_id, started_at, duration_seconds) VALUES (?, ?, NULL)",
                (self.game_id, "2026-09-28T10:00:00")
            )

        tab = TabStats(self.root, self.db)
        # Вызываем методы, которые ранее падали с TypeError: '>' not supported
        try:
            tab.update_activity_graph()
            tab._update_summary_cards()
        except TypeError as e:
            self.fail(f"TabStats выбросил TypeError при обработке сессии с None: {e}")
        finally:
            tab.destroy()

    def test_tab_calendar_with_none_duration_session(self):
        """Проверка, что TabCalendar не падает с TypeError при duration_seconds = None"""
        today = date.today()
        today_iso = today.strftime("%Y-%m-%d") + "T12:00:00"

        with self.db.lock:
            cur = self.db.conn.cursor()
            cur.execute(
                "INSERT INTO sessions (game_id, started_at, duration_seconds) VALUES (?, ?, NULL)",
                (self.game_id, today_iso)
            )

        tab = TabCalendar(self.root, self.db)
        tab.current_year = today.year
        tab.current_month = today.month

        # Вызываем загрузку данных календаря (ранее падало на duration <= 0)
        try:
            tab.load_month_data()
        except TypeError as e:
            self.fail(f"TabCalendar выбросил TypeError при обработке сессии с None: {e}")
        finally:
            tab.destroy()


class TestAudit3Task2IntelligentProcessFilter(unittest.TestCase):
    """Тесты для Задачи 2: Интеллектуальная фильтрация уведомлений о новых играх"""

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

    def test_is_system_process_exclusions(self):
        """Проверка распознавания системных имен и путей Windows"""
        # Системные имена из SYSTEM_EXCLUDE_EXES
        for name in ['cmd.exe', 'powershell.exe', 'explorer.exe', 'taskmgr.exe', 'git.exe', 'conhost.exe']:
            self.assertTrue(is_system_process(name), f"{name} должен быть распознан как системный")

        # Регистронезависимость
        self.assertTrue(is_system_process("CMD.EXE"))
        self.assertTrue(is_system_process("Explorer.Exe"))

        # Пути к Windows / System32
        self.assertTrue(is_system_process("customtool.exe", r"C:\Windows\System32\customtool.exe"))
        self.assertTrue(is_system_process("helper.exe", r"C:\Windows\SysWOW64\helper.exe"))
        self.assertTrue(is_system_process("service.exe", r"C:\Windows\service.exe"))

        # Обычные игры
        self.assertFalse(is_system_process("witcher3.exe", r"D:\Games\Witcher 3\bin\x64\witcher3.exe"))
        self.assertFalse(is_system_process("skyrimSE.exe", r"C:\Program Files (x86)\Steam\steamapps\common\Skyrim\skyrimSE.exe"))

    def test_notification_not_sent_for_headless_process(self):
        """Процесс без видимого окна верхнего уровня не отправляет уведомление"""
        self.settings.notify_new_game = True

        mock_proc = MagicMock()
        mock_proc.info = {'pid': 1111, 'name': 'background_tool.exe', 'exe': r'D:\Tools\background_tool.exe'}

        with patch('psutil.process_iter', return_value=[mock_proc]), \
             patch.object(self.tracker, '_has_visible_window', return_value=False), \
             patch.object(self.tracker, '_get_active_window_pid', return_value=None):
            self.tracker._check_processes()

        self.mock_tray.show_notification.assert_not_called()
        self.mock_on_notify.assert_not_called()

    def test_notification_not_sent_for_system_process_even_with_window(self):
        """Системный процесс (например, explorer.exe или cmd.exe) не отправляет уведомление, даже имея окно"""
        self.settings.notify_new_game = True

        mock_proc = MagicMock()
        mock_proc.info = {'pid': 2222, 'name': 'cmd.exe', 'exe': r'C:\Windows\System32\cmd.exe'}

        with patch('psutil.process_iter', return_value=[mock_proc]), \
             patch.object(self.tracker, '_has_visible_window', return_value=True), \
             patch.object(self.tracker, '_get_active_window_pid', return_value=None):
            self.tracker._check_processes()

        self.mock_tray.show_notification.assert_not_called()
        self.mock_on_notify.assert_not_called()

    def test_notification_sent_for_real_game_with_visible_window(self):
        """Обычная игра с видимым окном верхнего уровня успешно отправляет уведомление"""
        self.settings.notify_new_game = True

        mock_proc = MagicMock()
        mock_proc.info = {'pid': 3333, 'name': 'cyberpunk2077.exe', 'exe': r'D:\Games\Cyberpunk 2077\bin\cyberpunk2077.exe'}

        with patch('psutil.process_iter', return_value=[mock_proc]), \
             patch.object(self.tracker, '_has_visible_window', return_value=True), \
             patch.object(self.tracker, '_get_active_window_pid', return_value=None):
            self.tracker._check_processes()

        self.mock_tray.show_notification.assert_called_once()
        args = self.mock_tray.show_notification.call_args[0]
        self.assertIn("cyberpunk2077.exe", args[1].lower())
        self.mock_on_notify.assert_called_once()


class TestAudit3Task3ArchivedGamesStats(unittest.TestCase):
    """Тесты для Задачи 3: Корректный учёт времени архивированных игр в общей статистике"""

    @classmethod
    def setUpClass(cls):
        cls.root = ctk.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.update()
        except Exception:
            pass
        cls.root.destroy()

    def setUp(self):
        self.db = Database(":memory:")
        # Добавляем 1 активную игру (2 часа) и 1 архивированную игру (3 часа)
        self.active_id = self.db.add_game("active.exe", "Active Game")
        self.db.update_game_time(self.active_id, 7200)

        self.archived_id = self.db.add_game("archived.exe", "Archived Game")
        self.db.update_game_time(self.archived_id, 10800)
        self.db.archive_game(self.archived_id)  # отправляем в архив

    def tearDown(self):
        self.db.close()

    def test_summary_card_total_hours_includes_archived(self):
        """Карточка «Всего часов» учитывает как активные, так и архивные игры при включенном переключателе"""
        tab = TabStats(self.root, self.db)
        # По умолчанию архив выключен (только активные 2.0 ч)
        self.assertIn("2.0 ч", tab.card_total_hours.value_label.cget("text"))

        # Включаем учет архива: 2.0 ч + 3.0 ч = 5.0 ч (в архиве: 3.0 ч)
        tab.include_archive_var.set(True)
        tab.load_stats()
        card_text = tab.card_total_hours.value_label.cget("text")
        self.assertIn("5.0 ч", card_text)
        self.assertIn("3.0 ч", card_text)

        tab.destroy()

    def test_moving_game_to_archive_preserves_total_hours(self):
        """При включенном переключателе перенос активной игры в архив не уменьшает общее наигранное время"""
        tab = TabStats(self.root, self.db)
        tab.include_archive_var.set(True)
        tab.load_stats()
        text_before = tab.card_total_hours.value_label.cget("text")

        # Переносим активную игру в архив
        self.db.archive_game(self.active_id)
        tab.load_stats()
        text_after = tab.card_total_hours.value_label.cget("text")

        self.assertIn("5.0 ч", text_before)
        self.assertIn("5.0 ч", text_after)

        tab.destroy()

    def test_top_games_includes_archived_games(self):
        """График топа игр включает архивированные игры при включенном учете архива"""
        tab = TabStats(self.root, self.db)
        tab.include_archive_var.set(True)
        tab.load_stats()

        # Archived Game имеет 10800 сек (3 ч), Active Game имеет 7200 сек (2 ч)
        # Обе игры должны быть показаны
        self.assertIsNotNone(tab.top_fig)

        # Проверим, что на графике присутствуют метки обеих игр
        ax = tab.top_fig.axes[0]
        labels = [t.get_text() for t in ax.get_yticklabels()]
        self.assertTrue(any("Archived Game" in l for l in labels))
        self.assertTrue(any("Active Game" in l for l in labels))

        tab.destroy()


if __name__ == '__main__':
    unittest.main()
