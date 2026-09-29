import os
import sys
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import customtkinter as ctk

from database import Database
from settings import AppSettings
from tracker import GameTracker
from ui.main_window import MainWindow, NotificationsDialog
from ui.tab_games import TabGames
from ui.tab_stats import TabStats
from ui.settings_window import SettingsWindow


class TestBugUX2Tasks(unittest.TestCase):
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
        self.settings = AppSettings(self.db)
        self.tracker = GameTracker(self.db, self.settings)

    def tearDown(self):
        self.tracker.stop()
        self.db.close()

    # ------------------ TASK 1 ------------------
    def test_task1_background_detection_does_not_force_foreground(self):
        """1. При обнаружении процесса окно не восстанавливается принудительно."""
        window = MainWindow(self.db, self.tracker, self.settings)
        window.withdraw()

        # Мокаем deiconify, lift, focus_force
        window.deiconify = MagicMock()
        window.lift = MagicMock()
        window.focus_force = MagicMock()

        # Поступает фоновое обнаружение
        window.add_detected_notification("newgame.exe", "C:\\Games\\newgame.exe")

        # Окно НЕ должно было принудительно восстанавливаться
        window.deiconify.assert_not_called()
        window.lift.assert_not_called()
        window.focus_force.assert_not_called()

        # Уведомление должно быть сохранено в списке и бейдж должен обновиться
        self.assertEqual(len(window.pending_notifications), 1)
        self.assertEqual(window.pending_notifications[0]['exe_name'], "newgame.exe")
        self.assertIn("1", window.notifications_btn.cget("text"))

        window.destroy()

    def test_task1_click_on_notification_restores_and_opens_dialog(self):
        """1. Только при клике по уведомлению открывается окно добавления игры."""
        window = MainWindow(self.db, self.tracker, self.settings)
        window.withdraw()
        window.add_detected_notification("game_to_add.exe", "C:\\Games\\game_to_add.exe")

        # Мокаем show_window и prompt_add_new_game
        window.show_window = MagicMock()
        window.prompt_add_new_game = MagicMock()

        # Пользователь кликает по уведомлению
        window.open_detected_game_from_notification()

        window.show_window.assert_called_once()
        window.prompt_add_new_game.assert_called_once_with("game_to_add.exe", "C:\\Games\\game_to_add.exe")

        window.destroy()

    def test_task1_notifications_dialog_management(self):
        """1. Список уведомлений в приложении позволяет добавить, не отслеживать или пропустить."""
        window = MainWindow(self.db, self.tracker, self.settings)
        window.add_detected_notification("game1.exe", "C:\\Games\\game1.exe")
        window.add_detected_notification("game2.exe", "C:\\Games\\game2.exe")

        dialog = NotificationsDialog(
            window, self.db, self.tracker,
            on_add_game=window.prompt_add_new_game,
            on_remove_notification=window.remove_pending_notification
        )

        self.assertEqual(len(window.pending_notifications), 2)

        # Пропускаем game1.exe
        dialog._skip("game1.exe")
        self.assertEqual(len(window.pending_notifications), 1)
        self.assertEqual(window.pending_notifications[0]['exe_name'], "game2.exe")

        # Выбираем «Не отслеживать» для game2.exe
        dialog._ignore("game2.exe")
        self.assertEqual(len(window.pending_notifications), 0)
        self.assertTrue(self.db.is_process_ignored("game2.exe"))

        dialog.destroy()
        window.destroy()

    # ------------------ TASK 2 ------------------
    def test_task2_ignore_persists_across_restart(self):
        """2. Решение «НЕ ОТСЛЕЖИВАТЬ» сохраняется в БД и загружается после перезапуска."""
        # Пользователь выбирает игнорировать процесс
        self.tracker.ignore_exe("notepad.exe")
        self.assertIn("notepad.exe", self.tracker._ignored_exes)
        self.assertTrue(self.db.is_process_ignored("notepad.exe"))

        # Симулируем перезапуск приложения с тем же объектом базы данных
        new_tracker = GameTracker(self.db, self.settings)
        self.assertIn("notepad.exe", new_tracker._ignored_exes)

        # Разрешаем отслеживание
        new_tracker.unignore_exe("notepad.exe")
        self.assertNotIn("notepad.exe", new_tracker._ignored_exes)
        self.assertFalse(self.db.is_process_ignored("notepad.exe"))
        new_tracker.stop()

    def test_task2_settings_window_ignored_section(self):
        """2. В окне настроек отображаются игнорируемые процессы и кнопка отмены решения."""
        self.tracker.ignore_exe("discord.exe")
        settings_win = SettingsWindow(self.root, self.db, self.settings)
        settings_win.master.tracker = self.tracker

        # Проверяем, что discord.exe отображается в списке
        ignored_rows = self.db.get_ignored_processes()
        self.assertEqual(len(ignored_rows), 1)
        self.assertEqual(ignored_rows[0]['exe_name'], "discord.exe")

        # Отменяем игнорирование через SettingsWindow
        settings_win._unignore_process("discord.exe")
        self.assertFalse(self.db.is_process_ignored("discord.exe"))
        self.assertNotIn("discord.exe", self.tracker._ignored_exes)

        settings_win.destroy()

    # ------------------ TASK 3 ------------------
    def test_task3_rename_game_updates_search_filter(self):
        """3. Переименование игры повторно применяет активный поисковый фильтр."""
        tab = TabGames(self.root, self.db, self.tracker, self.settings)
        g_id = self.db.add_game("witcher.exe", "The Witcher 3")
        tab.refresh_games()

        # Вводим поисковый запрос "Witcher"
        tab.search_var.set("Witcher")
        tab.filter_games()
        # Карточка отображается (packed)
        self.assertIn(g_id, tab.cards)
        self.assertEqual(tab.cards[g_id].winfo_manager(), "pack")

        # Переименовываем в "Cyberpunk 2077"
        tab.rename_game(g_id, "Cyberpunk 2077")

        # Теперь карточка не должна отображаться, так как "Cyberpunk 2077" не содержит "witcher"
        self.assertEqual(tab.cards[g_id].winfo_manager(), "")

        # Переименовываем обратно в "Witcher Remake"
        tab.rename_game(g_id, "Witcher Remake")
        self.assertEqual(tab.cards[g_id].winfo_manager(), "pack")

        tab.destroy()

    # ------------------ TASK 4 ------------------
    def test_task4_search_filter_preserved_after_refresh(self):
        """4. Поисковый фильтр сохраняется и автоматически применяется после refresh_games."""
        tab = TabGames(self.root, self.db, self.tracker, self.settings)
        g1 = self.db.add_game("witcher3.exe", "The Witcher 3")
        g2 = self.db.add_game("cyberpunk.exe", "Cyberpunk 2077")
        tab.refresh_games()

        # Вводим "Witcher"
        tab.search_var.set("Witcher")
        tab.filter_games()
        self.assertEqual(tab.cards[g1].winfo_manager(), "pack")
        self.assertEqual(tab.cards[g2].winfo_manager(), "")

        # Пользователь меняет сортировку (вызывает refresh_games)
        tab.sort_option.set("📅 По дате добавления")
        tab.refresh_games()

        # Проверяем: поле поиска по-прежнему "Witcher", и фильтр остался примененным!
        self.assertEqual(tab.search_var.get(), "Witcher")
        self.assertEqual(tab.cards[g1].winfo_manager(), "pack")
        self.assertEqual(tab.cards[g2].winfo_manager(), "")

        tab.destroy()

    # ------------------ TASK 5 ------------------
    def test_task5_stats_include_archive_switch(self):
        """5. Переключатель «Учитывать архив» в статистике влияет на все показатели."""
        # 1 активная игра: 2 часа (7200 сек), 2 сессии по 1 ч
        active_id = self.db.add_game("active.exe", "Active Game")
        self.db.update_game_time(active_id, 7200)
        s1 = self.db.start_session(active_id)
        self.db.end_session(s1, 3600)
        s2 = self.db.start_session(active_id)
        self.db.end_session(s2, 3600)

        # 1 архивная игра: 10 часов (36000 сек), 1 сессия на 10 ч
        archived_id = self.db.add_game("archived.exe", "Archived Game")
        self.db.update_game_time(archived_id, 36000)
        s3 = self.db.start_session(archived_id)
        self.db.end_session(s3, 36000)
        self.db.archive_game(archived_id)

        tab = TabStats(self.root, self.db)

        # 1. По умолчанию «Учитывать архив» выключен:
        self.assertFalse(tab.include_archive_var.get())
        # Общее время = 2.0 ч
        self.assertIn("2.0 ч", tab.card_total_hours.value_label.cget("text"))
        self.assertNotIn("12.0 ч", tab.card_total_hours.value_label.cget("text"))
        # Самая долгая сессия среди активных = 1.0 ч (Active Game), а не 10 ч
        self.assertIn("Active Game", tab.card_longest_session.value_label.cget("text"))
        self.assertIn("1.0 ч", tab.card_longest_session.value_label.cget("text"))
        # Топ игр содержит только Active Game
        ax = tab.top_fig.axes[0]
        top_labels = [t.get_text() for t in ax.get_yticklabels()]
        self.assertIn("Active Game", top_labels)
        self.assertFalse(any("Archived Game" in l for l in top_labels))

        # 2. Включаем «Учитывать архив»:
        tab.include_archive_var.set(True)
        tab.load_stats()

        # Общее время = 12.0 ч (2.0 + 10.0)
        self.assertIn("12.0 ч", tab.card_total_hours.value_label.cget("text"))
        # Самая долгая сессия теперь Archived Game (10.0 ч)
        self.assertIn("Archived Game", tab.card_longest_session.value_label.cget("text"))
        self.assertIn("10.0 ч", tab.card_longest_session.value_label.cget("text"))
        # Топ игр включает Archived Game
        ax2 = tab.top_fig.axes[0]
        top_labels2 = [t.get_text() for t in ax2.get_yticklabels()]
        self.assertTrue(any("Archived Game" in l for l in top_labels2))

        tab.destroy()


if __name__ == '__main__':
    unittest.main()
