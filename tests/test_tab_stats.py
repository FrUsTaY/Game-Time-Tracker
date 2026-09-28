import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import customtkinter as ctk
from database import Database
from ui.tab_stats import TabStats


class TestTabStats(unittest.TestCase):
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
        self.game_id = self.db.add_game("game1.exe", "Game One")
        self.db.update_game_time(self.game_id, 7200)
        # Add some sessions
        s1 = self.db.start_session(self.game_id)
        self.db.end_session(s1, 3600)
        s2 = self.db.start_session(self.game_id)
        self.db.end_session(s2, 3600)

    def tearDown(self):
        self.db.close()

    def test_activity_graph_figure_canvas_reused(self):
        """Проверка, что Figure и Canvas переиспользуются при смене периодов, устраняя утечки памяти."""
        tab = TabStats(self.root, self.db)
        self.assertIsNotNone(tab.activity_fig)
        self.assertIsNotNone(tab.activity_canvas)

        initial_fig = tab.activity_fig
        initial_canvas = tab.activity_canvas

        # Переключаем периоды 10 раз
        for period in ["7", "30", "90", "7", "30", "90"]:
            tab.period_var.set(period)
            tab.update_activity_graph()
            self.assertIs(tab.activity_fig, initial_fig)
            self.assertIs(tab.activity_canvas, initial_canvas)

        tab.destroy()

    def test_top_games_figure_canvas_reused(self):
        """Проверка, что Figure и Canvas для топа игр переиспользуются при обновлении."""
        tab = TabStats(self.root, self.db)
        self.assertIsNotNone(tab.top_fig)
        self.assertIsNotNone(tab.top_canvas)

        initial_fig = tab.top_fig
        initial_canvas = tab.top_canvas

        tab._update_top_games()
        self.assertIs(tab.top_fig, initial_fig)
        self.assertIs(tab.top_canvas, initial_canvas)

        tab.destroy()

    def test_destroy_cleanup_figures(self):
        """Проверка корректного освобождения Matplotlib объектов при destroy()."""
        tab = TabStats(self.root, self.db)
        self.assertIsNotNone(tab.top_fig)
        self.assertIsNotNone(tab.activity_fig)

        tab.destroy()
        self.assertIsNone(tab.top_fig)
        self.assertIsNone(tab.top_canvas)
        self.assertIsNone(tab.activity_fig)
        self.assertIsNone(tab.activity_canvas)


if __name__ == '__main__':
    unittest.main()
