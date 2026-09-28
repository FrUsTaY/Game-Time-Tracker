"""
tests/test_stage2_ux.py — тесты для UX-улучшений Этапа 2 (Задачи 6–10).
"""

import unittest
from unittest.mock import MagicMock, patch
import customtkinter as ctk
from datetime import date, datetime
import os
import tempfile

from database import Database
from settings import AppSettings
from ui.tab_calendar import TabCalendar
from ui.tab_archive import TabArchive
from ui.tab_stats import TabStats
from ui.widgets import GameCard, ArchiveCard


class TestStage2UX(unittest.TestCase):
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

    def test_task6_calendar_reset_day_details_on_month_change(self):
        """Задача 6: Переключение месяца сбрасывает детали дня в 'Выберите день'."""
        cal = TabCalendar(self.root, self.db)
        # Имитируем выбранный день
        cal.details_title.configure(text="15 Март 2026")
        cal.total_day_label.configure(text="Всего: 2 ч")

        cal.reset_day_details()
        self.assertEqual(cal.details_title.cget("text"), "Выберите день")
        self.assertEqual(cal.total_day_label.cget("text"), "")

        # Проверяем, что prev_month и next_month вызывают сброс
        cal.details_title.configure(text="20 Апрель 2026")
        with patch.object(cal, 'load_month_data'):
            cal.next_month()
            self.assertEqual(cal.details_title.cget("text"), "Выберите день")

            cal.details_title.configure(text="10 Май 2026")
            cal.prev_month()
            self.assertEqual(cal.details_title.cget("text"), "Выберите день")
        cal.destroy()

    def test_task7_processes_filter_hides_system_and_windowless(self):
        """Задача 7: AddFromProcessesDialog скрывает системные и фоновые процессы по умолчанию."""
        from ui.tab_games import AddFromProcessesDialog

        tracker_mock = MagicMock()
        tracker_mock.get_running_processes.return_value = [
            {'pid': 100, 'name': 'game.exe', 'exe': 'C:\\Games\\game.exe'},
            {'pid': 200, 'name': 'svchost.exe', 'exe': 'C:\\Windows\\system32\\svchost.exe'},
            {'pid': 300, 'name': 'notepad.exe', 'exe': 'C:\\Windows\\notepad.exe'},
            {'pid': 400, 'name': 'custom_tool.exe', 'exe': 'C:\\tool.exe'},
        ]

        with patch('win32gui.EnumWindows') as mock_enum:
            # Имитируем, что только game.exe имеет окно
            def fake_enum(cb, _):
                with patch('win32gui.IsWindowVisible', return_value=True), \
                     patch('win32process.GetWindowThreadProcessId', return_value=(0, 100)), \
                     patch('win32gui.GetWindowText', return_value="Awesome Game"):
                    cb(1234, None)
                return True
            mock_enum.side_effect = fake_enum

            dialog = AddFromProcessesDialog(self.root, tracker_mock, on_add=MagicMock())
            dialog.withdraw()

            # По умолчанию показаны только реальные окна и несистемные процессы
            filtered_names = [p['name'] for p in dialog.filtered_processes]
            self.assertIn('game.exe', filtered_names)
            self.assertNotIn('svchost.exe', filtered_names)

            # Если включить показ фоновых процессов
            dialog.show_background_var.set(True)
            dialog.filter_processes()
            all_filtered_names = [p['name'] for p in dialog.filtered_processes]
            self.assertIn('svchost.exe', all_filtered_names)
            dialog.destroy()

    def test_task8_archive_card_delete_button_and_delete_game(self):
        """Задача 8: Наличие кнопки 'Удалить' в ArchiveCard и метод delete_game в TabArchive."""
        on_restore_mock = MagicMock()
        on_delete_mock = MagicMock()

        card = ArchiveCard(
            self.root,
            game_id=1,
            display_name="Test Game",
            total_seconds=3600,
            added_at="2026-09-01",
            archived_at="2026-09-20",
            icon_path=None,
            on_restore=on_restore_mock,
            on_delete=on_delete_mock
        )
        self.assertTrue(hasattr(card, 'delete_btn'))
        self.assertEqual(card.delete_btn.cget("text"), "🗑 Удалить")
        card.destroy()

        # Проверяем TabArchive.delete_game
        game_id = self.db.add_game("archived_game.exe", "Archived Game", None)
        self.db.archive_game(game_id)
        self.assertTrue(self.db.get_game_by_id(game_id)['is_archived'])

        archive_tab = TabArchive(self.root, self.db)
        with patch('tkinter.messagebox.askyesno', return_value=True):
            archive_tab.delete_game(game_id)

        self.assertIsNone(self.db.get_game_by_id(game_id))
        archive_tab.destroy()

    def test_task9_stats_graph_90_days_date_thinning(self):
        """Задача 9: Для 90 дней метки дат на графике активности прореживаются."""
        stats_tab = TabStats(self.root, self.db)
        stats_tab.period_var.set("90")
        stats_tab.update_activity_graph()

        ax = stats_tab.activity_fig.axes[0]
        xticks = ax.get_xticks()
        # Для 90 дней количество меток должно быть существенно меньше 90 (около 13-14)
        self.assertLess(len(xticks), 25)
        self.assertGreater(len(xticks), 5)
        stats_tab.destroy()

    def test_task10_game_card_rename_cancel_on_escape(self):
        """Задача 10: Нажатие Escape отменяет переименование и не вызывает on_rename."""
        on_rename_mock = MagicMock()
        card = GameCard(
            self.root,
            game_id=1,
            display_name="Original Name",
            total_seconds=100,
            last_launched=None,
            icon_path=None,
            on_archive=MagicMock(),
            on_delete=MagicMock(),
            on_rename=on_rename_mock,
            is_active=False
        )

        card._start_rename()
        # Находим entry внутри карточки
        entries = [w for w in card.winfo_children() if isinstance(w, ctk.CTkEntry)]
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        entry.delete(0, 'end')
        entry.insert(0, "Changed Name")

        # Эмулируем нажатие Escape
        entry.event_generate("<Escape>")
        card.update_idletasks()

        # on_rename НЕ должен быть вызван, имя должно остаться прежним
        on_rename_mock.assert_not_called()
        self.assertEqual(card.display_name, "Original Name")
        card.destroy()


if __name__ == '__main__':
    unittest.main()
